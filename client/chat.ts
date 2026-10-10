import { h } from 'snabbdom';

import { _ } from './i18n';
import { patch } from './document';
import { selfReport, shouldSkipMessage } from './chatSpam';
import { displayUsername, isAnonUsername } from './user';
import { linkifyNodes } from './linkify';

export interface ChatController {
    anon: boolean;
    doSend: any;
    spectator?: boolean;
    gameId?: string;
    tournamentId?: string;
    simulId?: string;
}

// ------ Deterministic color assignment for usernames, theme-aware ------
function getThemeColorParams(): { s: number; lBase: number; lMod: number } {
    const theme = document.body?.dataset?.theme;
    if (theme === 'dark') {
        return { s: 60, lBase: 50, lMod: 10 };
    } else {
        return { s: 70, lBase: 60, lMod: 10 };
    }
}

/**
 * Returns a mapping from username to HSL color, deterministically assigned by
 * alphabetical order and spaced evenly around the color wheel.
 * Saturation and lightness are chosen based on theme and username length.
 */
function assignUsernameColors(usernames: string[]): Record<string, string> {
    const { s, lBase, lMod } = getThemeColorParams();
    const sorted = [...usernames].sort((a, b) => a.localeCompare(b));
    const total = sorted.length;
    const colors: Record<string, string> = {};
    for (let i = 0; i < total; ++i) {
        const name = sorted[i];
        if (!userColorMap[name]) {
            const lightness = lBase + (name.length % lMod);
            const hue = Math.round(((i + 1) * 360) / (total + 1));
            colors[name] = `hsl(${hue} ${s} ${lightness})`;
            userColorMap[name] = colors[name];
        } else {
            colors[name] = userColorMap[name];
        }
    }
    return colors;
}

// Stores all seen usernames for color assignment (session-based)
const activeUsernames = new Set<string>();
const userColorMap: { [username: string]: string } = {};

// The one definition of what sending a chat message is: self-report it, then hand
// the envelope to the controller. Exported because the bughouse preset buttons send
// too, and they live outside this view — see two-board/round/chatPresets.ts. They
// must use THIS, not their own copy: a second envelope would drift, and selfReport
// is easy to leave out.
export function chatSender(ctrl: ChatController, chatType: string): (message: string) => void {
    const spectator = 'spectator' in ctrl && ctrl.spectator;
    return (message: string) => {
        selfReport(message);
        const m: any = { type: chatType, message: message, room: spectator ? 'spectator' : 'player' };
        if ('gameId' in ctrl) m['gameId'] = ctrl.gameId;
        if ('tournamentId' in ctrl) m['tournamentId'] = ctrl.tournamentId;
        // Carried over from upstream when this function was extracted out of chatView():
        // simul chat routes on this id, and dropping it would have silently broken simul
        // chat for the sake of a refactor that was only meant to move code.
        if ('simulId' in ctrl) m['simulId'] = ctrl.simulId;
        ctrl.doSend(m);
    };
}

export interface ChatViewOptions {
    /** Render the chat header: the room label and the chat on/off toggle.
        Defaults to true. A chat with no room concept and no toggle passes false
        and gets NO header element — not an empty one. The bughouse round page
        used to receive an empty `div.chatroom`, which drew nothing and cost the
        message list 14px of padding in landscape and 12.15px in portrait. */
    chatHeader?: boolean;
}

export function chatView(ctrl: ChatController, chatType: string, opts: ChatViewOptions = {}) {
    const spectator = 'spectator' in ctrl && ctrl.spectator;
    const chatHeader = opts.chatHeader ?? true;
    function onKeyPress(e: KeyboardEvent) {
        const cb = <HTMLInputElement>document.getElementById('checkbox');
        if (cb && !cb.checked) return;
        const message = (e.target as HTMLInputElement).value.trim();
        if ((e.keyCode === 13 || e.which === 13) && message.length > 0) {
            sendMessage(message);
            (e.target as HTMLInputElement).value = '';
        }
    }
    const sendMessage = chatSender(ctrl, chatType);
    function onClick() {
        const activated = (<HTMLInputElement>document.getElementById('checkbox')).checked;
        const chatEntry = <HTMLInputElement>document.getElementById('chat-entry');
        (<HTMLElement>document.getElementById(chatType + '-messages')).style.display = activated ? 'block' : 'none';
        chatEntry.disabled = !activated;
        chatEntry.placeholder = activated
            ? ctrl.anon
                ? _('Sign in to chat')
                : _('Please be nice in the chat!')
            : _('Chat is disabled');
    }
    return h(`div#${chatType}.${chatType}.chat`, [
        chatHeader
            ? h('div.chatroom', [
                  spectator ? _('Spectator room') : _('Chat room'),
                  h('input#checkbox', {
                      props: { title: _('Toggle the chat'), name: 'checkbox', type: 'checkbox', checked: 'true' },
                      on: { click: onClick },
                  }),
              ])
            : null,
        // A list a reader can step through, whose new messages are read out when the reader is
        // free, as lichess does. The inner div only collects the items, so it is no list level.
        h(`ol#${chatType}-messages`, { attrs: { 'aria-live': 'polite', 'aria-relevant': 'additions' } }, [
            h('div#messages', { attrs: { role: 'none' } }),
        ]),
        h('input#chat-entry', {
            props: {
                type: 'text',
                name: 'entry',
                autocomplete: 'off',
                placeholder: ctrl.anon ? _('Sign in to chat') : _('Please be nice in the chat!'),
                disabled: ctrl.anon,
            },
            attrs: {
                maxlength: 140,
                // autofocus: "true",
                'aria-label': _('Chat'),
            },
            on: { keypress: onKeyPress },
        }),
    ]);
}

