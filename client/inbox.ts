import { h, VNode } from 'snabbdom';

import { _ } from './i18n';
import { patch } from './document';
import { timeago } from './datetime';
import { PyChessModel } from './types';
import { confirmDialog } from './confirmDialog';
import { alertDialog } from './alertDialog';
import { expandInboxGameEmbeds, makeExternalLinkPopups, renderRichText } from './richTextEnhance';

interface ThreadSummary {
    user: string;
    title: string;
    online?: boolean;
    patron?: boolean;
    system?: boolean;
    updatedAt: string;
    unread: boolean;
    lastMsg: {
        user: string;
        text: string;
        createdAt: string;
    };
}

interface Message {
    _id: string;
    tid: string;
    from: string;
    to: string;
    text: string;
    createdAt: string;
}

interface InboxApiError {
    type?: string;
    code?: string;
    message?: string;
}

const INBOX_MAX_MSG_LEN = 2000;

function inboxApiErrorMessage(data: InboxApiError, fallback: string): string {
    switch (data.code) {
        case 'login_required': return _('Login required');
        case 'invalid_contact': return _('Invalid contact');
        case 'user_not_found': return _('User not found');
        case 'invalid_before': return _('Invalid message cursor');
        case 'system_user_no_messages': return _("PyChess doesn't accept new messages.");
        case 'invalid_request': return _('Invalid request');
        case 'message_empty': return _('Message is empty');
        case 'message_too_long': return _('Message too long (max %1)', INBOX_MAX_MSG_LEN);
        case 'too_many_similar_messages': return _('Too many similar messages. Please wait and retry.');
        case 'cannot_send_from_account': return _('Cannot send messages from this account');
        case 'user_blocked': return _('User is blocked');
        case 'cannot_message_user': return _('Cannot message this user');
        case 'friends_only': return _('Only friends can message this user');
        case 'system_messages_cannot_delete': return _('PyChess system messages cannot be deleted.');
        default: return data.message || fallback;
    }
}

interface ThreadResponse {
    contact: {
        name: string;
        title: string;
        online?: boolean;
        patron?: boolean;
        system?: boolean;
        canMessage?: boolean;
        blockedByMe?: boolean;
        blockedByThem?: boolean;
    };
    messages: Message[];
    hasMore?: boolean;
}

async function parseJsonResponse(res: Response) {
    const text = await res.text();
    if (text.length === 0) return { status: res.status, data: {} as any };
    try {
        return { status: res.status, data: JSON.parse(text) };
    } catch {
        throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
    }
}

function titleAndName(title: string, name: string) {
    return title ? `${title} ${name}` : name;
}

function pad2(num: number): string {
    return (num < 10 ? '0' : '') + num;
}

function parseDate(input: string): Date | null {
    const date = new Date(input);
    return Number.isNaN(date.getTime()) ? null : date;
}

function sameDay(left: Date, right: Date): boolean {
    return (
        left.getDate() === right.getDate() &&
        left.getMonth() === right.getMonth() &&
        left.getFullYear() === right.getFullYear()
    );
}

function renderDayLabel(date: Date): string {
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);

    if (sameDay(date, today)) return _('Today').toUpperCase();
    if (sameDay(date, yesterday)) return _('Yesterday').toUpperCase();

    return date.toLocaleDateString(undefined, { year: 'numeric', month: 'numeric', day: 'numeric' });
}

