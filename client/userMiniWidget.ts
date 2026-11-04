import { Chessground } from 'chessgroundx';
import { Api } from 'chessgroundx/api';

import { _, ngettext } from './i18n';
import { boardSettings } from './boardSettings';
import { timeago } from './datetime';
import { sizeMiniBoardHost } from './miniBoard';
import { ensureCataloguedVariantsLoaded, getLastMoveFen, splitVariantKey, VARIANTS } from './variants';
import { displayUsername } from './user';
import { renderFollowButtonState } from './followButton';
import { subscribeOngoingRealtime } from './ongoingRealtime';

interface MiniPerf {
    variant: string;
    rating: number;
    provisional: boolean;
    nb: number;
}

interface MiniPlaying {
    gameId: string;
    url: string;
    variant: string;
    fen: string;
    lastMove: string;
    w: string;
    wTitle: string;
    b: string;
    bTitle: string;
    orientation: 'white' | 'black';
}

interface MiniPayload {
    username: string;
    system?: boolean;
    title: string;
    online: boolean;
    patron: boolean;
    canMessage?: boolean;
    canFollow?: boolean;
    following?: boolean;
    joinedAt: string | null;
    count: {
        game: number;
        win: number;
        loss: number;
        draw: number;
        rated: number;
    };
    vsScore: {
        mineTenths: number;
        oppTenths: number;
    } | null;
    perfs: MiniPerf[];
    playing: MiniPlaying | null;
}

interface OngoingMessage {
    gameId: string;
    fen: string;
    lastMove: string;
}

interface CacheEntry {
    expiresAt: number;
    payload: MiniPayload;
}

const HOVER_DELAY_MS = 150;
const HOVER_INTENT_POLL_MS = 150;
const HOVER_INTENT_SENSITIVITY = 7;
const HIDE_DELAY_MS = 130;
const CACHE_TTL_MS = 8000;

function parseProfileId(target: HTMLElement): string | null {
    const href = target.getAttribute('data-href') ?? target.getAttribute('href');
    if (!href) return null;

    let url: URL;
    try {
        url = new URL(href, window.location.origin);
    } catch {
        return null;
    }

    const parts = url.pathname.split('/').filter(Boolean);
    if (parts.length < 2 || parts[0] !== '@') return null;
    return decodeURIComponent(parts[1]);
}

function clearElement(el: HTMLElement) {
    while (el.firstChild) el.removeChild(el.firstChild);
}

function formatJoinedAgo(value: string | null): string {
    if (!value) return '';
    const parsed = new Date(value);
    if (!Number.isFinite(parsed.getTime())) return '';
    return timeago(parsed.toISOString());
}

function formatTenthsScore(value: number): string {
    const points = Math.max(0, Math.trunc(value));
    const whole = Math.floor(points / 10);
    return points % 10 === 5 ? `${whole}½` : `${whole}`;
}

class UserMiniWidget {
    private readonly root: HTMLDivElement;
    private readonly content: HTMLDivElement;

    private hoverTimer?: number;
    private hideTimer?: number;
    private requestSeq = 0;

    private anchor?: HTMLElement;
    private anchorUser?: string;
    private overWidget = false;
    private lastMouseX = 0;
    private lastMouseY = 0;

    private cg?: Api;
    private liveGameId?: string;
    private liveVariantName?: string;
    private liveOrientation: 'white' | 'black' = 'white';

    private readonly cache = new Map<string, CacheEntry>();
    private ongoingRealtime: ReturnType<typeof subscribeOngoingRealtime> | null = null;

    constructor(
        private readonly assetURL: string,
        private readonly currentUsername: string,
        private readonly isAnon: boolean,
    ) {
        this.root = document.createElement('div');
        this.root.className = 'user-mini-widget hidden';

        this.content = document.createElement('div');
        this.content.className = 'user-mini-widget__content';
        this.root.appendChild(this.content);

        document.body.appendChild(this.root);

        this.root.addEventListener('mouseenter', () => {
            this.overWidget = true;
            this.clearHideTimer();
        });
        this.root.addEventListener('mouseleave', () => {
            this.overWidget = false;
            this.scheduleHide();
        });
    }

