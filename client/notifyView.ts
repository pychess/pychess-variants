import { h, VNode } from 'snabbdom';

import { _ } from './i18n';
import { patch } from './document';
import { timeago } from './datetime';
import { sound } from './sound';
import { subscribeHeaderRealtime } from './headerRealtime';
import { setHeaderPanelExpanded } from './headerPanel';

interface Message {
    type: string;
    read: boolean;
    createdAt: string;
    content: {
        id: string;
        tid?: string;
        arr?: string;
        opp: string;
        topic?: string;
        slug?: string;
        categ?: string;
        team?: string;
        name?: string;
        text?: string;
        date?: string;
        win?: boolean | null;
        san?: string;
    };
}

function corrMoveText(opp: string, san?: string) {
    return `${opp} ${_('played')} ${san || _('a move')}`;
}

function result(win: boolean | null) {
    switch (win) {
        case true:
            return 'Congratulations, you won!';
        case false:
            return 'Defeat';
        default:
            return 'Draw';
    }
}

function messageView(message: Message) {
    const read = message.read ? '' : '.new';
    const content = message.content;
    switch (message.type) {
        case 'gameAborted':
            return h(`div.notification.corr${read}`, [
                h('div.icon.icon-paper-plane'),
                h('span.content', [
                    h('span', [
                        h('strong', 'Game vs ' + content.opp),
                        h('info.date', { attrs: { timestamp: message.createdAt } }, timeago(message.createdAt)),
                    ]),
                    h('span', 'Game aborted'),
                ]),
            ]);
        case 'gameEnd':
            return h(`a.notification.corr${read}`, { attrs: { href: '/' + content.id } }, [
                h('div.icon.icon-paper-plane'),
                h('span.content', [
                    h('span', [
                        h('strong', 'Game vs ' + content.opp),
                        h('info.date', { attrs: { timestamp: message.createdAt } }, timeago(message.createdAt)),
                    ]),
                    h('span', result(content.win ?? null)),
                ]),
            ]);
        case 'corrAlarm':
            return h(`a.notification.corr${read}`, { attrs: { href: '/' + content.id } }, [
                h('div.icon.icon-paper-plane'),
                h('span.content', [
                    h('span', [
                        h('strong', 'Time is almost up!'),
                        h('info.date', { attrs: { timestamp: message.createdAt } }, timeago(message.createdAt)),
                    ]),
                    h('span', 'Game vs ' + content.opp),
                ]),
            ]);
        case 'corrMove':
            return h(`a.notification.corr${read}`, { attrs: { href: '/' + content.id } }, [
                h('div.icon.icon-paper-plane'),
                h('span.content', [
                    h('span', [
                        h('strong', _('It is your turn')),
                        h('info.date', { attrs: { timestamp: message.createdAt } }, timeago(message.createdAt)),
                    ]),
                    h('span', corrMoveText(content.opp, content.san)),
                ]),
            ]);
        case 'swissStartReminder':
            return h(
                `a.notification.corr${read}`,
                { attrs: { href: `/tournament/${content.tid || content.id}` } },
                [
                    h('div.icon.icon-bullhorn'),
                    h('span.content', [
                        h('span', [
                            h('strong', _('Swiss tournament starting soon')),
                            h('info.date', { attrs: { timestamp: message.createdAt } }, timeago(message.createdAt)),
                        ]),
                        h(
                            'span',
                            `${content.name || _('Your Swiss tournament')} ${_('starts at')} ${content.date ? new Date(content.date).toLocaleString() : ''}.`,
                        ),
                    ]),
                ],
            );
        case 'rrChallenge':
            return h(
                `a.notification.corr${read}`,
                {
                    attrs: {
                        href: `/tournament/${content.tid || content.id}${content.arr ? `#${content.arr}` : ''}`,
                    },
                },
                [
                    h('div.icon.icon-crossedswords'),
                    h('span.content', [
                        h('span', [
                            h('strong', _('Round-robin challenge')),
                            h('info.date', { attrs: { timestamp: message.createdAt } }, timeago(message.createdAt)),
                        ]),
                        h('span', `${content.opp} ${_('challenged you in your tournament pairing.')}`),
                    ]),
                ],
            );
        case 'rrArrangementTime':
            return h(
                `a.notification.corr${read}`,
                {
                    attrs: {
                        href: `/tournament/${content.tid || content.id}${content.arr ? `#${content.arr}` : ''}`,
                    },
                },
                [
                    h('div.icon.icon-check'),
                    h('span.content', [
                        h('span', [
                            h('strong', _('Round-robin scheduling')),
                            h('info.date', { attrs: { timestamp: message.createdAt } }, timeago(message.createdAt)),
                        ]),
                        h(
                            'span',
                            `${content.opp} ${_('agreed on')} ${content.date ? new Date(content.date).toLocaleString() : _('your proposed game time')}.`,
                        ),
                    ]),
                ],
            );
        case 'rrArrangementReminder':
            return h(
                `a.notification.corr${read}`,
                {
                    attrs: {
                        href: `/tournament/${content.tid || content.id}${content.arr ? `#${content.arr}` : ''}`,
                    },
                },
                [
                    h('div.icon.icon-bullhorn'),
                    h('span.content', [
                        h('span', [
                            h('strong', _('Round-robin reminder')),
                            h('info.date', { attrs: { timestamp: message.createdAt } }, timeago(message.createdAt)),
                        ]),
                        h(
                            'span',
                            `${_('Your scheduled pairing with')} ${content.opp} ${_('is coming up at')} ${content.date ? new Date(content.date).toLocaleString() : ''}.`,
                        ),
                    ]),
                ],
            );
        case 'teamUpdate':
            return h(
                `a.notification.corr${read}`,
                { attrs: { href: `/team/${encodeURIComponent(content.team || '')}/updates` } },
                [
                    h('div.icon.icon-bullhorn'),
                    h('span.content', [
                        h('span', [
                            h('strong', content.name || _('Team update')),
                            h('info.date', { attrs: { timestamp: message.createdAt } }, timeago(message.createdAt)),
                        ]),
                        h('span', content.text || _('New team update')),
                    ]),
                ],
            );
        case 'inboxMsg':
            return h(`a.notification.corr${read}`, { attrs: { href: `/inbox/${encodeURIComponent(content.id)}` } }, [
                h('div.icon.icon-comment-o'),
                h('span.content', [
                    h('span', [
                        h('strong', _('Inbox message')),
                        h('info.date', { attrs: { timestamp: message.createdAt } }, timeago(message.createdAt)),
                    ]),
                    h('span', `${_('New message from')} ${content.opp}`),
                ]),
            ]);
        case 'forumMention': {
            const topicName = content.topic || _('a forum topic');
            const href =
                content.categ && content.slug
                    ? `/forum/${encodeURIComponent(content.categ)}/${encodeURIComponent(content.slug)}#${encodeURIComponent(content.id)}`
                    : '/forum';
            return h(`a.notification.corr${read}`, { attrs: { href } }, [
                h('div.icon.icon-comment-o'),
                h('span.content', [
                    h('span', [
                        h('strong', content.opp),
                        h('info.date', { attrs: { timestamp: message.createdAt } }, timeago(message.createdAt)),
                    ]),
                    h('span', `${_('mentioned you in')} ${topicName}`),
                ]),
            ]);
        }
        default:
            return '';
    }
}