// `ply` and `ctrl: RoundControllerBughouse` used to trail this signature, so that a
// message could be titled with the SAN of the move it was said at and click through
// to that ply. Both were DEAD. The only callers that passed them passed `user: ''`,
// which takes the first branch below and reads neither — and the decoration lived in
// the last branch, reachable only for a real username, which no caller ever combined
// with a controller. The live implementation of that feature is chatMessageBug() in
// two-board/round/chat.ts, which builds its own SAN element and click handlers.
//
// Removing them takes the last bughouse dependency out of this shared module, and
// takes the `undefined` padding out of its callers: the bughouse call sites read
//     chatMessage('', '…', 'bugroundchat', undefined, idx, this)
// where the `undefined` only existed to step over a `time` they had no value for on
// the way to arguments that were never read.
/** Chat history resent on load or reconnect is not news: the list stays silent while it refills. */
export function replayingChat(chatType: string): void {
    const list = document.getElementById(chatType + '-messages');
    if (!list) return;
    list.setAttribute('aria-live', 'off');
    setTimeout(() => list.setAttribute('aria-live', 'polite'), 1000);
}

export function chatMessage(user: string, message: string, chatType: string, time?: number) {
    if (shouldSkipMessage(message)) return;

    // when the first duck placement starts, DuckInput.start() calls:
    // chatMessage('', _('Place the duck on an empty square.'), "roundchat");
    // But standalone /analysis/duck has no round chat DOM.
    const chatDiv = document.getElementById(chatType + '-messages') as HTMLElement | null;
    const container = document.getElementById('messages') as HTMLElement | null;
    if (!chatDiv || !container) return;

    const isBottom = chatDiv.scrollHeight - (chatDiv.scrollTop + chatDiv.offsetHeight) < 80;
    const localTime = time
        ? new Date(time * 1000).toLocaleTimeString('default', { hour: '2-digit', minute: '2-digit', hour12: false })
        : '';
    const isAnon = isAnonUsername(user);
    const displayUser = displayUsername(user);
    const messageNodes = linkifyNodes(message, 'chat-message-link');

    // Update active usernames set
    if (user.length && user !== '_server') {
        activeUsernames.add(displayUser);
    }
    // Get color mapping
    const usernameColorMap = assignUsernameColors(Array.from(activeUsernames));

    if (user.length === 0) {
        patch(container, h('div#messages', [h('li.message.offer', [h('t', messageNodes)])]));
    } else if (user === '_server') {
        patch(
            container,
            h('div#messages', [
                h('li.message.server', [h('div.time', localTime), h('user', _('Server')), h('t', messageNodes)]),
            ]),
        );
    } else {
        const userNode = isAnon
            ? h('span', { style: { color: usernameColorMap[displayUser] || '#aaa' } }, displayUser)
            : h(
                  'a',
                  {
                      attrs: { href: '/@/' + user },
                      class: { 'user-link': true },
                      style: { color: usernameColorMap[displayUser] || '#aaa' },
                  },
                  displayUser,
              );
        patch(
            container,
            h('div#messages', [
                h('li.message', [
                    h('div.time', localTime),
                    h('user', [userNode]),
                    h('t', messageNodes),
                ]),
            ]),
        );
    }

    if (isBottom)
        setTimeout(() => {
            chatDiv.scrollTop = chatDiv.scrollHeight;
        }, 200);
}