function renderClockTime(input: string): string {
    const date = parseDate(input);
    if (date === null) return '';
    return `${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

function reportThreadId(user1: string, user2: string): string {
    return [user1, user2]
        .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }) || a.localeCompare(b))
        .join(':');
}

export function inboxView(model: PyChessModel) {
    let threads: ThreadSummary[] = [];
    let contact = model.profileid || '';
    let contactTitle = '';
    let contactOnline = false;
    let contactPatron = false;
    let contactSystem = false;
    let contactCanMessage = true;
    let blockedUsers = new Set<string>();
    let contactBlocked = false;
    let contactBlockedByThem = false;
    let messages: Message[] = [];
    let hasMoreMessages = false;
    let loadingMore = false;
    let draft = '';
    let loading = true;
    let sending = false;
    let appEl: HTMLElement | VNode;
    let evtSource: EventSource | null = null;
    let reconnectTimer: number | null = null;
    let pendingScrollToBottom = false;
    let pendingRestoreScroll: { top: number; height: number } | null = null;
    let pendingComposerFocus = false;

    function convoBodyEl() {
        return document.querySelector('#inbox-app .inbox-convo-body') as HTMLElement | null;
    }

    function composerEl() {
        return document.querySelector('#inbox-app .inbox-convo-post-text') as HTMLTextAreaElement | null;
    }

    function enhanceConvoBody(el: HTMLElement) {
        expandInboxGameEmbeds(el);
        makeExternalLinkPopups(el, { selector: ".inbox-msg.their a[href^='http']" });
        window.requestAnimationFrame(() => expandInboxGameEmbeds(el));
    }

    function redraw() {
        appEl = patch(appEl, render());
        const convoBody = convoBodyEl();
        if (convoBody && pendingRestoreScroll) {
            const { top, height } = pendingRestoreScroll;
            convoBody.scrollTop = convoBody.scrollHeight - height + top;
            pendingRestoreScroll = null;
        } else if (convoBody && pendingScrollToBottom) {
            convoBody.scrollTop = convoBody.scrollHeight;
            pendingScrollToBottom = false;
        }

        if (pendingComposerFocus) {
            const composer = composerEl();
            if (composer && !composer.disabled) {
                composer.focus();
                const cursor = composer.value.length;
                composer.setSelectionRange(cursor, cursor);
                pendingComposerFocus = false;
            }
        }
    }

    function selectedThread() {
        return threads.find(thread => thread.user === contact);
    }

    function loadThreads(selectFirstWhenEmpty = true) {
        fetch('/api/inbox/threads')
            .then(parseJsonResponse)
            .then(({ status, data }: { status: number; data: { threads?: ThreadSummary[] } & InboxApiError }) => {
                if (status >= 400) {
                    throw new Error(inboxApiErrorMessage(data, `HTTP ${status}`));
                }
                const payload = data;
                threads = payload.threads || [];
                if (selectFirstWhenEmpty && !contact && threads.length > 0) {
                    contact = threads[0].user;
                    openThread(contact);
                    return;
                }
                if (!contact || threads.length === 0) loading = false;
                redraw();
            })
            .catch(err => {
                console.warn('Failed to load inbox threads.', err);
                loading = false;
                redraw();
            });
    }

    function loadBlockedUsers() {
        fetch('/api/blocks')
            .then(parseJsonResponse)
            .then(({ status, data }: { status: number; data: { blocks?: string[] } }) => {
                if (status >= 400) return;
                blockedUsers = new Set((data.blocks || []).filter(Boolean));
                contactBlocked = blockedUsers.has(contact);
                redraw();
            })
            .catch(err => console.warn('Failed to load blocked users.', err));
    }

    function openThread(user: string, before?: number, loadingOlder = false) {
        if (!user) return;
        if (!loadingOlder) loading = true;
        redraw();

        const query = before ? `?before=${before}` : '';
        fetch(`/api/inbox/thread/${encodeURIComponent(user)}${query}`)
            .then(parseJsonResponse)
            .then(
                async ({ status, data }: { status: number; data: ThreadResponse & InboxApiError }) => {
                    if (status >= 400 || data.type === 'error') {
                        if (data.code === 'invalid_contact' || data.message === 'Invalid contact') {
                            contact = '';
                            contactTitle = '';
                            contactOnline = false;
                            contactPatron = false;
                            contactSystem = false;
                            contactCanMessage = true;
                            contactBlocked = false;
                            contactBlockedByThem = false;
                            messages = [];
                            hasMoreMessages = false;
                            loadingMore = false;
                            loading = false;
                            history.replaceState({}, '', '/inbox');
                            redraw();
                            return;
                        }
                        void alertDialog({ text: inboxApiErrorMessage(data, _('Could not open conversation.')) });
                        loadingMore = false;
                        loading = false;
                        redraw();
                        return;
                    }

                    if (loadingOlder) {
                        messages = (data.messages || []).concat(messages);
                    } else {
                        contact = data.contact.name;
                        contactTitle = data.contact.title || '';
                        contactOnline = Boolean(data.contact.online);
                        contactPatron = Boolean(data.contact.patron);
                        contactSystem = Boolean(data.contact.system);
                        contactCanMessage = data.contact.canMessage !== false;
                        contactBlocked = Boolean(data.contact.blockedByMe);
                        contactBlockedByThem = Boolean(data.contact.blockedByThem);
                        messages = data.messages || [];
                        history.replaceState({ contact }, '', `/inbox/${encodeURIComponent(contact)}`);
                        const readResponse = await fetch(`/api/inbox/thread/${encodeURIComponent(contact)}/read`, {
                            method: 'POST',
                        });
                        if (!readResponse.ok) throw new Error(`HTTP ${readResponse.status}`);
                        loadThreads(false);
                        pendingScrollToBottom = true;
                    }

                    hasMoreMessages = Boolean(data.hasMore);
                    loadingMore = false;
                    loading = false;
                    redraw();
                },
            )
            .catch(err => {
                console.warn('Failed to load inbox thread.', err);
                loadingMore = false;
                loading = false;
                redraw();
            });
    }

    function loadOlderMessages() {
        if (!contact || loadingMore || !hasMoreMessages || messages.length === 0) return;
        const oldestDate = parseDate(messages[0].createdAt);
        if (!oldestDate) return;

        const convoBody = convoBodyEl();
        if (convoBody) {
            pendingRestoreScroll = {
                top: convoBody.scrollTop,
                height: convoBody.scrollHeight,
            };
        }

        loadingMore = true;
        redraw();
        openThread(contact, oldestDate.getTime(), true);
    }

    function sendMessage() {
        const text = draft.trim();
        if (!contact || !text || sending) return;

        sending = true;
        redraw();

        const formData = new URLSearchParams({ text });
        fetch(`/api/inbox/thread/${encodeURIComponent(contact)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
            body: formData.toString(),
        })
            .then(parseJsonResponse)
            .then(({ status, data }) => {
                if (status >= 400 || data.type === 'error') {
                    void alertDialog({ text: inboxApiErrorMessage(data, _('Could not send message.')) });
                    return;
                }

                draft = '';
                pendingScrollToBottom = true;
                pendingComposerFocus = true;
                openThread(contact);
            })
            .catch(err => {
                console.warn('Failed to send inbox message.', err);
                void alertDialog({ text: _('Could not send message.') });
                pendingComposerFocus = true;
            })
            .finally(() => {
                sending = false;
                redraw();
            });
    }

    function toggleBlock() {
        if (!contact) return;
        const nextBlocked = !contactBlocked;
        const formData = new URLSearchParams({ block: `${nextBlocked}` });
        fetch(`/api/${encodeURIComponent(contact)}/block`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
            body: formData.toString(),
        })
            .then(parseJsonResponse)
            .then(({ status }) => {
                if (status >= 400) {
                    void alertDialog({ text: _('Could not update block state.') });
                    return;
                }
                contactBlocked = nextBlocked;
                if (nextBlocked) contactCanMessage = false;
                else if (!contactBlockedByThem) contactCanMessage = true;
                if (nextBlocked) blockedUsers.add(contact);
                else blockedUsers.delete(contact);
                redraw();
            })
            .catch(err => {
                console.warn('Failed to update block state.', err);
                void alertDialog({ text: _('Could not update block state.') });
            });
    }

    async function deleteConversation() {
        if (!contact) return;
        const targetContact = contact;
        const confirmed = await confirmDialog({
            text: _('Delete conversation?'),
            confirmText: _('Delete'),
            cancelText: _('Cancel'),
            danger: true,
        });
        if (!confirmed) return;

        fetch(`/api/inbox/thread/${encodeURIComponent(targetContact)}/delete`, {
            method: 'POST',
        })
            .then(parseJsonResponse)
            .then(({ status, data }: { status: number; data: InboxApiError }) => {
                if (status >= 400 || data.type === 'error') {
                    void alertDialog({ text: inboxApiErrorMessage(data, _('Could not delete conversation.')) });
                    return;
                }

                threads = threads.filter(t => t.user !== targetContact);
                if (contact === targetContact) {
                    messages = [];
                    contact = '';
                    contactTitle = '';
                    contactOnline = false;
                    contactPatron = false;
                    contactSystem = false;
                    loading = false;
                    history.replaceState({}, '', '/inbox');
                }
                loadThreads(true);
                redraw();
            })
            .catch(err => {
                console.warn('Failed to delete conversation.', err);
                void alertDialog({ text: _('Could not delete conversation.') });
            });
    }

    function connectInbox() {
        if (evtSource !== null) evtSource.close();
        evtSource = new EventSource('/inbox/subscribe');
        evtSource.onmessage = (event: MessageEvent) => {
            const payload = JSON.parse(event.data) as { unread: number; thread?: string };
            if (payload.thread) {
                if (payload.thread === contact) openThread(contact);
                else loadThreads(false);
            } else {
                loadThreads(false);
            }
        };
        evtSource.onerror = function () {
            if (evtSource !== null) {
                evtSource.close();
                evtSource = null;
            }
            if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
            reconnectTimer = window.setTimeout(() => {
                reconnectTimer = null;
                connectInbox();
            }, 1500);
        };
    }

    function renderThreadItem(thread: ThreadSummary) {
        const isSelected = thread.user === contact;
        const statusClass = thread.system
            ? '.system'
            : `${thread.online ? '.online' : ''}${thread.patron ? '.patron.icon-patron-wing' : ''}`;
        return h(
            `button.inbox-thread${isSelected ? '.active' : ''}${thread.unread ? '.unread' : ''}`,
            {
                props: { type: 'button' },
                on: { click: () => openThread(thread.user) },
            },
            [
                h('div.inbox-thread-head', [
                    h(
                        `strong.inbox-user${statusClass}`,
                        { attrs: thread.patron ? { title: _('PyChess Patron') } : {} },
                        titleAndName(thread.title, thread.user),
                    ),
                    h('span.inbox-thread-date', timeago(thread.lastMsg?.createdAt || thread.updatedAt)),
                ]),
                h('div.inbox-thread-body', thread.lastMsg?.text || ''),
            ],
        );
    }

    function renderMessage(msg: Message) {
        const mine = msg.from === model.username;
        const createdAt = parseDate(msg.createdAt);
        const textNodes = renderRichText(msg.text);
        return h(`div.inbox-msg${mine ? '.mine' : '.their'}`, [
            h('span.inbox-msg-text', textNodes),
            h(
                'em.inbox-msg-time',
                {
                    attrs: {
                        title: createdAt ? createdAt.toLocaleString() : '',
                    },
                },
                renderClockTime(msg.createdAt),
            ),
        ]);
    }

    function renderMessagesWithDates(msgs: Message[]) {
        const nodes: VNode[] = [];
        let lastDate: Date | null = null;

        msgs.forEach(msg => {
            const date = parseDate(msg.createdAt);
            if (date !== null && (lastDate === null || !sameDay(lastDate, date))) {
                nodes.push(h('div.inbox-day', renderDayLabel(date)));
                lastDate = date;
            }
            nodes.push(renderMessage(msg));
        });

        return nodes;
    }

    function render() {
        const thread = selectedThread();
        const hasContact = Boolean(thread || contact);
        const challengeHref = hasContact ? `/@/${encodeURIComponent(contact)}/challenge` : '#';
        const challengeBlocked = contactBlocked || contactBlockedByThem;
        const reportHref = hasContact
            ? `/report?source=inbox&username=${encodeURIComponent(contact)}&reason=harassment&thread=${encodeURIComponent(reportThreadId(model.username, contact))}`
            : '#';
        const convoBodyNodes: (VNode | null)[] = [];
        if (hasMoreMessages) {
            convoBodyNodes.push(
                h(
                    'button.inbox-load-more.button.button-empty',
                    {
                        props: { type: 'button', disabled: loadingMore },
                        on: { click: loadOlderMessages },
                    },
                    loadingMore ? _('Loading...') : _('Load more'),
                ),
            );
        }
        if (messages.length) {
            convoBodyNodes.push(...renderMessagesWithDates(messages));
        } else {
            convoBodyNodes.push(h('div.inbox-empty', _('No messages yet.')));
        }
        return h('main#inbox-app.inbox.box.inbox-app', [
            h('section.inbox-side', [
                h('div.inbox-side-head', [h('h2', _('Inbox'))]),
                h('div.inbox-side-compose', [
                    h('input', {
                        attrs: { type: 'text', placeholder: _('Type username and press Enter') },
                        props: { value: contact },
                        on: {
                            input: (e: Event) => {
                                contact = (e.target as HTMLInputElement).value.trim();
                            },
                            keypress: (e: KeyboardEvent) => {
                                if (e.key === 'Enter' && contact) openThread(contact);
                            },
                        },
                    }),
                ]),
                h(
                    'div.inbox-thread-list',
                    threads.length ? threads.map(renderThreadItem) : [h('div.inbox-empty', _('No conversations yet.'))],
                ),
            ]),
            h('section.inbox-convo', [
                h('div.inbox-convo-head', [
                    thread
                        ? h('h2', [
                              contactSystem
                                  ? h('span.inbox-user.system', thread.user)
                                  : h(
                                        `a.user-link.ulpt.inbox-user${contactOnline ? '.online' : ''}${
                                            contactPatron ? '.patron.icon-patron-wing' : ''
                                        }`,
                                        {
                                            attrs: {
                                                href: `/@/${encodeURIComponent(thread.user)}`,
                                                ...(contactPatron ? { title: _('PyChess Patron') } : {}),
                                            },
                                        },
                                        titleAndName(thread.title || contactTitle, thread.user),
                                    ),
                          ])
                        : h('h2', _('Select a conversation')),
                    h(
                        'div.inbox-convo-actions',
                        hasContact && !contactSystem
                            ? [
                                  ...(challengeBlocked
                                      ? []
                                      : [
                                            h('a.inbox-action.icon.icon-crossedswords', {
                                                attrs: { href: challengeHref, title: _('Challenge') },
                                            }),
                                        ]),
                                  h('button.inbox-action.icon.icon-ban', {
                                      props: { type: 'button' },
                                      attrs: { title: contactBlocked ? _('Unblock') : _('Block') },
                                      on: { click: toggleBlock },
                                  }),
                                  h('button.inbox-action.icon.icon-trash-o', {
                                      props: { type: 'button' },
                                      attrs: { title: _('Delete') },
                                      on: { click: deleteConversation },
                                  }),
                                  h('a.inbox-action.icon.icon-warning', {
                                      attrs: { href: reportHref, title: _('Report to moderators') },
                                  }),
                              ]
                            : [],
                    ),
                ]),
                h(
                    'div.inbox-convo-body',
                    {
                        hook: {
                            insert(vnode) {
                                enhanceConvoBody(vnode.elm as HTMLElement);
                            },
                            postpatch(_oldVnode, vnode) {
                                enhanceConvoBody(vnode.elm as HTMLElement);
                            },
                        },
                    },
                    loading ? h('div.inbox-empty', _('Loading...')) : (convoBodyNodes.filter(Boolean) as VNode[]),
                ),
                contactSystem
                    ? h('div.inbox-convo-readonly', _("PyChess doesn't accept new messages."))
                    : h(
                          'form.inbox-convo-post',
                          {
                              on: {
                                  submit: (event: Event) => {
                                      event.preventDefault();
                                      sendMessage();
                                  },
                              },
                          },
                          [
                              h('textarea.inbox-convo-post-text', {
                                  attrs: {
                                      // The server keeps existing conversation access visible, but can
                                      // still lock composing if the recipient only accepts friend PMs.
                                      placeholder: !contact
                                          ? _('Select a conversation first')
                                          : contactBlocked || contactBlockedByThem
                                            ? _('This conversation is blocked')
                                            : contactCanMessage
                                              ? _('Write a message...')
                                              : _('This user only accepts messages from friends'),
                                      rows: 1,
                                      enterkeyhint: 'send',
                                      disabled: !contact || sending || !contactCanMessage,
                                  },
                                  props: { value: draft },
                                  on: {
                                      input: (e: Event) => {
                                          draft = (e.target as HTMLTextAreaElement).value;
                                          redraw();
                                      },
                                      keydown: (e: KeyboardEvent) => {
                                          if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
                                              e.preventDefault();
                                              sendMessage();
                                          }
                                      },
                                  },
                              }),
                              h(
                                  'button.inbox-convo-post-submit.button',
                                  {
                                      props: {
                                          type: 'submit',
                                          disabled: !contact || sending || !contactCanMessage || !draft.trim(),
                                      },
                                  },
                                  sending ? _('Sending...') : _('Send'),
                              ),
                          ],
                      ),
            ]),
        ]);
    }

    setTimeout(() => {
        appEl = document.getElementById('inbox-app') as HTMLElement;
        loadBlockedUsers();
        if (contact) openThread(contact);
        loadThreads(!contact);
        connectInbox();
    }, 0);

    return h('main#inbox-app.inbox.box.inbox-app');
}
