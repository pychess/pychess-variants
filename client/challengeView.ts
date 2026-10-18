import { h, VNode } from 'snabbdom';

import { colorIcon } from './chess';
import { _ } from './i18n';
import { patch } from './document';
import { alertDialog } from './alertDialog';
import { sound } from './sound';
import { VARIANTS } from './variants';
import { subscribeHeaderRealtime } from './headerRealtime';
import { setHeaderPanelExpanded } from './headerPanel';

interface Challenge {
    id: string;
    challenger: string;
    challengerTitle: string;
    opponent: string;
    incoming: boolean;
    variant: string;
    chess960: boolean | null;
    rated: boolean;
    color: string;
    tc: string;
    expireAt: string;
    status: string;
}

interface ChallengeEnvelope {
    challenges: Challenge[];
    gameId?: string;
}

const DECLINE_REASONS: Array<{ key: string; label: string }> = [
    { key: 'generic', label: "I'm not accepting challenges at the moment." },
    { key: 'later', label: 'This is not the right time for me, please ask again later.' },
    { key: 'tooFast', label: 'This time control is too fast for me, please challenge again with a slower game.' },
    { key: 'tooSlow', label: 'This time control is too slow for me, please challenge again with a faster game.' },
    { key: 'timeControl', label: "I'm not accepting challenges with this time control." },
    { key: 'rated', label: 'Please send me a rated challenge instead.' },
    { key: 'casual', label: 'Please send me a casual challenge instead.' },
    { key: 'standard', label: "I'm not accepting variant challenges right now." },
    { key: 'variant', label: "I'm not willing to play this variant right now." },
    { key: 'noBot', label: "I'm not accepting challenges from bots." },
    { key: 'onlyBot', label: "I'm only accepting challenges from bots." },
];

function challengeLabel(challenge: Challenge) {
    const prefix = challenge.challengerTitle ? `${challenge.challengerTitle} ` : '';
    if (challenge.status === 'declined') {
        return challenge.incoming
            ? `${_('You declined')} ${prefix}${challenge.challenger}`
            : `${challenge.opponent} ${_('declined your challenge')}`;
    }
    if (challenge.status === 'canceled') {
        return challenge.incoming
            ? `${prefix}${challenge.challenger} ${_('canceled the challenge')}`
            : `${_('Challenge to')} ${challenge.opponent} ${_('was canceled')}`;
    }
    if (challenge.status === 'accepted') {
        return challenge.incoming
            ? `${prefix}${challenge.challenger} ${_('started the game')}`
            : `${_('Challenge accepted by')} ${challenge.opponent}`;
    }
    return challenge.incoming ? `${prefix}${challenge.challenger}` : challenge.opponent;
}

function challengeVariantIcon(challenge: Challenge) {
    const variant = VARIANTS[challenge.variant];
    return variant ? variant.icon(Boolean(challenge.chess960)) : '';
}

function challengeColorIconClass(challenge: Challenge) {
    const variant = VARIANTS[challenge.variant];
    if (!variant) return '';
    if (challenge.color === 'w') return colorIcon(challenge.variant, variant.colors.first);
    if (challenge.color === 'b') return colorIcon(challenge.variant, variant.colors.second);
    return '';
}

function challengeMetaView(challenge: Challenge) {
    const colorClass = challengeColorIconClass(challenge);
    const colorIconVNode = colorClass
        ? [h('span.challenge-color', [h('span.is', { class: { [colorClass]: true } })]), h('span.challenge-dot', '•')]
        : [];
    const variant = VARIANTS[challenge.variant];
    const variantName = variant
        ? variant.displayName(Boolean(challenge.chess960))
        : `${challenge.variant}${challenge.chess960 ? '960' : ''}`;

    const parts = [challenge.rated ? _('Rated') : _('Casual'), challenge.tc, variantName];

    if (challenge.status === 'offline') parts.push(_('Offline'));
    else if (challenge.status === 'declined') parts.push(_('Declined'));
    else if (challenge.status === 'accepted') parts.push(_('Accepted'));

    return h('span.challenge-meta', [
        ...colorIconVNode,
        ...parts.flatMap((part, index) => (index === 0 ? [part] : [h('span.challenge-dot', '•'), part])),
    ]);
}