    init() {
        document.body.addEventListener('mouseover', this.onBodyMouseOver);
        document.body.addEventListener('mouseout', this.onBodyMouseOut);
        document.body.addEventListener('mousemove', this.onBodyMouseMove);
        window.addEventListener('scroll', this.onWindowChange, true);
        window.addEventListener('resize', this.onWindowChange);
    }

    private connectOngoingSource() {
        if (!this.liveGameId || this.ongoingRealtime !== null) return;

        const onMessage = (data: string) => {
            if (!this.liveGameId || !this.cg || !this.liveVariantName) return;
            const msg = JSON.parse(data) as OngoingMessage;
            if (msg.gameId !== this.liveGameId) return;

            const [lastMove, fen] = getLastMoveFen(this.liveVariantName, msg.lastMove, msg.fen);
            this.cg.set({
                fen,
                lastMove,
                orientation: this.liveOrientation,
            });
        };
        this.ongoingRealtime = subscribeOngoingRealtime(onMessage);
    }

    private disconnectOngoingSource() {
        this.ongoingRealtime?.close();
        this.ongoingRealtime = null;
    }

    private onWindowChange = () => {
        if (!this.anchor || this.root.classList.contains('hidden')) return;
        this.positionForAnchor(this.anchor);
    };

    private onBodyMouseOver = (event: MouseEvent) => {
        const target = event.target as HTMLElement | null;
        if (!target) return;
        this.lastMouseX = event.clientX;
        this.lastMouseY = event.clientY;

        const anchor = target.closest('.user-link') as HTMLElement | null;
        if (!anchor || this.root.contains(anchor)) return;

        const profileId = parseProfileId(anchor);
        if (!profileId) return;
        if (profileId === this.currentUsername && anchor.closest('#username')) return;

        this.anchor = anchor;
        this.anchorUser = profileId;

        this.clearHideTimer();
        this.scheduleShow(anchor, profileId);
    };

    private onBodyMouseMove = (event: MouseEvent) => {
        this.lastMouseX = event.clientX;
        this.lastMouseY = event.clientY;
    };

    private onBodyMouseOut = (event: MouseEvent) => {
        const target = event.target as HTMLElement | null;
        if (!target) return;
        const fromLink = target.closest('.user-link') as HTMLElement | null;
        if (!fromLink) return;

        const related = event.relatedTarget as HTMLElement | null;
        if (related && (this.root.contains(related) || fromLink.contains(related))) return;

        this.clearHoverTimer();
        this.scheduleHide();
    };

    private placeByPoint(x: number, y: number) {
        const spacing = 8;
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const widgetRect = this.root.getBoundingClientRect();

        let left = x + 20;
        if (left + widgetRect.width > vw - spacing) {
            left = vw - widgetRect.width - spacing;
        }
        if (left < spacing) left = spacing;

        let top = y + 16;
        if (top + widgetRect.height > vh - spacing) {
            top = y - widgetRect.height - spacing;
        }
        if (top < spacing) top = spacing;

        this.root.style.left = `${Math.round(left)}px`;
        this.root.style.top = `${Math.round(top)}px`;
        this.root.style.visibility = 'visible';
    }

    private scheduleShow(anchor: HTMLElement, profileId: string) {
        this.clearHoverTimer();
        const startX = this.lastMouseX;
        const startY = this.lastMouseY;
        this.hoverTimer = window.setTimeout(() => {
            this.hoverTimer = undefined;
            this.checkHoverIntent(anchor, profileId, startX, startY);
        }, HOVER_DELAY_MS);
    }

    private checkHoverIntent(anchor: HTMLElement, profileId: string, prevX: number, prevY: number) {
        if (this.anchor !== anchor || this.anchorUser !== profileId) return;

        const movement = Math.abs(this.lastMouseX - prevX) + Math.abs(this.lastMouseY - prevY);
        if (movement <= HOVER_INTENT_SENSITIVITY) {
            void this.show(anchor, profileId);
            return;
        }

        this.hoverTimer = window.setTimeout(() => {
            this.hoverTimer = undefined;
            this.checkHoverIntent(anchor, profileId, this.lastMouseX, this.lastMouseY);
        }, HOVER_INTENT_POLL_MS);
    }

