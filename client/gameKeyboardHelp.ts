import { h, type VNode } from 'snabbdom';
import type * as cg from 'chessgroundx/types';

import { _ } from './i18n';
import { patch } from './document';
import type { Variant } from './variants';
import { POCKET_HOTKEYS } from './pocketHotkeys';
import type { KeyboardMove, KeyboardMoveCommands } from './accessibility/keyboardMove';

interface ShortcutItem {
    keys: string[];
    description: string;
    compactKeys?: boolean;
}

interface ShortcutSection {
    title: string;
    items: ShortcutItem[];
    wide?: boolean;
}

export interface GameKeyboardHelpHost {
    closeKeyboardHelp(): void;
    variant: Variant;
    pocketHotkeyRoles?: readonly cg.Role[];
    keyboardMove?: KeyboardMove;
    keyboardMoveCommands?(): KeyboardMoveCommands;
}

let keyboardHelpVNode: VNode | null = null;
// What had focus when the dialog opened, given back when it closes.
let returnFocus: HTMLElement | null = null;

export function isKeyboardHelpShortcut(event: KeyboardEvent) {
    return event.key === '?' || (event.key === '/' && event.shiftKey);
}

// Whole names only: the move input's words ("upv", "downv") are keys too.
function formatKeyLabel(key: string) {
    const names: Record<string, string> = {
        left: _('Left arrow'),
        right: _('Right arrow'),
        up: _('Up arrow'),
        down: _('Down arrow'),
        enter: _('Enter'),
        escape: _('Escape'),
    };
    return names[key] ?? key;
}

function renderKey(key: string): VNode {
    return h('kbd', formatKeyLabel(key));
}

function renderKeys(keys: string[], compact = false): VNode {
    return h(
        compact ? 'div.keys.compact' : 'div.keys',
        compact
            ? keys.map(renderKey)
            : keys.flatMap((key, index) =>
                  index === 0 ? [renderKey(key)] : [h('span.sep', _('or')), renderKey(key)],
              ),
    );
}

function buildPocketShortcutSection(ctrl: GameKeyboardHelpHost): ShortcutSection | null {
    const roles = ctrl.pocketHotkeyRoles;
    if (!roles?.length) return null;

    return {
        title: _('Drops'),
        wide: true,
        items: [
            {
                keys: POCKET_HOTKEYS.slice(0, roles.length),
                description: _('Select pocket piece by position'),
                compactKeys: true,
            },
        ],
    };
}

// Lichess's help for its keyboard move input, when this page shows one: the moves, with an example
// from the current position so that it is in the variant's own notation, and the page's words.
export function buildKeyboardMoveSections(ctrl: GameKeyboardHelpHost): ShortcutSection[] {
    if (!ctrl.keyboardMove?.active()) return [];
    const [san, uci] = ctrl.keyboardMove.example() ?? ['Nc3', 'b1c3'];
    const words: Record<string, string> = {
        clock: _('Read out the clocks'),
        who: _("Read out the opponent's name"),
        draw: _('Offer a draw'),
        resign: _('Resign'),
        zerk: _('Berserk'),
        next: _('Next puzzle'),
        upv: _('Vote up'),
        downv: _('Vote down'),
    };
    const offered = Object.keys(ctrl.keyboardMoveCommands?.() ?? {});
    return [
        {
            title: _('Typing moves'),
            items: [
                { keys: ['m'], description: _('Focus the move input') },
                { keys: [san, uci], description: _('Play a move, as the move list writes it or by its squares') },
                { keys: ['enter'], description: _('Play the move typed so far, or confirm a correspondence move') },
                { keys: ['escape'], description: _('Leave the move input') },
            ],
        },
        {
            title: _('Typing commands'),
            items: [
                ...offered.map(word => ({ keys: [word], description: words[word] })),
                ...(document.getElementById('chat-entry') ? [{ keys: ['/'], description: _('Focus the chat') }] : []),
                { keys: ['help', '?'], description: _('Show keyboard shortcuts') },
            ],
        },
    ];
}

