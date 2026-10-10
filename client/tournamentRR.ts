import { h, VNode } from 'snabbdom';

import { _ } from './i18n';
import { patch } from './document';
import { alertDialog } from './alertDialog';
import { confirmDialog } from './confirmDialog';
import { chatView, chatMessage, ChatController } from './chat';
import { timeago } from './datetime';
import { JSONObject, PyChessModel } from './types';
import { newWebsocket } from '@/socket/webSocketUtils';
import { displayUsername, userLink } from './user';
import { timeControlStr } from './view';
import { initializeClock, localeOptions, syncTournamentStartAlerts } from './tournamentClock';
import { tournamentLifecycleView } from './tournamentLifecycle';
import { roundRobinFaq } from './tournamentFaq';
import {
    MsgError,
    MsgGetGames,
    MsgGetPlayers,
    MsgPing,
    MsgRRArrangements,
    MsgRRManagement,
    MsgRRSettings,
    MsgTournamentStatus,
    TournamentManagePlayer,
    MsgUserConnectedTournament,
    MsgUserStatus,
    RRArrangementCell,
    TournamentGame,
    TournamentPlayer,
} from './tournamentType';
import { VARIANTS } from './variants';
import { sound } from './sound';
import { redirectFirst } from './tournamentAlerts';

type RRFlatpickrOptions = {
    enableTime: boolean;
    time_24hr: boolean;
    dateFormat: string;
    altInput: boolean;
    altFormat: string;
    inline?: boolean;
    minDate: string | Date;
    maxDate: Date;
    monthSelectorType: string;
    disableMobile: boolean;
    defaultDate?: string;
    onChange?: (selectedDates: Date[]) => void;
};

type FlatpickrInstance = {
    setDate: (date: Date | string, triggerChange?: boolean) => void;
    destroy: () => void;
};

type RRFlatpickrFunction = (element: HTMLElement, options: RRFlatpickrOptions) => FlatpickrInstance;

type FlatpickrElement = HTMLInputElement & {
    _flatpickr?: FlatpickrInstance;
};

const T_STATUS = {
    0: 'created',
    1: 'started',
    2: 'aborted',
    3: 'finished',
    4: 'archived',
} as const;

type RRViewMode = 'overview' | 'challenges' | 'manage';
type RRChallengeRow = {
    id: string;
    opponent: string;
    round: number;
    color: string;
    status: string;
    label: string;
    actionable: boolean;
    incoming: boolean;
    gameId: string;
    when: string;
};

type RRGameListRow = {
    id: string;
    white: string;
    black: string;
    status: string;
    gameId: string;
    date: string;
    scheduled: boolean;
};

const SCORE_SHIFT = 100000;

type RRSchedulePerspective = {
    mine: string;
    opponent: string;
    agreed: string;
};

type RRSummaryStats = Pick<MsgTournamentStatus, 'nbPlayers' | 'sumRating' | 'nbGames' | 'wWin' | 'bWin' | 'draw'>;

export class TournamentRRController implements ChatController {
    sock;
    tournamentId: string;
    username: string;
    anon: boolean;
    system = 1;
    variant = VARIANTS['chess'];
    chess960 = false;
    rated = '';
    tournamentStatus = 'created';
    userStatus = 'spectator';
    rounds = 0;
    startDate = '';
    secondsToStart = 0;
    secondsToFinish = 0;
    tournamentMinutes = 0;
    roundOngoingGames = 0;
    secondsToNextRound = 0;
    manualNextRoundPending = false;
    clockInterval: ReturnType<typeof setInterval> | null = null;
    players: TournamentPlayer[] = [];
    rrPlayers: string[] = [];
    matrix: Record<string, Record<string, RRArrangementCell>> = {};
    completedGames = 0;
    totalGames = 0;
    createdBy = '';
    approvalRequired = false;
    joiningClosed = false;
    pendingPlayers: TournamentManagePlayer[] = [];
    deniedPlayers: TournamentManagePlayer[] = [];
    page = 1;
    selectedPlayer = '';
    selectedGames: TournamentGame[] = [];
    podiumPlayers: TournamentPlayer[] = [];
    summaryStats: RRSummaryStats = { nbPlayers: 0, sumRating: 0, nbGames: 0, wWin: 0, bWin: 0, draw: 0 };
    viewMode: RRViewMode = 'overview';
    selectedArrangementId = '';
    hoveredRow = '';
    hoveredCol = '';
    kickUsername = '';
    scheduleDrafts: Record<string, string> = {};
    onlineByUsername: Record<string, boolean | undefined> = {};
    patronByUsername: Record<string, boolean | undefined> = {};
    flatpickrReady: Promise<void>;
    arrangementPresenceInterval: number | null = null;
    presenceArrangementId = '';
    openCalendarArrangementId = '';
    annulDeadlineTimer: number | null = null;
    clockdiv: VNode;
    action: VNode;
    descriptionNode: VNode;
    startsAtNode: VNode;
    systemNode: VNode;
    creatorNode: VNode;
    minutesNode: VNode;
    manageNode: VNode;
    lifecycleActions: VNode;
    bodyNode: VNode;
    modalNode: VNode;
    podiumNode: VNode;
    summaryNode: VNode;
    crossTableNode: VNode | null = null;
    gamesNode: VNode | null = null;
    boundHashChange: () => void;
    boundVisibilityChange: () => void;
    creatorCanManage: boolean;
    isTournamentDirector: boolean;