    private scheduleHide() {
        this.clearHideTimer();
        this.hideTimer = window.setTimeout(() => {
            this.hideTimer = undefined;
            if (this.overWidget) return;
            this.root.classList.add('hidden');
            this.clearLiveBoard();
        }, HIDE_DELAY_MS);
    }

    private clearHoverTimer() {
        if (this.hoverTimer === undefined) return;
        window.clearTimeout(this.hoverTimer);
        this.hoverTimer = undefined;
    }

    private clearHideTimer() {
        if (this.hideTimer === undefined) return;
        window.clearTimeout(this.hideTimer);
        this.hideTimer = undefined;
    }

    private async show(anchor: HTMLElement, profileId: string) {
        this.root.classList.remove('hidden');
        this.positionForAnchor(anchor);
        this.renderLoading(profileId);

        const seq = ++this.requestSeq;
        try {
            const payload = await this.fetchMini(profileId);
            if (seq !== this.requestSeq || this.anchorUser !== profileId) return;
            // Rating performances are built-in variants only.  A current casual
            // game, however, can be a catalogued variant and needs board metadata.
            const playingVariant = payload.playing ? splitVariantKey(payload.playing.variant).base : null;
            if (playingVariant && !VARIANTS[playingVariant]) {
                try {
                    await ensureCataloguedVariantsLoaded();
                } catch (error) {
                    console.warn('Failed to load catalogued variants for user mini', error);
                }
            }
            if (seq !== this.requestSeq || this.anchorUser !== profileId) return;
            this.renderPayload(payload);
            this.positionForAnchor(anchor);
        } catch {
            if (seq !== this.requestSeq) return;
            this.root.classList.add('hidden');
            this.clearLiveBoard();
        }
    }

    private async fetchMini(profileId: string): Promise<MiniPayload> {
        const now = Date.now();
        const cached = this.cache.get(profileId);
        if (cached && cached.expiresAt > now) {
            return cached.payload;
        }

        const response = await fetch(`/@/${encodeURIComponent(profileId)}/mini`);
        if (!response.ok) throw new Error(`mini fetch failed: ${response.status}`);
        const payload = (await response.json()) as MiniPayload;

        this.cache.set(profileId, {
            expiresAt: now + CACHE_TTL_MS,
            payload,
        });

        return payload;
    }

    private renderLoading(profileId: string) {
        clearElement(this.content);

        const head = document.createElement('div');
        head.className = 'umw-head';
        head.textContent = profileId;
        this.content.appendChild(head);
    }