function compareMessages(a: Message, b: Message) {
    if (a.createdAt < b.createdAt) return 1;
    if (a.createdAt > b.createdAt) return -1;
    return 0;
}

function renderMessages(messages: Message[]) {
    let renderedMessages = [];
    if (messages.length === 0) {
        renderedMessages.push(
            h('span.notification.empty', [h('div.icon.icon-info', '🛈'), h('span.text', _('No notifications.'))]),
        );
    } else {
        messages.sort(compareMessages).forEach((message: Message) => renderedMessages.push(messageView(message)));
    }
    return renderedMessages;
}

export function notifyView() {
    var page: number = 0;
    var unread: number = 0;
    var messages: Message[] = [];
    let realtime: ReturnType<typeof subscribeHeaderRealtime> | null = null;
    let notifyStreamReady = false;

    const xmlhttp = new XMLHttpRequest();
    const url = '/notifications?p=';
    var notifyAppEl: HTMLElement | VNode;

    const newNotifyCounter = (sum: number, message: Message) => sum + (message.read ? 0 : 1);

    function redraw() {
        const counter = document.querySelector('#btn-notify .data-count') as HTMLElement | null;
        if (counter) counter.setAttribute('data-count', `${unread}`);
        const button = document.getElementById('btn-notify') as HTMLElement | null;
        if (button) button.setAttribute('aria-label', `Notifications: ${unread}`);
        notifyAppEl = patch(notifyAppEl, h('div#notify-app', renderMessages(messages)));
    }

    function unreadMessageIds(items: Message[]) {
        return new Set(items.filter(message => !message.read).map(message => `${message.type}:${message.createdAt}`));
    }

    function applyMessages(nextMessages: Message[], allowSound = false) {
        const previousUnread = unreadMessageIds(messages);
        messages = nextMessages;
        unread = messages.reduce(newNotifyCounter, 0);
        if (allowSound) {
            const newUnread = messages.filter(
                message => !message.read && !previousUnread.has(`${message.type}:${message.createdAt}`),
            );
            if (newUnread.length > 0) {
                if (newUnread.some(message => message.type === 'inboxMsg')) sound.newPM();
                else sound.genericNotify();
            }
        }
        page = 0;
        redraw();
    }

    function connectNotifications() {
        realtime?.close();
        realtime = subscribeHeaderRealtime('notifications', data => {
            applyMessages(JSON.parse(data), notifyStreamReady);
            notifyStreamReady = true;
        });
    }

    xmlhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            notifyAppEl = document.getElementById('notify-app') as HTMLElement;
            applyMessages(JSON.parse(this.responseText));
            connectNotifications();
        }
    };
    xmlhttp.open('GET', `${url}${page}`, true);
    xmlhttp.send();

    function sendNotified() {
        void window.fetch('/notified', { method: 'POST' });
    }

    function showNotify() {
        if (unread > 0) {
            messages.forEach(msg => (msg.read = true));
            unread = 0;
            (document.querySelector('#btn-notify .data-count') as HTMLElement).setAttribute('data-count', `${unread}`);
            sendNotified();
        } else {
            document.querySelectorAll('#notify-app .notification.new').forEach(el => el.classList.remove('new'));
        }
        setHeaderPanelExpanded('btn-notify', true);
        (document.getElementById('notify-app') as HTMLElement).style.display = 'flex';
    }

    function toggleNotify() {
        if ((document.getElementById('notify-app') as HTMLElement).style.display === 'flex') {
            hideNotify();
        } else {
            showNotify();
        }
    }

    return h('div#notify-panel', [
        h('button#btn-notify', { on: { click: toggleNotify }, attrs: { 'aria-label': `Notifications: ${unread}`, 'aria-expanded': 'false', 'aria-controls': 'notify-app' } }, [
            h('div.icon.icon-bell-o.data-count', { attrs: { 'data-count': 0 } }),
        ]),
        h('div#notify-app'),
    ]);
}

export function hideNotify() {
    setHeaderPanelExpanded('btn-notify', false);
    (document.getElementById('notify-app') as HTMLElement).style.display = 'none';
}