export function challengeView() {
    let challenges: Challenge[] = [];
    let appEl: HTMLElement | VNode;
    let realtime: ReturnType<typeof subscribeHeaderRealtime> | null = null;
    let challengeStreamReady = false;
    const pending = new Set<string>();

    const counterEl = () => document.querySelector('#btn-challenge .data-count') as HTMLElement | null;

    function visibleChallenges() {
        return challenges.filter(challenge => challenge.status !== 'declined');
    }

    function incomingCount() {
        return visibleChallenges().reduce(
            (sum, challenge) => sum + (challenge.incoming && ['created', 'offline'].includes(challenge.status) ? 1 : 0),
            0,
        );
    }

    function redraw() {
        const count = incomingCount();
        const counter = counterEl();
        if (counter) counter.setAttribute('data-count', `${count}`);
        const button = document.getElementById('btn-challenge') as HTMLElement | null;
        if (button) {
            const label = `${_('Challenges')}: ${count}`;
            button.setAttribute('aria-label', label);
            button.setAttribute('title', label);
        }
        appEl = patch(appEl, h('div#challenge-app', renderChallenges()));
    }

    function activeIncomingChallengeIds(items: Challenge[]) {
        return new Set(
            items
                .filter(challenge => challenge.incoming && ['created', 'offline'].includes(challenge.status))
                .map(challenge => challenge.id),
        );
    }

    function applyEnvelope(envelope: ChallengeEnvelope, allowSound = false) {
        const previousActiveIncoming = activeIncomingChallengeIds(challenges);
        challenges = envelope.challenges;
        const nextActiveIncoming = activeIncomingChallengeIds(challenges);
        if (allowSound && [...nextActiveIncoming].some(challengeId => !previousActiveIncoming.has(challengeId))) {
            sound.newChallenge();
        }
        redraw();
        if (envelope.gameId) window.location.assign(`/${envelope.gameId}`);
    }

    function loadChallenges() {
        fetch('/challenges')
            .then(res => res.json())
            .then((payload: ChallengeEnvelope) => applyEnvelope(payload))
            .catch(err => console.warn('Failed to load challenges.', err));
    }

    function connectChallenges() {
        realtime?.close();
        realtime = subscribeHeaderRealtime('challenges', data => {
            applyEnvelope(JSON.parse(data), challengeStreamReady);
            challengeStreamReady = true;
        });
    }

    function postAction(challenge: Challenge, action: 'accept' | 'decline' | 'cancel', reason = 'generic') {
        pending.add(challenge.id);
        if (action === 'cancel' || action === 'decline') {
            challenges = challenges.filter(item => item.id !== challenge.id);
        }
        redraw();
        const init: RequestInit = { method: 'POST' };
        if (action === 'decline') {
            init.headers = { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' };
            init.body = new URLSearchParams({ reason }).toString();
        }
        fetch(`/api/challenge/seek/${challenge.id}/${action}`, init)
            .then(res => res.json())
            .then(payload => {
                if (payload.type === 'error') {
                    void alertDialog({ text: payload.message });
                } else if (payload.type === 'new_game' && payload.gameId) {
                    window.location.assign(`/${payload.gameId}`);
                    return;
                }
                loadChallenges();
            })
            .catch(err => console.warn(`Failed to ${action} challenge.`, err))
            .finally(() => {
                pending.delete(challenge.id);
                redraw();
            });
    }

    function actionButtons(challenge: Challenge) {
        if (!['created', 'offline'].includes(challenge.status)) return undefined;
        const disabled = pending.has(challenge.id);
        if (challenge.incoming) {
            return h('div.challenge-actions', [
                h('button.challenge-action.challenge-action-accept', {
                    props: { type: 'button', disabled },
                    attrs: { title: _('Accept'), 'aria-label': _('Accept'), 'data-icon': '?' },
                    on: { click: () => postAction(challenge, 'accept') },
                }),
                h('button.challenge-action.challenge-action-decline', {
                    props: { type: 'button', disabled },
                    attrs: { title: _('Decline'), 'aria-label': _('Decline'), 'data-icon': 'j' },
                    on: { click: () => postAction(challenge, 'decline') },
                }),
                h(
                    'select.challenge-reason',
                    {
                        props: { disabled, value: 'generic' },
                        attrs: { title: _('Decline with reason'), 'aria-label': _('Decline with reason') },
                        on: {
                            change: (event: Event) => {
                                const select = event.target as HTMLSelectElement;
                                const reason = select.value;
                                if (!reason || reason === 'generic') return;
                                postAction(challenge, 'decline', reason);
                                select.value = 'generic';
                            },
                        },
                    },
                    [
                        h('option', { attrs: { value: 'generic' } }, ''),
                        ...DECLINE_REASONS.filter(reason => reason.key !== 'generic').map(reason =>
                            h('option', { attrs: { value: reason.key } }, _(reason.label)),
                        ),
                    ],
                ),
            ]);
        }
        return h('div.challenge-actions', [
            h('div.challenge-owner', _('Waiting')),
            h('button.challenge-action.challenge-action-decline', {
                props: { type: 'button', disabled },
                attrs: { title: _('Cancel'), 'aria-label': _('Cancel'), 'data-icon': 'j' },
                on: { click: () => postAction(challenge, 'cancel') },
            }),
        ]);
    }

    function renderChallenges() {
        const items = visibleChallenges();
        if (items.length === 0) {
            return [h('span.notification.empty', [h('span.text', _('No challenges.'))])];
        }

        return items.map(challenge => {
            const actions = actionButtons(challenge);
            return h(
                `div.notification.challenge${challenge.incoming && ['created', 'offline'].includes(challenge.status) ? '.new' : ''}${challenge.status === 'declined' ? '.challenge-inactive' : ''}`,
                {
                    attrs: { tabindex: 0 },
                },
                [
                    h('div.content', [
                        h('div.challenge-main', [
                            h('div.challenge-text', [
                                h('span.challenge-head', [h('strong', challengeLabel(challenge))]),
                                challengeMetaView(challenge),
                            ]),
                            h('div.icon.challenge-variant-icon', {
                                attrs: { 'data-icon': challengeVariantIcon(challenge) },
                            }),
                        ]),
                        ...(actions ? [actions] : []),
                    ]),
                ],
            );
        });
    }

    function showChallenge() {
        setHeaderPanelExpanded('btn-challenge', true);
        (document.getElementById('challenge-app') as HTMLElement).style.display = 'flex';
    }

    function toggleChallenge() {
        if ((document.getElementById('challenge-app') as HTMLElement).style.display === 'flex') {
            hideChallenge();
        } else {
            showChallenge();
        }
    }

    window.setTimeout(() => {
        appEl = document.getElementById('challenge-app') as HTMLElement;
        loadChallenges();
        connectChallenges();
    }, 0);

    return h('div#challenge-panel', [
        h(
            'button#btn-challenge',
            { on: { click: toggleChallenge }, attrs: {
                    'aria-label': `${_('Challenges')}: 0`,
                    title: `${_('Challenges')}: 0`,
                    'aria-expanded': 'false',
                    'aria-controls': 'challenge-app',
                } },
            [h('div.icon.icon-crossedswords.data-count', { attrs: { 'data-count': 0 } })],
        ),
        h('div#challenge-app'),
    ]);
}

export function hideChallenge() {
    setHeaderPanelExpanded('btn-challenge', false);
    (document.getElementById('challenge-app') as HTMLElement).style.display = 'none';
}