    private renderPayload(payload: MiniPayload) {
        clearElement(this.content);
        this.clearLiveBoard();

        const head = document.createElement('div');
        head.className = 'umw-head';

        const status = document.createElement('span');
        status.className = `umw-status ${payload.online ? 'online' : 'offline'}${
            payload.patron ? ' patron icon-patron-wing' : ''
        }`;
        status.setAttribute('aria-hidden', 'true');
        if (payload.patron) status.title = _('PyChess Patron');
        head.appendChild(status);

        const nameLink = document.createElement('a');
        nameLink.className = 'user-link';
        nameLink.href = `/@/${encodeURIComponent(payload.username)}`;
        nameLink.textContent = `${payload.title ? `${payload.title} ` : ''}${displayUsername(payload.username)}`;
        head.appendChild(nameLink);

        this.content.appendChild(head);

        if (payload.perfs.length > 0) {
            const perfList = document.createElement('div');
            perfList.className = 'umw-perfs';

            for (const perf of payload.perfs) {
                const key = splitVariantKey(perf.variant);
                const variant = VARIANTS[key.base];
                if (!variant) continue;

                const link = document.createElement('a');
                link.className = 'umw-perf icon';
                link.href = `/@/${encodeURIComponent(payload.username)}/perf/${perf.variant}`;
                link.setAttribute('data-icon', variant.icon(key.chess960));
                link.title = `${variant.displayName(key.chess960)} • ${perf.nb}`;
                link.textContent = `${perf.rating}${perf.provisional ? '?' : ''}`;
                perfList.appendChild(link);
            }

            this.content.appendChild(perfList);
        }

        const actions = this.renderActions(payload);
        if (actions) this.content.appendChild(actions);

        if (payload.vsScore) {
            const score = document.createElement('div');
            score.className = 'umw-score';
            score.textContent = `${_('Your score')}: ${formatTenthsScore(payload.vsScore.mineTenths)} - ${formatTenthsScore(payload.vsScore.oppTenths)}`;
            this.content.appendChild(score);
        }

        const details = document.createElement('div');
        details.className = 'umw-details';

        const games = document.createElement('span');
        const gamesCount = Math.max(0, payload.count?.game ?? 0);
        games.textContent = ngettext('%1 game', '%1 games', gamesCount);
        details.appendChild(games);

        const joined = formatJoinedAgo(payload.joinedAt);
        if (joined) {
            const joinedEl = document.createElement('span');
            joinedEl.className = 'umw-joined';
            joinedEl.textContent = `${_('Joined')} ${joined}`;
            details.appendChild(joinedEl);
        }

        this.content.appendChild(details);

        if (payload.playing) {
            const key = splitVariantKey(payload.playing.variant);
            const variant = VARIANTS[key.base];
            if (variant) {
                const gameLink = document.createElement('a');
                gameLink.className = 'umw-game-link';
                gameLink.href = payload.playing.url;

                const boardHost = document.createElement('div');
                boardHost.className = `umw-game-board ${variant.boardFamily} ${variant.pieceFamily} ${variant.ui.boardMark}`;
                if (variant.pocket) boardHost.classList.add('with-pockets');
                boardHost.style.margin = '0 auto';

                const boardWrap = document.createElement('div');
                boardWrap.className = `cg-wrap ${variant.board.cg} mini`;
                boardHost.appendChild(boardWrap);

                gameLink.appendChild(boardHost);

                const players = document.createElement('div');
                players.className = 'umw-game-players';
                players.textContent = `${payload.playing.wTitle ? `${payload.playing.wTitle} ` : ''}${displayUsername(payload.playing.w)} vs ${payload.playing.bTitle ? `${payload.playing.bTitle} ` : ''}${displayUsername(payload.playing.b)}`;
                gameLink.appendChild(players);

                this.content.appendChild(gameLink);

                boardSettings.assetURL = this.assetURL;
                boardSettings.updateScopedBoardStyle(variant, boardWrap);
                boardSettings.updateScopedPieceStyle(variant, boardWrap);
                sizeMiniBoardHost(boardWrap);

                const [lastMove, fen] = getLastMoveFen(variant.name, payload.playing.lastMove, payload.playing.fen);
                this.cg = Chessground(boardWrap, {
                    fen,
                    lastMove,
                    orientation: payload.playing.orientation,
                    dimensions: variant.board.dimensions,
                    coordinates: false,
                    viewOnly: true,
                    addDimensionsCssVarsTo: boardHost,
                    pocketRoles: variant.pocket?.roles,
                });
                this.liveGameId = payload.playing.gameId;
                this.liveVariantName = variant.name;
                this.liveOrientation = payload.playing.orientation;
                this.connectOngoingSource();
            }
        }
    }