    constructor(_el: HTMLElement, model: PyChessModel) {
        this.tournamentId = model.tournamentId;
        this.username = model.username;
        this.creatorCanManage = model.tournamentmanager;
        this.isTournamentDirector = model.tournamentDirector;
        this.anon = model.anon === 'True';
        this.variant = VARIANTS[model.variant];
        this.chess960 = model.chess960 === 'True';
        this.rated = model.rated;
        this.rounds = model.rounds || 0;
        this.startDate = model.date;
        this.tournamentStatus = T_STATUS[model.status as keyof typeof T_STATUS];
        this.selectedArrangementId = decodeURIComponent(window.location.hash.replace(/^#/, ''));
        this.boundHashChange = () => this.syncArrangementFromHash();
        this.boundVisibilityChange = () => {
            if (document.visibilityState === 'visible') this.loadArrangementOnlineStatus();
        };
        this.flatpickrReady = this.ensureFlatpickrLoaded();

        this.sock = newWebsocket('wst');
        this.sock.onopen = () => {
            this.doSend({
                type: 'tournament_user_connected',
                tournamentId: this.tournamentId,
                username: this.username,
            });
            this.doSend({ type: 'get_players', tournamentId: this.tournamentId, page: this.page });
        };
        this.sock.onmessage = (e: MessageEvent) => this.onMessage(e);

        patch(document.getElementById('lobbychat') as HTMLElement, chatView(this, 'lobbychat'));
        this.lifecycleActions = patch(
            document.getElementById('tournament-lifecycle') as HTMLElement,
            this.renderLifecycleActions(),
        );
        this.descriptionNode = patch(
            document.getElementById('description') as HTMLElement,
            h('div#description.description'),
        );
        this.startsAtNode = patch(document.getElementById('startsAt') as HTMLElement, h('div#startsAt'));
        this.systemNode = patch(document.getElementById('tsystem') as HTMLElement, h('div#tsystem'));
        this.creatorNode = patch(document.getElementById('createdBy') as HTMLElement, h('div#createdBy'));
        this.minutesNode = patch(document.getElementById('tminutes') as HTMLElement, h('span#tminutes'));
        this.manageNode = patch(document.getElementById('rr-manage') as HTMLElement, h('div#rr-manage'));
        this.clockdiv = patch(document.getElementById('clockdiv') as HTMLElement, h('div#clockdiv'));
        this.action = patch(document.getElementById('action') as HTMLElement, h('div#action'));
        this.bodyNode = patch(document.getElementById('rr-body') as HTMLElement, h('div#rr-body'));
        this.modalNode = patch(document.getElementById('rr-modal') as HTMLElement, h('div#rr-modal'));
        this.podiumNode = patch(document.getElementById('podium') as HTMLElement, h('div#podium'));
        this.summaryNode = patch(document.getElementById('summarybox') as HTMLElement, h('div#summarybox'));
        patch(document.querySelector('div.tour-faq') as HTMLElement, roundRobinFaq(this.rated));
        window.addEventListener('hashchange', this.boundHashChange);
        document.addEventListener('visibilitychange', this.boundVisibilityChange);
    }

    doSend(message: JSONObject) {
        this.sock.send(JSON.stringify(message));
    }

    renderLifecycleActions() {
        return tournamentLifecycleView(
            {
                status: this.tournamentStatus,
                system: this.system,
                manualNextRoundPending: this.manualNextRoundPending,
                creatorCanManage: this.creatorCanManage,
                isDirector: this.isTournamentDirector,
            },
            () => this.doSend({ type: 'start_next_round', tournamentId: this.tournamentId }),
        );
    }

    updateLifecycleActions() {
        this.lifecycleActions = patch(this.lifecycleActions, this.renderLifecycleActions());
    }

    isHost() {
        return this.username === this.createdBy;
    }

    canManage() {
        return this.creatorCanManage;
    }

    canAnnulResults() {
        return this.creatorCanManage || this.isTournamentDirector;
    }

    annulReplayAvailable() {
        if (!['created', 'started'].includes(this.tournamentStatus)) return false;
        const deadline = this.scheduleMaxDate().getTime();
        return Number.isFinite(deadline) && Date.now() < deadline;
    }

    syncAnnulDeadlineTimer() {
        if (this.annulDeadlineTimer !== null) {
            window.clearTimeout(this.annulDeadlineTimer);
            this.annulDeadlineTimer = null;
        }
        if (!this.canAnnulResults() || !this.annulReplayAvailable()) return;

        const deadline = this.scheduleMaxDate().getTime();
        const remaining = deadline - Date.now();
        const maxTimeout = 2_147_000_000;
        this.annulDeadlineTimer = window.setTimeout(
            () => {
                this.annulDeadlineTimer = null;
                if (Date.now() < deadline) {
                    this.syncAnnulDeadlineTimer();
                    return;
                }
                this.renderModal();
            },
            Math.min(remaining + 50, maxTimeout),
        );
    }

    async annulArrangementGame(cell: RRArrangementCell) {
        if (!cell.gameId || !this.canAnnulResults() || !this.annulReplayAvailable()) return;
        const confirmed = await confirmDialog({
            title: _('Annul result'),
            text: _('This removes the tournament result and reopens the pairing for a replay. The original game remains in the pairing history.'),
            confirmText: _('Annul result'),
            danger: true,
        });
        if (!confirmed) return;
        this.doSend({
            type: 'rr_annul_game',
            tournamentId: this.tournamentId,
            arrangementId: cell.id,
            gameId: cell.gameId,
        });
    }

    playerByName(name: string) {
        return this.players.find(player => player.name === name);
    }

    login() {
        window.location.assign('/login');
    }

    join() {
        this.doSend({ type: 'join', tournamentId: this.tournamentId });
    }

    withdraw() {
        this.doSend({ type: 'withdraw', tournamentId: this.tournamentId });
    }

    setViewMode(viewMode: RRViewMode) {
        this.viewMode = viewMode;
        this.updateActionButton();
        this.renderManageButton();
        this.renderBody();
    }

    setHovered(row: string, col: string) {
        if (this.hoveredRow === row && this.hoveredCol === col) return;
        this.hoveredRow = row;
        this.hoveredCol = col;
        this.renderCrossTable();
    }

    setHoveredRow(row: string) {
        if (this.hoveredRow === row && this.hoveredCol === '') return;
        this.hoveredRow = row;
        this.hoveredCol = '';
        this.renderCrossTable();
    }

    setHoveredCol(col: string) {
        if (this.hoveredRow === '' && this.hoveredCol === col) return;
        this.hoveredRow = '';
        this.hoveredCol = col;
        this.renderCrossTable();
    }

    clearHovered() {
        if (!this.hoveredRow && !this.hoveredCol) return;
        this.hoveredRow = '';
        this.hoveredCol = '';
        this.renderCrossTable();
    }

    selectedArrangement(): RRArrangementCell | undefined {
        for (const row of Object.values(this.matrix)) {
            for (const cell of Object.values(row)) {
                if (cell.id === this.selectedArrangementId) return cell;
            }
        }
        return undefined;
    }

    syncArrangementFromHash() {
        const arrangementId = decodeURIComponent(window.location.hash.replace(/^#/, ''));
        if (this.selectedArrangementId === arrangementId) return;
        this.selectedArrangementId = arrangementId;
        this.renderModal();
        this.renderCrossTable();
    }

    selectArrangement(cell: RRArrangementCell) {
        this.selectedArrangementId = cell.id;
        window.history.replaceState(null, '', `#${encodeURIComponent(cell.id)}`);
        this.renderModal();
        this.renderCrossTable();
    }

    closeArrangement() {
        if (this.selectedArrangementId === '') return;
        this.selectedArrangementId = '';
        this.openCalendarArrangementId = '';
        const url = new URL(window.location.href);
        url.hash = '';
        window.history.replaceState(null, '', url.toString());
        this.stopArrangementPresencePolling();
        this.renderModal();
        this.renderCrossTable();
    }

    async ensureFlatpickrLoaded(): Promise<void> {
        if (typeof this.flatpickrFunction() === 'function') return;

        const cssId = 'rr-flatpickr-css';
        if (!document.getElementById(cssId)) {
            const link = document.createElement('link');
            link.id = cssId;
            link.rel = 'stylesheet';
            link.href = 'https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css';
            document.head.appendChild(link);
        }

        await new Promise<void>((resolve, reject) => {
            const existing = document.getElementById('rr-flatpickr-script') as HTMLScriptElement | null;
            if (existing) {
                existing.addEventListener('load', () => resolve(), { once: true });
                existing.addEventListener('error', () => reject(new Error('flatpickr load failed')), { once: true });
                if (typeof this.flatpickrFunction() === 'function') resolve();
                return;
            }

            const script = document.createElement('script');
            script.id = 'rr-flatpickr-script';
            script.src = 'https://cdn.jsdelivr.net/npm/flatpickr';
            script.onload = () => resolve();
            script.onerror = () => reject(new Error('flatpickr load failed'));
            document.head.appendChild(script);
        }).catch(() => undefined);
    }

    flatpickrFunction(): RRFlatpickrFunction | undefined {
        return (window as Window & { flatpickr?: RRFlatpickrFunction }).flatpickr;
    }

    schedulePerspective(cell: RRArrangementCell): RRSchedulePerspective {
        const isWhite = cell.white === this.username;
        return {
            mine: isWhite ? cell.whiteSuggestedAt : cell.blackSuggestedAt,
            opponent: isWhite ? cell.blackSuggestedAt : cell.whiteSuggestedAt,
            agreed: cell.scheduledAt,
        };
    }

    defaultScheduleDraft(cell: RRArrangementCell): string {
        const perspective = this.schedulePerspective(cell);
        const source = perspective.mine || perspective.agreed || perspective.opponent;
        if (!source) return '';
        const date = new Date(source);
        date.setSeconds(0, 0);
        const adjusted = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
        return adjusted.toISOString().slice(0, 16);
    }

    scheduleDraft(cell: RRArrangementCell): string {
        const existing = this.scheduleDrafts[cell.id];
        if (existing !== undefined) return existing;
        const draft = this.defaultScheduleDraft(cell);
        this.scheduleDrafts[cell.id] = draft;
        return draft;
    }

    setScheduleDraft(arrangementId: string, value: string) {
        this.scheduleDrafts[arrangementId] = value;
    }

    localDateInputValue(date: Date): string {
        const normalized = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
        return normalized.toISOString().slice(0, 16);
    }

    scheduleMaxDate(): Date {
        const startsAt = new Date(this.startDate);
        if (!Number.isNaN(startsAt.getTime()) && this.tournamentMinutes > 0) {
            return new Date(startsAt.getTime() + this.tournamentMinutes * 60 * 1000);
        }
        if (this.secondsToFinish > 0) return new Date(Date.now() + this.secondsToFinish * 1000);
        return new Date();
    }

    submitSchedule(cell: RRArrangementCell, value: string) {
        if (!value) {
            this.doSend({ type: 'rr_set_time', tournamentId: this.tournamentId, arrangementId: cell.id });
            return;
        }
        const parsed = new Date(value);
        this.doSend({
            type: 'rr_set_time',
            tournamentId: this.tournamentId,
            arrangementId: cell.id,
            date: parsed.toISOString(),
        });
    }

    playerOnline(username: string): boolean | undefined {
        return this.onlineByUsername[username];
    }

    playerPatron(username: string): boolean | undefined {
        return this.patronByUsername[username];
    }

    async loadArrangementOnlineStatus() {
        const cell = this.selectedArrangement();
        if (!cell) return;
        try {
            const response = await fetch(
                `/api/users/status?ids=${encodeURIComponent(cell.white)},${encodeURIComponent(cell.black)}`,
            );
            if (!response.ok) return;
            const payload = (await response.json()) as Array<{ id: string; online?: boolean; patron?: boolean }>;
            payload.forEach(entry => {
                this.onlineByUsername[entry.id] = entry.online;
                this.patronByUsername[entry.id] = entry.patron;
            });
            this.renderModal();
        } catch {
            return;
        }
    }

    startArrangementPresencePolling(cell: RRArrangementCell) {
        if (this.presenceArrangementId === cell.id && this.arrangementPresenceInterval !== null) return;
        this.stopArrangementPresencePolling();
        this.presenceArrangementId = cell.id;
        void this.loadArrangementOnlineStatus();
        this.arrangementPresenceInterval = window.setInterval(() => {
            void this.loadArrangementOnlineStatus();
        }, 35000);
    }

    stopArrangementPresencePolling() {
        this.presenceArrangementId = '';
        if (this.arrangementPresenceInterval !== null) {
            window.clearInterval(this.arrangementPresenceInterval);
            this.arrangementPresenceInterval = null;
        }
    }

    updateActionButton() {
        let button = h('div#action');
        if (this.viewMode === 'manage') {
            button = h(
                'button#action',
                {
                    on: { click: () => this.setViewMode('overview') },
                    class: { icon: true, 'icon-step-backward': true },
                },
                _('Back'),
            );
        } else if (this.anon && 'created|started'.includes(this.tournamentStatus)) {
            button = h(
                'button#action',
                { on: { click: () => this.login() }, class: { icon: true, 'icon-play': true } },
                _('LOG IN'),
            );
        } else if (this.tournamentStatus === 'created') {
            if (this.userStatus === 'pending') {
                button = h('div#action.pending-note', _('JOIN REQUEST PENDING'));
            } else if (this.userStatus === 'denied') {
                button = h('div#action.pending-note', _('JOIN REQUEST DENIED'));
            } else if (this.userStatus === 'joined') {
                button = h(
                    'button#action',
                    { on: { click: () => this.withdraw() }, class: { icon: true, 'icon-flag-o': true } },
                    _('WITHDRAW'),
                );
            } else if (this.joiningClosed && !this.isHost()) {
                button = h('div#action.pending-note', _('JOINING CLOSED'));
            } else {
                button = h(
                    'button#action',
                    { on: { click: () => this.join() }, class: { icon: true, 'icon-play': true } },
                    _('JOIN'),
                );
            }
        } else if (this.tournamentStatus === 'started') {
            if ('spectator|paused|withdrawn|denied|pending'.includes(this.userStatus)) {
                button = h(
                    'button#action',
                    { on: { click: () => this.join() }, class: { icon: true, 'icon-play': true } },
                    _('JOIN'),
                );
            } else {
                button = h(
                    'button#action',
                    { on: { click: () => this.withdraw() }, class: { icon: true, 'icon-flag-o': true } },
                    _('WITHDRAW'),
                );
            }
        }
        this.action = patch(this.action, button);
    }

    renderInfo(msg: MsgUserConnectedTournament) {
        this.startDate = msg.startsAt;
        this.tournamentMinutes = msg.tminutes;
        this.createdBy = msg.createdBy;
        this.approvalRequired = !!msg.rrRequiresApproval;
        this.joiningClosed = !!msg.rrJoiningClosed;
        this.descriptionNode = patch(this.descriptionNode, h('div#description.description', msg.description));
        const startsAtDate = new Date(msg.startsAt);
        const endsAtDate = new Date(startsAtDate.getTime() + msg.tminutes * 60 * 1000);
        this.startsAtNode = patch(
            this.startsAtNode,
            h(
                'div#startsAt',
                `${startsAtDate.toLocaleString('default', localeOptions)} - ${endsAtDate.toLocaleString('default', localeOptions)}`,
            ),
        );
        this.systemNode = patch(
            this.systemNode,
            h('div#tsystem', `${this.rated === 'True' ? _('Rated') : _('Unrated')} - ${_('Round-Robin')}`),
        );
        this.creatorNode = patch(
            this.creatorNode,
            h('div#createdBy', [h('strong', _('By')), ' ', userLink(msg.createdBy, [displayUsername(msg.createdBy)])]),
        );
        this.minutesNode = patch(this.minutesNode, h('span#tminutes', ` • ${msg.tminutes}m`));
        this.secondsToStart = msg.secondsToStart;
        this.secondsToFinish = msg.secondsToFinish;
        initializeClock(this as any);
        this.updateActionButton();
        this.renderManageButton();
        this.renderBody();
        this.renderModal();
        this.syncAnnulDeadlineTimer();
    }

    gameListRows(): RRGameListRow[] {
        const rows: RRGameListRow[] = [];
        const seen = new Set<string>();
        const order = this.rrPlayers.length > 0 ? this.rrPlayers : this.players.map(player => player.name);
        for (const player of order) {
            const row = this.matrix[player] || {};
            for (const cell of Object.values(row)) {
                if (!cell.id || seen.has(cell.id)) continue;
                seen.add(cell.id);
                if (cell.status === 'pending' && !cell.gameId && !cell.scheduledAt) continue;
                rows.push({
                    id: cell.id,
                    white: cell.white,
                    black: cell.black,
                    status: cell.status,
                    gameId: cell.gameId,
                    date: cell.scheduledAt || cell.date,
                    scheduled: !!cell.scheduledAt,
                });
            }
        }
        return rows.sort((left, right) => {
            const leftTime = Date.parse(left.date);
            const rightTime = Date.parse(right.date);
            if (!Number.isNaN(leftTime) && !Number.isNaN(rightTime) && leftTime !== rightTime) {
                return leftTime - rightTime;
            }
            return left.id.localeCompare(right.id);
        });
    }

    gameListStatus(row: RRGameListRow): string {
        if (row.gameId && row.status === 'finished') return _('Finished');
        if (row.gameId || row.status === 'started') return _('Current game');
        if (row.scheduled) return _('Scheduled');
        if (row.status === 'challenged') return _('Challenge');
        if (row.status === 'expired') return _('Not played');
        return row.status;
    }

    gamesVNode() {
        const rows = this.gameListRows().map(row => {
            const target = this.findArrangementById(row.id);
            const icon = row.gameId && row.status === 'finished' ? '●' : '◌';
            return h(
                'tr',
                {
                    class: {
                        actionable: !!target,
                        ongoing: !!row.gameId && row.status !== 'finished',
                        finished: row.status === 'finished',
                    },
                    on: {
                        click: () => {
                            if (row.gameId) {
                                window.location.assign('/' + row.gameId);
                            } else if (target) {
                                this.selectArrangement(target);
                            }
                        },
                    },
                },
                [
                    h('td.icon-col', icon),
                    h('td.matchup', [
                        userLink(row.white, [displayUsername(row.white)]),
                        ' vs ',
                        userLink(row.black, [displayUsername(row.black)]),
                    ]),
                    h('td.status-col', this.gameListStatus(row)),
                    h(
                        'td.time-col',
                        row.date ? h('info-date', { attrs: { timestamp: row.date } }, timeago(row.date)) : '',
                    ),
                ],
            );
        });
        return h('table#games.box.pairings', [
            h('thead', h('tr', [h('th'), h('th', _('Games')), h('th', _('Status')), h('th', _('When'))])),
            h('tbody', rows),
        ]);
    }

    renderGames() {
        this.renderBody();
    }

    selectPlayer(player: string) {
        this.selectedPlayer = player;
        this.renderCrossTable();
        this.doSend({ type: 'get_games', tournamentId: this.tournamentId, player });
    }

    cellDisplay(cell: RRArrangementCell): string {
        if (cell.points !== undefined && cell.points !== null && cell.points !== '') {
            return `${cell.points}`;
        }
        const anyCell = cell as RRArrangementCell & { result?: string };
        if (anyCell.result) {
            if (anyCell.result === '1/2-1/2') return '½';
            const rowIsWhite = cell.color === 'white';
            if (anyCell.result === '1-0') return rowIsWhite ? '1' : '0';
            if (anyCell.result === '0-1') return rowIsWhite ? '0' : '1';
        }
        if (cell.status === 'started') return '...';
        if (cell.status === 'challenged') return cell.challenger === this.username ? '!' : '?';
        if (cell.status === 'expired') return '-';
        return '';
    }

    arrangementAction(cell: RRArrangementCell) {
        if (cell.gameId) {
            window.location.assign('/' + cell.gameId);
            return;
        }
        if (![cell.white, cell.black].includes(this.username)) return;
        if (cell.status === 'challenged' && cell.challenger !== this.username) {
            this.doSend({ type: 'rr_accept_challenge', tournamentId: this.tournamentId, arrangementId: cell.id });
            return;
        }
        if (cell.status === 'pending') {
            this.doSend({ type: 'rr_challenge', tournamentId: this.tournamentId, arrangementId: cell.id });
        }
    }

    challengeRows(): RRChallengeRow[] {
        const rows: RRChallengeRow[] = [];
        const seen = new Set<string>();
        const order = this.rrPlayers.length > 0 ? this.rrPlayers : this.players.map(player => player.name);
        for (const player of order) {
            const row = this.matrix[player] || {};
            for (const cell of Object.values(row)) {
                if (!cell.id || seen.has(cell.id)) continue;
                seen.add(cell.id);
                const canAct = [cell.white, cell.black].includes(this.username);
                const isVisible = ['challenged', 'started'].includes(cell.status) || cell.gameId !== '';
                if (!isVisible && !(canAct && cell.status === 'pending')) continue;
                const opponent = canAct
                    ? cell.white === this.username
                        ? cell.black
                        : cell.white
                    : `${cell.white} vs ${cell.black}`;
                const incoming = canAct && cell.status === 'challenged' && cell.challenger !== this.username;
                const color = canAct ? (cell.white === this.username ? 'white' : 'black') : ' ';
                let label = _('Waiting');
                if (cell.gameId) label = _('Open game');
                else if (cell.scheduledAt && cell.status === 'pending') label = _('Create challenge');
                else if (cell.status === 'pending') label = _('Create challenge');
                else if (incoming) label = _('Accept challenge');
                else if (cell.status === 'challenged') label = _('Awaiting response');
                else if (cell.status === 'started') label = _('Game in progress');
                rows.push({
                    id: cell.id,
                    opponent,
                    round: cell.round,
                    color,
                    status: cell.status,
                    label,
                    actionable: cell.gameId !== '' || (canAct && (cell.status === 'pending' || incoming)),
                    incoming,
                    gameId: cell.gameId,
                    when: cell.scheduledAt || cell.date,
                });
            }
        }
        return rows.sort((left, right) => {
            if (left.incoming !== right.incoming) return left.incoming ? -1 : 1;
            const leftTime = Date.parse(left.when);
            const rightTime = Date.parse(right.when);
            if (!Number.isNaN(leftTime) && !Number.isNaN(rightTime) && leftTime !== rightTime) {
                return leftTime - rightTime;
            }
            return left.round - right.round;
        });
    }

    renderCrossTable() {
        const order = this.rrPlayers.length > 0 ? this.rrPlayers : this.players.map(player => player.name);
        const rowHoverHandlers = (rowPlayer: string) => ({
            mouseenter: () => this.setHoveredRow(rowPlayer),
            mouseleave: () => this.clearHovered(),
        });
        const colHoverHandlers = (colPlayer: string) => ({
            mouseenter: () => this.setHoveredCol(colPlayer),
            mouseleave: () => this.clearHovered(),
        });
        const cellHoverHandlers = (rowPlayer: string, colPlayer: string) => ({
            mouseenter: () => this.setHovered(rowPlayer, colPlayer),
            mouseleave: () => this.clearHovered(),
        });
        const rows = order.map((rowPlayer, rowIndex) => {
            const rowPlayerData = this.playerByName(rowPlayer);
            return h(
                'tr',
                {
                    class: {
                        hovered: this.hoveredRow === rowPlayer,
                        'selected-player': this.selectedPlayer === rowPlayer,
                        selectable: true,
                        withdrawn: !!rowPlayerData?.withdrawn,
                    },
                    on: {
                        click: () => this.selectPlayer(rowPlayer),
                        ...rowHoverHandlers(rowPlayer),
                    },
                },
                [
                    h('th', { on: rowHoverHandlers(rowPlayer) }, `${rowIndex + 1}`),
                    h(
                        'th',
                        { on: rowHoverHandlers(rowPlayer) },
                        userLink(rowPlayer, [
                            rowPlayerData?.withdrawn ? h('span.rr-player-state', '• ') : '',
                            displayUsername(rowPlayer),
                        ]),
                    ),
                ],
            );
        });

        const arrangementRows = order.map(rowPlayer =>
            h(
                'tr',
                {
                    class: {
                        hovered: this.hoveredRow === rowPlayer,
                        withdrawn: !!this.playerByName(rowPlayer)?.withdrawn,
                    },
                    on: rowHoverHandlers(rowPlayer),
                },
                order.map(colPlayer => {
                    const cell = this.matrix[rowPlayer]?.[colPlayer];
                    if (rowPlayer === colPlayer)
                        return h('td.rr-cell.rr-self', {
                            class: {
                                hovered: this.hoveredRow === rowPlayer || this.hoveredCol === colPlayer,
                            },
                            on: cellHoverHandlers(rowPlayer, colPlayer),
                        });
                    const isMe = !!cell && [cell.white, cell.black].includes(this.username);
                    const display = cell ? this.cellDisplay(cell) : '';
                    const rowIsWhite = cell?.color === 'white';
                    const drawResult = cell?.result === '1/2-1/2';
                    const winResult =
                        !!cell && ((cell.result === '1-0' && rowIsWhite) || (cell.result === '0-1' && !rowIsWhite));
                    const lossResult =
                        !!cell && ((cell.result === '1-0' && !rowIsWhite) || (cell.result === '0-1' && rowIsWhite));
                    const isSelected = this.selectedArrangementId !== '' && cell?.id === this.selectedArrangementId;
                    return h(
                        'td.rr-cell',
                        {
                            attrs: {
                                title: cell ? `${rowPlayer} vs ${colPlayer}` : '',
                            },
                            class: {
                                actionable: !!cell && isMe,
                                hovered: this.hoveredRow === rowPlayer || this.hoveredCol === colPlayer,
                                selected: isSelected,
                                pending: cell?.status === 'pending',
                                challenged: cell?.status === 'challenged',
                                incoming: cell?.status === 'challenged' && cell?.challenger !== this.username,
                                outgoing: cell?.status === 'challenged' && cell?.challenger === this.username,
                                started: cell?.status === 'started',
                                draw: drawResult,
                                win: winResult,
                                loss: lossResult,
                                empty: !cell,
                            },
                            on: cell
                                ? {
                                      click: () => this.selectArrangement(cell),
                                      ...cellHoverHandlers(rowPlayer, colPlayer),
                                  }
                                : cellHoverHandlers(rowPlayer, colPlayer),
                        },
                        display !== '' ? h('div', display) : '',
                    );
                }),
            ),
        );

        const scoreRows = order.map(playerName => {
            const player = this.playerByName(playerName);
            const playerScore = player ? Math.trunc(player.score / SCORE_SHIFT) : 0;
            const maxScore = Math.max(0, ...this.players.map(entry => Math.trunc(entry.score / SCORE_SHIFT)));
            return h(
                'tr',
                {
                    class: {
                        hovered: this.hoveredRow === playerName,
                        'selected-player': this.selectedPlayer === playerName,
                        withdrawn: !!player?.withdrawn,
                    },
                    on: rowHoverHandlers(playerName),
                },
                [
                    h(
                        'td',
                        {
                            class: {
                                me: playerName === this.username,
                                winner: !!player && playerScore === maxScore && maxScore > 0,
                            },
                            on: rowHoverHandlers(playerName),
                        },
                        `${playerScore}`,
                    ),
                ],
            );
        });

        if (this.crossTableNode === null) return;
        this.crossTableNode = patch(
            this.crossTableNode,
            h('div#rr-crosstable.r-table-wrap', [
                h('div.r-table-wrap-players', [
                    h('table', [h('thead', h('tr', [h('th', '#'), h('th', _('Player'))])), h('tbody', rows)]),
                ]),
                h('div.r-table-wrap-arrs', [
                    h('table', [
                        h(
                            'thead',
                            h(
                                'tr',
                                order.map((playerName, index) =>
                                    h(
                                        'th',
                                        {
                                            class: {
                                                hovered: this.hoveredCol === playerName,
                                                me: playerName === this.username,
                                            },
                                            on: colHoverHandlers(playerName),
                                        },
                                        `${index + 1}`,
                                    ),
                                ),
                            ),
                        ),
                        h('tbody', arrangementRows),
                    ]),
                ]),
                h('div.r-table-wrap-scores', [
                    h('table', [h('thead', h('tr', [h('th', 'Σ')])), h('tbody', scoreRows)]),
                ]),
            ]),
        );
    }

    renderManageButton() {
        if (!this.canManage()) {
            this.manageNode = patch(this.manageNode, h('div#rr-manage'));
            return;
        }
        this.manageNode = patch(
            this.manageNode,
            h('div#rr-manage', [
                h(
                    `button.button.manage-players.button-primary${this.viewMode === 'manage' ? '.active' : ''}`,
                    {
                        on: {
                            click: () => this.setViewMode(this.viewMode === 'manage' ? 'overview' : 'manage'),
                        },
                    },
                    _('Manage players'),
                ),
            ]),
        );
    }

    viewNavVNode() {
        const nav = [
            ['overview', _('Games')],
            ['challenges', _('Challenges')],
        ] as Array<[RRViewMode, string]>;
        return h(
            'div#rr-nav',
            {
                attrs: {
                    role: 'tablist',
                    'aria-label': _('Round-robin views'),
                },
            },
            nav.map(([mode, label], idx) =>
                h(
                    'span',
                    {
                        attrs: {
                            role: 'tab',
                            id: `rr-tab-${mode}`,
                            'aria-selected': this.viewMode === mode ? 'true' : 'false',
                            'aria-controls': `rr-panel-${mode}`,
                            tabindex: this.viewMode === mode ? '0' : '-1',
                        },
                        on: { click: () => this.setViewMode(mode) },
                        hook: {
                            insert: vnode => {
                                const el = vnode.elm as HTMLElement | undefined;
                                if (!el) return;
                                el.onkeydown = (e: KeyboardEvent) => {
                                    if (e.key === 'Enter' || e.key === ' ') {
                                        e.preventDefault();
                                        this.setViewMode(mode);
                                    }
                                    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                                        e.preventDefault();
                                        const nextMode =
                                            nav[(idx + (e.key === 'ArrowRight' ? 1 : nav.length - 1)) % nav.length][0];
                                        this.setViewMode(nextMode);
                                    }
                                };
                            },
                        },
                    },
                    label,
                ),
            ),
        );
    }

    scheduleCalendarOpen(cell: RRArrangementCell) {
        return this.openCalendarArrangementId === cell.id;
    }

    openScheduleCalendar(cell: RRArrangementCell) {
        if (this.scheduleCalendarOpen(cell)) return;
        this.openCalendarArrangementId = cell.id;
        this.renderModal();
        window.requestAnimationFrame(() => {
            document.querySelector('.rr-arr-user-bottom')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    }

    closeScheduleCalendar(cell: RRArrangementCell) {
        if (!this.scheduleCalendarOpen(cell)) return;
        this.openCalendarArrangementId = '';
        this.renderModal();
    }

    formatDateTime(dateLike: string | Date): string {
        return new Date(dateLike).toLocaleString('default', localeOptions);
    }

    formatArrangementDate(dateText: string): VNode {
        if (!dateText) return h('span.date', '-');
        const date = new Date(dateText);
        return h(
            'span.date',
            {
                attrs: {
                    title: date.toUTCString(),
                },
            },
            this.formatDateTime(date),
        );
    }

    modalPlayerLink(username: string): VNode {
        const player = this.playerByName(username);
        const online = !!this.playerOnline(username);
        const patron = !!this.playerPatron(username);
        return h('div.rr-arr-player-link', [
            h('i-side', {
                class: {
                    icon: true,
                    online,
                    offline: !online,
                    'icon-online': online && !patron,
                    'icon-offline': !online && !patron,
                    'icon-patron-wing': patron,
                },
                attrs: patron ? { title: _('PyChess Patron') } : {},
            }),
            userLink(
                username,
                [
                    player?.title ? h('player-title', `${player.title} `) : '',
                    displayUsername(username),
                    player?.title !== 'BOT' && player?.rating ? ` (${player.rating})` : '',
                ],
                { className: 'user-link' },
            ),
        ]);
    }

    modalPlayerColors(cell: RRArrangementCell, username: string): VNode {
        const color = username === cell.white ? _('White') : _('Black');
        return h(`div.rr-arr-color-icon.${username === cell.white ? 'white' : 'black'}`, { attrs: { title: color } });
    }

    modalActionButton(cell: RRArrangementCell): VNode | null {
        const canAct = [cell.white, cell.black].includes(this.username);
        if (cell.gameId) {
            return h('a.button.fbt.go-to-game', { attrs: { href: `/${cell.gameId}` } }, _('Open game'));
        }
        if (this.tournamentStatus === 'finished' || !canAct) return null;
        if (!['pending', 'challenged'].includes(cell.status)) return null;
        let label = _('Create challenge');
        let title = _('Create challenge');
        let ready = false;
        if (cell.status === 'challenged') {
            ready = true;
            if (cell.challenger === this.username) {
                label = _('View challenge');
                title = _('View challenge');
            } else {
                label = _('Accept challenge');
                title = _('Accept challenge');
            }
        }
        return h(
            'button.button.fbt',
            {
                class: {
                    ready,
                },
                attrs: {
                    title,
                },
                on: {
                    click: () => this.arrangementAction(cell),
                },
            },
            h('span', label),
        );
    }

    modalAnnulButton(cell: RRArrangementCell): VNode | null {
        if (!this.canAnnulResults() || !this.annulReplayAvailable()) return null;
        if (cell.status !== 'finished' || !cell.gameId) return null;
        return h(
            'button.button.button-red',
            {
                attrs: { title: _('Annul result and replay') },
                on: { click: () => void this.annulArrangementGame(cell) },
            },
            _('Annul result'),
        );
    }

    modalPlayerAction(cell: RRArrangementCell, username: string): VNode | null {
        const canAct = [cell.white, cell.black].includes(this.username);
        if (!canAct || cell.gameId || ['started', 'finished', 'expired'].includes(cell.status)) return null;
        const perspective = this.schedulePerspective(cell);
        const mine = username === this.username;
        const suggestedAt = mine ? perspective.mine : perspective.opponent;
        const draft = this.scheduleDraft(cell);
        if (!mine) {
            return h('div.suggested-time-wrap', [
                h('input.disabled', {
                    key: suggestedAt || '',
                    attrs: {
                        title: _('Suggested time'),
                        disabled: true,
                        placeholder: _('Suggested time'),
                    },
                    hook: {
                        insert: vnode => {
                            const input = vnode.elm as HTMLInputElement;
                            input.value = suggestedAt ? this.formatDateTime(suggestedAt) : '';
                        },
                        update: (oldVnode, vnode) => {
                            if (oldVnode.key === vnode.key) return;
                            const input = vnode.elm as HTMLInputElement;
                            input.value = suggestedAt ? this.formatDateTime(suggestedAt) : '';
                        },
                    },
                }),
                h(
                    'button.fbt',
                    {
                        attrs: {
                            disabled: !suggestedAt,
                            title: _('Accept suggested time'),
                        },
                        on: {
                            click: () => {
                                if (!suggestedAt) return;
                                const acceptedDraft = this.defaultScheduleDraft({
                                    ...cell,
                                    whiteSuggestedAt:
                                        cell.white === this.username ? suggestedAt : cell.whiteSuggestedAt,
                                    blackSuggestedAt:
                                        cell.black === this.username ? suggestedAt : cell.blackSuggestedAt,
                                });
                                this.setScheduleDraft(cell.id, acceptedDraft);
                                this.submitSchedule(cell, acceptedDraft);
                            },
                        },
                    },
                    _('Accept'),
                ),
            ]);
        }

        return h(
            'div.suggested-time-wrap',
            {
                class: {
                    'hide-calendar': !this.scheduleCalendarOpen(cell),
                },
            },
            [
                h(
                    'div.flatpickr-input-wrap',
                    {
                        on: {
                            click: () => this.openScheduleCalendar(cell),
                        },
                    },
                    [
                        h('input.flatpickr', {
                            key: perspective.mine || perspective.agreed || '',
                            attrs: {
                                title: perspective.mine ? _('Suggest different time') : _('Suggested time'),
                                placeholder: _('Suggest time'),
                            },
                            hook: {
                                insert: vnode => {
                                    const input = vnode.elm as FlatpickrElement;
                                    this.flatpickrReady
                                        .then(() => {
                                            const flatpickr = this.flatpickrFunction();
                                            if (typeof flatpickr !== 'function') {
                                                input.value = perspective.mine
                                                    ? this.formatDateTime(perspective.mine)
                                                    : '';
                                                return;
                                            }
                                            input._flatpickr?.destroy();
                                            input._flatpickr = flatpickr(input, {
                                                enableTime: true,
                                                time_24hr: true,
                                                dateFormat: 'Z',
                                                altInput: true,
                                                altFormat: 'Y-m-d H:i',
                                                inline: true,
                                                minDate: new Date(),
                                                maxDate: this.scheduleMaxDate(),
                                                monthSelectorType: 'static',
                                                disableMobile: true,
                                                defaultDate: draft ? new Date(draft).toISOString() : undefined,
                                                onChange: selectedDates => {
                                                    const selected = selectedDates[0];
                                                    this.setScheduleDraft(
                                                        cell.id,
                                                        selected ? this.localDateInputValue(selected) : '',
                                                    );
                                                },
                                            });
                                            if (perspective.mine) {
                                                const scheduledDate = new Date(perspective.mine);
                                                input._flatpickr.setDate(scheduledDate, false);
                                            }
                                        })
                                        .catch(() => undefined);
                                },
                                update: (oldVnode, vnode) => {
                                    const input = vnode.elm as FlatpickrElement;
                                    if (!input._flatpickr) return;
                                    if (oldVnode.key === vnode.key && this.scheduleDraft(cell) === draft) return;
                                    if (draft) input._flatpickr.setDate(new Date(draft), false);
                                },
                                destroy: vnode => {
                                    const input = vnode.elm as FlatpickrElement;
                                    input._flatpickr?.destroy();
                                    delete input._flatpickr;
                                },
                            },
                        }),
                    ],
                ),
                h('div.calendar-button-wrap', [
                    h(
                        'button.button.button-green.text',
                        {
                            on: {
                                click: () => {
                                    this.closeScheduleCalendar(cell);
                                    this.submitSchedule(cell, this.scheduleDraft(cell));
                                },
                            },
                        },
                        _('Confirm'),
                    ),
                ]),
            ],
        );
    }

    modalPlayerSection(cell: RRArrangementCell, username: string, position: 'top' | 'bottom'): VNode {
        return h(`div.rr-arr-user.rr-arr-user-${position}`, [
            h('div.rr-arr-name', [this.modalPlayerLink(username), this.modalPlayerColors(cell, username)]),
            this.modalPlayerAction(cell, username),
        ]);
    }

    modalValueRows(cell: RRArrangementCell): Array<VNode | null> {
        return [
            cell.scheduledAt
                ? h('div.title-value-wrap', [
                      h('span.title', `${_('Scheduled at')}:`),
                      h('span.value', this.formatArrangementDate(cell.scheduledAt)),
                  ])
                : null,
            cell.gameId
                ? h('div.title-value-wrap', [
                      h('span.title', `${_('Started at')}:`),
                      h('span.value', this.formatArrangementDate(cell.date)),
                  ])
                : null,
            cell.previousGameIds.length > 0
                ? h('div.title-value-wrap', [
                      h('span.title', `${_('Previous games')}:`),
                      h(
                          'span.value',
                          cell.previousGameIds.flatMap((gameId, index) => [
                              index > 0 ? ', ' : '',
                              h('a', { attrs: { href: `/${gameId}` } }, gameId),
                          ]),
                      ),
                  ])
                : null,
        ];
    }

    renderModal() {
        const cell = this.selectedArrangement();
        if (!cell) {
            this.stopArrangementPresencePolling();
            this.modalNode = patch(this.modalNode, h('div#rr-modal'));
            return;
        }
        this.startArrangementPresencePolling(cell);
        const canAct = [cell.white, cell.black].includes(this.username);
        const users = cell.white === this.username ? [cell.black, cell.white] : [cell.white, cell.black];
        const actionButton = this.modalActionButton(cell);
        this.modalNode = patch(
            this.modalNode,
            h(
                'div#rr-modal.modal-overlay.modal-overlay-fullscreen',
                {
                    style: { display: 'flex' },
                    on: {
                        click: (evt: Event) => {
                            if (evt.target === evt.currentTarget) this.closeArrangement();
                        },
                    },
                },
                [
                    h('div.rr-modal-content.rr-arr-modal', [
                        h('div.rr-arr-header', [
                            h('button.close', {
                                on: { click: () => this.closeArrangement() },
                                attrs: {
                                    type: 'button',
                                    'data-icon': 'j',
                                    title: _('Cancel'),
                                    'aria-label': _('Cancel'),
                                },
                            }),
                            h('h3', `${_('Game scheduling')} • ${_('Round')} ${cell.round}`),
                        ]),
                        h('div.rr-arr-users', [
                            this.modalPlayerSection(cell, users[0], 'top'),
                            this.modalPlayerSection(cell, users[1], 'bottom'),
                        ]),
                        h('div.rr-total-section', [
                            h(
                                'div.values',
                                this.modalValueRows(cell).filter((row): row is VNode => row !== null),
                            ),
                            cell.gameId
                                ? h('div.arr-start-wrap', [actionButton, this.modalAnnulButton(cell)])
                                : actionButton && canAct
                                  ? h('div.arr-start-wrap', [
                                        actionButton,
                                        h(
                                            'span.help',
                                            _('The game will not start automatically at the scheduled time.'),
                                        ),
                                    ])
                                  : null,
                        ]),
                    ]),
                ],
            ),
        );
    }

    challengesVNode() {
        const rows = this.challengeRows();
        return h('div#rr-challenges.box', [
            rows.length === 0
                ? h('div.rr-empty', _('No current challenges or active pairing actions.'))
                : h('table.players', [
                      h(
                          'thead',
                          h('tr', [
                              h('th', _('Opponent')),
                              h('th', _('Round')),
                              h('th', _('Color')),
                              h('th', _('Status')),
                              h('th', _('When')),
                              h('th', _('Action')),
                          ]),
                      ),
                      h(
                          'tbody',
                          rows.map(row => {
                              const cell =
                                  this.selectedArrangementId === row.id ? this.selectedArrangement() : undefined;
                              const target = cell || this.findArrangementById(row.id);
                              return h(
                                  'tr',
                                  {
                                      class: { incoming: row.incoming },
                                      on: target ? { click: () => this.selectArrangement(target) } : {},
                                  },
                                  [
                                      h('td', userLink(row.opponent, [displayUsername(row.opponent)])),
                                      h('td', `${row.round}`),
                                      h('td', row.color.toUpperCase()),
                                      h('td', row.status === 'pending' && row.when ? _('Scheduled') : row.status),
                                      h(
                                          'td',
                                          row.when
                                              ? h('info-date', { attrs: { timestamp: row.when } }, timeago(row.when))
                                              : '',
                                      ),
                                      h(
                                          'td',
                                          row.actionable && target
                                              ? h(
                                                    'button.button',
                                                    {
                                                        on: {
                                                            click: (evt: Event) => {
                                                                evt.stopPropagation();
                                                                this.arrangementAction(target);
                                                            },
                                                        },
                                                    },
                                                    row.label,
                                                )
                                              : row.label,
                                      ),
                                  ],
                              );
                          }),
                      ),
                  ]),
        ]);
    }

    findArrangementById(arrangementId: string): RRArrangementCell | undefined {
        for (const row of Object.values(this.matrix)) {
            for (const cell of Object.values(row)) {
                if (cell.id === arrangementId) return cell;
            }
        }
        return undefined;
    }

    renderManagement() {
        if (!this.canManage()) {
            this.bodyNode = patch(
                this.bodyNode,
                h('div#rr-body', [
                    h('div#rr-management.box.rr-empty', _('Player management is only available to the organizer.')),
                ]),
            );
            return;
        }

        const approved = this.players.filter(player => player.name !== this.createdBy && !player.withdrawn);
        const kickOptions = Array.from(
            new Set([
                ...approved.map(player => player.name),
                ...this.pendingPlayers.map(player => player.name),
                ...this.deniedPlayers.map(player => player.name),
            ]),
        ).sort();

        const renderRow = (player: TournamentManagePlayer, actions: VNode[]) =>
            h('tr', [
                h('td', userLink(player.name, [h('player-title', ` ${player.title} `), displayUsername(player.name)])),
                h('td', `${player.rating}`),
                h('td.manage-actions', actions),
            ]);
        const button = (label: string, message: object, reject = false) =>
            h(`button.button${reject ? '.reject' : ''}`, { on: { click: () => this.doSend(message as any) } }, label);

        this.bodyNode = patch(
            this.bodyNode,
            h('div#rr-body', [
                h('div#rr-management.box', [
                    h('div.rr-section-header', [
                        h('h2', _('Player management')),
                        h(
                            `button.button${this.joiningClosed ? '.button-green' : '.button-red'}`,
                            {
                                on: {
                                    click: () =>
                                        this.doSend({
                                            type: 'rr_set_joining_closed',
                                            tournamentId: this.tournamentId,
                                            closed: !this.joiningClosed,
                                        }),
                                },
                            },
                            this.joiningClosed ? _('Open joining') : _('Close joining'),
                        ),
                    ]),
                    h('div.rr-kick-wrap', [
                        h('label', { attrs: { for: 'rr-kick-user' } }, _('Kick player')),
                        h('div.rr-kick-controls', [
                            h('input#rr-kick-user', {
                                attrs: { list: 'rr-kick-options', placeholder: _('Enter username') },
                                props: { value: this.kickUsername },
                                on: {
                                    input: (evt: Event) => {
                                        this.kickUsername = (evt.target as HTMLInputElement).value;
                                    },
                                },
                            }),
                            h(
                                'datalist#rr-kick-options',
                                kickOptions.map(name => h('option', { attrs: { value: name } })),
                            ),
                            h(
                                'button.button.reject',
                                {
                                    class: { disabled: this.kickUsername.trim() === '' },
                                    on: {
                                        click: () => {
                                            const username = this.kickUsername.trim();
                                            if (username === '') return;
                                            this.doSend({
                                                type: 'rr_kick_player',
                                                tournamentId: this.tournamentId,
                                                username,
                                            });
                                            this.kickUsername = '';
                                            this.renderBody();
                                        },
                                    },
                                },
                                _('Kick'),
                            ),
                        ]),
                    ]),
                    this.approvalRequired ? h('h3', _('Pending requests')) : null,
                    this.approvalRequired
                        ? h('table.players', [
                              h(
                                  'tbody',
                                  this.pendingPlayers.length > 0
                                      ? this.pendingPlayers.map(player =>
                                            renderRow(player, [
                                                button(_('Accept'), {
                                                    type: 'rr_approve_player',
                                                    tournamentId: this.tournamentId,
                                                    username: player.name,
                                                }),
                                                button(
                                                    _('Deny'),
                                                    {
                                                        type: 'rr_deny_player',
                                                        tournamentId: this.tournamentId,
                                                        username: player.name,
                                                    },
                                                    true,
                                                ),
                                            ]),
                                        )
                                      : [h('tr', [h('td', { attrs: { colspan: 3 } }, _('No pending requests'))])],
                              ),
                          ])
                        : null,
                    h('h3', _('Approved players')),
                    h('table.players', [
                        h(
                            'tbody',
                            approved.length > 0
                                ? approved.map(player =>
                                      renderRow(player, [
                                          button(
                                              _('Kick'),
                                              {
                                                  type: 'rr_kick_player',
                                                  tournamentId: this.tournamentId,
                                                  username: player.name,
                                              },
                                              true,
                                          ),
                                      ]),
                                  )
                                : [h('tr', [h('td', { attrs: { colspan: 3 } }, _('No approved players'))])],
                        ),
                    ]),
                    this.approvalRequired ? h('h3', _('Denied players')) : null,
                    this.approvalRequired
                        ? h('table.players', [
                              h(
                                  'tbody',
                                  this.deniedPlayers.length > 0
                                      ? this.deniedPlayers.map(player =>
                                            renderRow(player, [
                                                button(_('Accept'), {
                                                    type: 'rr_approve_player',
                                                    tournamentId: this.tournamentId,
                                                    username: player.name,
                                                }),
                                            ]),
                                        )
                                      : [h('tr', [h('td', { attrs: { colspan: 3 } }, _('No denied players'))])],
                              ),
                          ])
                        : null,
                ]),
            ]),
        );
    }

    renderMatrixShell(lowerContent: VNode) {
        this.bodyNode = patch(
            this.bodyNode,
            h('div#rr-body', [
                h('div#player', [
                    h('div#stats', [h('div#rr-crosstable')]),
                    this.viewNavVNode(),
                    h(
                        'div',
                        {
                            attrs: {
                                id: `rr-panel-${this.viewMode}`,
                                'aria-labelledby': `rr-tab-${this.viewMode}`,
                            },
                        },
                        [lowerContent],
                    ),
                ]),
            ]),
        );
        this.crossTableNode = patch(document.getElementById('rr-crosstable') as HTMLElement, h('div#rr-crosstable'));
        this.renderCrossTable();
    }

    renderOverview() {
        this.renderMatrixShell(this.gamesVNode());
        this.renderModal();
    }

    renderChallenges() {
        this.renderMatrixShell(this.challengesVNode());
        this.renderModal();
    }

    renderBody() {
        if (this.viewMode === 'manage') {
            this.renderManagement();
            this.renderModal();
            return;
        }
        if (this.viewMode === 'challenges') {
            this.renderChallenges();
            this.renderModal();
            return;
        }
        this.renderOverview();
    }

    completed() {
        return ['aborted', 'finished', 'archived'].includes(this.tournamentStatus);
    }

    calcRate(nbGames: number, wins: number) {
        return `${nbGames !== 0 ? Math.round(100 * (wins / nbGames)) : 0}%`;
    }

    renderSummary() {
        if (!this.completed() || this.summaryStats.nbGames <= 0) {
            this.summaryNode = patch(this.summaryNode, h('div#summarybox'));
            return;
        }
        const msg = this.summaryStats;
        this.summaryNode = patch(
            this.summaryNode,
            h('div#summarybox', [
                h('div#summary.box', [
                    h('h2', _('Tournament complete')),
                    h('table', [
                        h('tr', [h('th', _('Players')), h('td', msg.nbPlayers)]),
                        h('tr', [
                            h('th', _('Average rating')),
                            h('td', msg.nbPlayers > 0 ? Math.round(msg.sumRating / msg.nbPlayers) : 0),
                        ]),
                        h('tr', [h('th', _('Games played')), h('td', msg.nbGames)]),
                        h('tr', [h('th', _('%1 wins', _('White'))), h('td', this.calcRate(msg.nbGames, msg.wWin))]),
                        h('tr', [h('th', _('%1 wins', _('Black'))), h('td', this.calcRate(msg.nbGames, msg.bWin))]),
                        h('tr', [h('th', _('Draws')), h('td', this.calcRate(msg.nbGames, msg.draw))]),
                    ]),
                ]),
            ]),
        );
    }

    renderPodium() {
        if (!this.completed() || this.podiumPlayers.length === 0 || this.summaryStats.nbGames <= 0) {
            this.podiumNode = patch(this.podiumNode, h('div#podium'));
            return;
        }
        const classes = ['first', 'second', 'third'];
        this.podiumNode = patch(
            this.podiumNode,
            h('div#podium', [
                h(
                    'div.podium',
                    this.podiumPlayers
                        .slice(0, 3)
                        .map((player, index) =>
                            h(`div.${classes[index] || 'third'}`, [
                                h('div.trophy'),
                                userLink(player.name, [
                                    h('player-title', ` ${player.title} `),
                                    displayUsername(player.name),
                                ]),
                                h('table.stats', [
                                    h('tr', [h('th', _('Performance')), h('td', player.perf)]),
                                    h('tr', [h('th', _('Games played')), h('td', player.nbGames)]),
                                    h('tr', [
                                        h('th', _('Win rate')),
                                        h('td', this.calcRate(player.nbGames, player.nbWin)),
                                    ]),
                                ]),
                            ]),
                        ),
                ),
            ]),
        );
    }

    private onMsgUserConnected(msg: MsgUserConnectedTournament) {
        this.userStatus = msg.ustatus;
        this.creatorCanManage = msg.creatorCanManage;
        this.rounds = msg.rounds || this.rounds;
        this.tournamentStatus = T_STATUS[msg.tstatus as keyof typeof T_STATUS];
        this.roundOngoingGames = msg.roundOngoingGames || 0;
        this.secondsToNextRound = msg.secondsToNextRound || 0;
        this.manualNextRoundPending = msg.manualNextRound ?? false;
        this.renderInfo(msg);
        this.updateLifecycleActions();
    }

    private onMsgTournamentStatus(msg: MsgTournamentStatus) {
        this.tournamentStatus = T_STATUS[msg.tstatus as keyof typeof T_STATUS];
        this.rounds = msg.rounds || this.rounds;
        this.secondsToFinish = msg.secondsToFinish;
        this.roundOngoingGames = msg.roundOngoingGames || 0;
        this.secondsToNextRound = msg.secondsToNextRound || 0;
        this.manualNextRoundPending = msg.manualNextRound ?? false;
        this.summaryStats = {
            nbPlayers: msg.nbPlayers,
            sumRating: msg.sumRating,
            nbGames: msg.nbGames,
            wWin: msg.wWin,
            bWin: msg.bWin,
            draw: msg.draw,
        };
        initializeClock(this as any);
        this.updateActionButton();
        this.updateLifecycleActions();
        this.renderSummary();
        this.renderModal();
        this.syncAnnulDeadlineTimer();
    }

    private onMsgGetPlayers(msg: MsgGetPlayers) {
        this.players = msg.players;
        this.podiumPlayers = msg.podium || [];
        if (!this.selectedPlayer && this.players.length > 0) {
            this.selectedPlayer = this.players[0].name;
            this.doSend({ type: 'get_games', tournamentId: this.tournamentId, player: this.selectedPlayer });
        }
        this.doSend({ type: 'get_rr_arrangements', tournamentId: this.tournamentId });
        this.renderPodium();
        this.renderBody();
    }

    private onMsgGetGames(msg: MsgGetGames) {
        this.selectedPlayer = msg.name;
        this.selectedGames = msg.games;
        if (this.viewMode === 'overview') this.renderGames();
    }

    private onMsgRRArrangements(msg: MsgRRArrangements) {
        this.rrPlayers = msg.players;
        this.matrix = msg.matrix;
        this.completedGames = msg.completedGames;
        this.totalGames = msg.totalGames;
        Object.values(this.matrix).forEach(row =>
            Object.values(row).forEach(cell => {
                this.scheduleDrafts[cell.id] = this.defaultScheduleDraft(cell);
            }),
        );
        if (this.selectedArrangementId !== '' && !this.selectedArrangement()) this.selectedArrangementId = '';
        this.renderBody();
    }

    private onMsgRRManagement(msg: MsgRRManagement) {
        this.createdBy = msg.createdBy;
        this.approvalRequired = msg.approvalRequired;
        this.joiningClosed = msg.joiningClosed;
        this.pendingPlayers = msg.pendingPlayers;
        this.deniedPlayers = msg.deniedPlayers;
        this.renderManageButton();
        this.updateActionButton();
        this.renderBody();
    }

    private onMsgRRSettings(msg: MsgRRSettings) {
        this.createdBy = msg.createdBy;
        this.approvalRequired = msg.approvalRequired;
        this.joiningClosed = msg.joiningClosed;
        this.renderManageButton();
        this.updateActionButton();
        if (this.viewMode === 'manage' && !this.canManage()) this.viewMode = 'overview';
        this.renderBody();
    }

    private onMsgUserStatus(msg: MsgUserStatus) {
        this.userStatus = msg.ustatus;
        syncTournamentStartAlerts(this as any);
        this.updateActionButton();
    }

    private onMsgNewGame(msg: any) {
        redirectFirst(msg.gameId, () => {
            sound.genericNotify();
            window.setTimeout(() => window.location.assign('/' + msg.gameId), 700);
        });
    }

    private onMsgError(msg: MsgError) {
        void alertDialog({ text: msg.message });
    }

    private onMsgPing(msg: MsgPing) {
        this.doSend({ type: 'pong', timestamp: msg.timestamp });
    }

    onMsgChat(msg: any) {
        chatMessage(msg.user, msg.message, 'lobbychat');
    }

    onMsgFullChat(msg: any) {
        msg.lines.forEach((line: any) => chatMessage(line.user, line.message, 'lobbychat'));
    }

    onMessage(evt: MessageEvent) {
        if (evt.data === '/n') return;
        const msg = JSON.parse(evt.data);
        switch (msg.type) {
            case 'tournament_user_connected':
                this.onMsgUserConnected(msg);
                break;
            case 'tstatus':
                this.onMsgTournamentStatus(msg);
                break;
            case 'get_players':
                this.onMsgGetPlayers(msg);
                break;
            case 'get_games':
                this.onMsgGetGames(msg);
                break;
            case 'rr_arrangements':
                this.onMsgRRArrangements(msg);
                break;
            case 'rr_management':
                this.onMsgRRManagement(msg);
                break;
            case 'rr_settings':
                this.onMsgRRSettings(msg);
                break;
            case 'ustatus':
                this.onMsgUserStatus(msg);
                break;
            case 'new_game':
                this.onMsgNewGame(msg);
                break;
            case 'lobbychat':
                this.onMsgChat(msg);
                break;
            case 'fullchat':
                this.onMsgFullChat(msg);
                break;
            case 'ping':
                this.onMsgPing(msg);
                break;
            case 'error':
                this.onMsgError(msg);
                break;
        }
    }
}

function runTournamentRR(vnode: VNode, model: PyChessModel) {
    new TournamentRRController(vnode.elm as HTMLElement, model);
}

export function tournamentRRView(model: PyChessModel): VNode[] {
    const variant = VARIANTS[model.variant] ?? VARIANTS['chess'];
    const chess960 = model.chess960 === 'True';
    const dataIcon = variant.icon(chess960);
    const canEdit =
        (model.tournamentmanager && model.status === 0) ||
        (model.admin && (model.status === 0 || model.status === 1));

    return [
        h('aside.sidebar-first', [
            h('div.game-info', [
                h('div.info0.icon', { attrs: { 'data-icon': dataIcon } }, [
                    h('div.info2', [
                        h('div.tc', [
                            timeControlStr(model.base, model.inc, model.byo) + ' • ',
                            variant.displayName(chess960),
                            h('span#tminutes'),
                        ]),
                        h('div#rr-info-meta', [
                            h('div#tsystem'),
                            canEdit
                                ? h('a.icon-cog.edit-tournament', {
                                      attrs: {
                                          href: `/tournaments/${model.tournamentId}/edit`,
                                          title: _('Edit tournament'),
                                      },
                                  })
                                : null,
                        ]),
                        model.tournamentteamid
                            ? h('div.tournament-team', [
                                  h('strong', _('Team')),
                                  ' ',
                                  h(
                                      'a',
                                      { attrs: { href: `/team/${model.tournamentteamid}` } },
                                      model.tournamentteamname || model.tournamentteamid,
                                  ),
                              ])
                            : null,
                        h('div#createdBy'),
                    ]),
                ]),
                h('div#description'),
                h('div#startsAt'),
                h('div#rr-manage'),
            ]),
            h('div#tournament-lifecycle'),
            h('div#lobbychat'),
        ]),
        h(`div.players.${model.variant}`, [
            h('div.box', [
                h('div.tour-header', [h('h1', model.tournamentname), h('div#clockdiv')]),
                h('div#podium'),
                h('div#page-controls.btn-controls', [h('div#action')]),
                h('div#rr-shell', { hook: { insert: vnode => runTournamentRR(vnode, model) } }),
                h('div#rr-body'),
                h('div#summarybox'),
                h('div.tour-faq'),
            ]),
        ]),
        h('div#rr-modal'),
        h('under-chat#spectators'),
    ];
}