export function buildGameKeyboardHelpSections(
    ctrl: GameKeyboardHelpHost,
    options: { flipDescription?: string } = {},
): ShortcutSection[] {
    const sections: ShortcutSection[] = [
        {
            title: _('Navigation'),
            items: [
                { keys: ['left'], description: _('Previous move') },
                { keys: ['right'], description: _('Next move') },
                { keys: ['up'], description: _('First move') },
                { keys: ['down'], description: _('Last move') },
            ],
        },
        {
            title: _('Board'),
            items: [
                { keys: ['f'], description: options.flipDescription || _('Flip board') },
                ...(ctrl.variant.name === 'alice' ? [{ keys: ['s'], description: _('Split boards') }] : []),
                { keys: ['?'], description: _('Show keyboard shortcuts') },
            ],
        },
    ];

    const pocketShortcutSection = buildPocketShortcutSection(ctrl);
    if (pocketShortcutSection) sections.push(pocketShortcutSection);

    if (ctrl.variant.rules.gate || ctrl.variant.name === 'duck' || ctrl.variant.name === 'supply') {
        sections.push({
            title: _('Input'),
            items: [{ keys: ['enter'], description: _('Confirm current move input') }],
        });
    }

    sections.push(...buildKeyboardMoveSections(ctrl));
    return sections;
}

function view(ctrl: GameKeyboardHelpHost, sections: ShortcutSection[]): VNode {
    return h(
        'div.keyboard-help',
        {
            attrs: {
                role: 'dialog',
                'aria-modal': 'true',
                'aria-labelledby': 'keyboard-help-title',
            },
            on: {
                click: (event: MouseEvent) => {
                    if (event.target === event.currentTarget) ctrl.closeKeyboardHelp();
                },
            },
        },
        [
            h('div.keyboard-help__content', [
                h('div.keyboard-help__header', [
                    h('h2#keyboard-help-title', _('Keyboard shortcuts')),
                    h(
                        'button.keyboard-help__close',
                        {
                            attrs: { type: 'button', 'aria-label': _('Close') },
                            on: { click: () => ctrl.closeKeyboardHelp() },
                            hook: {
                                insert: vnode => {
                                    (vnode.elm as HTMLButtonElement).focus();
                                },
                            },
                        },
                        '×',
                    ),
                ]),
                h(
                    'div.keyboard-help__grid',
                    sections.map(section => {
                        const selector = section.wide
                            ? 'section.keyboard-help__section.keyboard-help__section--wide'
                            : 'section.keyboard-help__section';
                        return h(selector, [
                            h('h3', section.title),
                            h('table', [
                                h(
                                    'tbody',
                                    section.items.map(item =>
                                        h('tr', [
                                            h('td.keys-cell', renderKeys(item.keys, item.compactKeys)),
                                            h('td.description-cell', item.description),
                                        ]),
                                    ),
                                ),
                            ]),
                        ]);
                    }),
                ),
            ]),
        ],
    );
}

function ensureContainer() {
    let element = document.getElementById('keyboard-help');
    if (!element) {
        element = document.createElement('div');
        element.id = 'keyboard-help';
        document.body.appendChild(element);
    }
    element.style.display = 'flex';
    return element;
}

export function showGameKeyboardHelp(ctrl: GameKeyboardHelpHost, sections: ShortcutSection[]) {
    const container = ensureContainer();
    const vnode = view(ctrl, sections);

    if (keyboardHelpVNode === null) {
        returnFocus = document.activeElement as HTMLElement | null;
        container.innerHTML = '';
        const placeholder = document.createElement('div');
        container.appendChild(placeholder);
        keyboardHelpVNode = patch(placeholder, vnode);
    } else {
        keyboardHelpVNode = patch(keyboardHelpVNode, vnode);
    }
}

export function hideGameKeyboardHelp() {
    const container = document.getElementById('keyboard-help');
    if (container) container.style.display = 'none';
    keyboardHelpVNode = null;
    returnFocus?.focus();
    returnFocus = null;
}