    private renderActions(payload: MiniPayload): HTMLElement | undefined {
        const actions = document.createElement('div');
        actions.className = 'umw-actions upt__actions btn-rack';

        if (payload.system) {
            if (!this.isAnon && payload.username !== this.currentUsername && payload.canFollow) {
                actions.appendChild(this.makeFollowButton(payload.username, payload.following === true));
            }
            return actions.childElementCount > 0 ? actions : undefined;
        }

        const watchLink = this.makeActionLink(
            'icon icon-tv',
            `/@/${encodeURIComponent(payload.username)}/tv`,
            _('Watch'),
            true,
        );
        actions.appendChild(watchLink);

        if (!this.isAnon && payload.username !== this.currentUsername) {
            if (payload.canMessage !== false) {
                const messageLink = this.makeActionLink(
                    'icon icon-comment-o',
                    `/inbox/${encodeURIComponent(payload.username)}`,
                    _('Chat'),
                    true,
                );
                actions.appendChild(messageLink);
            }

            const challengeLink = this.makeActionLink(
                'icon icon-crossedswords',
                `/@/${encodeURIComponent(payload.username)}/challenge`,
                _('Challenge'),
                true,
            );
            actions.appendChild(challengeLink);

            if (payload.canFollow) {
                actions.appendChild(this.makeFollowButton(payload.username, payload.following === true));
            }
        }

        return actions.childElementCount > 0 ? actions : undefined;
    }

    private makeFollowButton(username: string, initiallyFollowing: boolean): HTMLAnchorElement {
        let following = initiallyFollowing;
        const button = document.createElement('a');
        button.className = 'umw-action-btn umw-follow-btn btn-rack__btn relation-button text icon icon-thumbs-o-up';
        button.href = `/api/${encodeURIComponent(username)}/follow`;
        const renderState = () => renderFollowButtonState(button, following);
        renderState();
        button.addEventListener('click', event => {
            event.preventDefault();
            const next = !following;
            const formData = new URLSearchParams({ follow: `${next}` });
            fetch(`/api/${encodeURIComponent(username)}/follow`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
                body: formData.toString(),
            })
                .then(res => {
                    if (!res.ok) return;
                    following = next;
                    renderState();
                })
                .catch(() => undefined);
        });
        return button;
    }

    private makeActionLink(
        className: string,
        href: string,
        text: string,
        iconOnly: boolean = false,
    ): HTMLAnchorElement {
        const link = document.createElement('a');
        link.className = `umw-action-btn btn-rack__btn ${className}`;
        if (iconOnly) link.classList.add('icon-only');
        link.href = href;
        link.title = text;
        link.setAttribute('aria-label', text);
        link.textContent = iconOnly ? '' : text;
        return link;
    }

    private clearLiveBoard() {
        this.disconnectOngoingSource();
        this.cg = undefined;
        this.liveGameId = undefined;
        this.liveVariantName = undefined;
    }

    private positionForAnchor(anchor: HTMLElement) {
        const rect = anchor.getBoundingClientRect();
        const spacing = 8;

        this.root.style.visibility = 'hidden';
        this.root.style.left = '0px';
        this.root.style.top = '0px';
        this.root.classList.remove('hidden');

        const widgetRect = this.root.getBoundingClientRect();
        const vw = window.innerWidth;
        const vh = window.innerHeight;

        // Profile game rows can rerender and detach the hovered link before positioning.
        // In that case, keep the widget near the pointer instead of defaulting near top-left.
        if (
            !anchor.isConnected ||
            !Number.isFinite(rect.left) ||
            !Number.isFinite(rect.top) ||
            (rect.left === 0 && rect.top === 0 && rect.width === 0 && rect.height === 0)
        ) {
            this.placeByPoint(this.lastMouseX, this.lastMouseY);
            return;
        }

        let left = rect.left + 24;
        if (left + widgetRect.width > vw - spacing) {
            left = vw - widgetRect.width - spacing;
        }
        if (left < spacing) left = spacing;

        let top = rect.bottom + spacing;
        if (top + widgetRect.height > vh - spacing) {
            top = rect.top - widgetRect.height - spacing;
        }
        if (top < spacing) top = spacing;

        this.root.style.left = `${Math.round(left)}px`;
        this.root.style.top = `${Math.round(top)}px`;
        this.root.style.visibility = 'visible';
    }
}

let miniWidget: UserMiniWidget | undefined;

export function initUserMiniWidget(assetURL: string, username: string, anon: string) {
    if (miniWidget) return;
    miniWidget = new UserMiniWidget(assetURL, username, anon === 'True' || anon === 'true');
    miniWidget.init();
}
