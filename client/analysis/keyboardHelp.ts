import { h, type VNode } from 'snabbdom';

import { _ } from '../i18n';
import { patch } from '../document';
import type { AnalysisController } from './analysisCtrl';
import { buildKeyboardMoveSections } from '../gameKeyboardHelp';

interface ShortcutItem {
    keys: string[];
    description: string;
}

interface ShortcutSection {
    title: string;
    items: ShortcutItem[];
}

let keyboardHelpVNode: VNode | null = null;
// What had focus when the dialog opened, given back when it closes.
let returnFocus: HTMLElement | null = null;

export function isKeyboardHelpShortcut(event: KeyboardEvent) {
    return event.key === '?' || (event.key === '/' && event.shiftKey);
}

// Whole names only, per part of a combination: the move input's words ("upv", "downv") are keys too.
function formatKeyLabel(key: string) {
    const names: Record<string, string> = {
        left: _('Left arrow'),
        right: _('Right arrow'),
        up: _('Up arrow'),
        down: _('Down arrow'),
        home: _('Home'),
        end: _('End'),
        shift: _('Shift'),
        enter: _('Enter'),
        space: _('Space'),
        escape: _('Escape'),
    };
    return key
        .split('+')
        .map(part => names[part] ?? part)
        .join('+');
}

function renderKey(key: string): VNode {
    return h('kbd', formatKeyLabel(key));
}

function renderKeys(keys: string[]): VNode {
    return h(
        'div.keys',
        keys.flatMap((key, index) => (index === 0 ? [renderKey(key)] : [h('span.sep', _('or')), renderKey(key)])),
    );
}

export function buildKeyboardHelpSections(ctrl: AnalysisController): ShortcutSection[] {
    const sections: ShortcutSection[] = [
        {
            title: _('Navigation'),
            items: [
                { keys: ['left'], description: _('Previous move') },
                { keys: ['right'], description: _('Next move') },
                { keys: ['up', 'home', '0'], description: _('First move') },
                { keys: ['down', 'end', '$'], description: _('Last move') },
                { keys: ['shift+left'], description: _('Previous variation') },
                { keys: ['shift+right'], description: _('Next variation') },
                { keys: ['shift+up'], description: _('Start of variation') },
                { keys: ['shift+down'], description: _('End of variation') },
            ],
        },
        {
            title: _('Board'),
            items: [
                { keys: ['f'], description: _('Flip board') },
                { keys: ['p'], description: _('Copy position reference') },
                { keys: ['?'], description: _('Show keyboard shortcuts') },
            ],
        },
    ];

    if (ctrl.variant.rules.gate || ctrl.variant.name === 'duck' || ctrl.variant.name === 'supply') {
        sections.push({
            title: _('Input'),
            items: [{ keys: ['enter'], description: _('Confirm current move input') }],
        });
    }

    sections.push(...buildKeyboardMoveSections(ctrl));
    return sections;
}

function view(ctrl: AnalysisController): VNode {
    const sections = buildKeyboardHelpSections(ctrl);

    return h(
        'div.analysis-keyboard-help',
        {
            attrs: {
                role: 'dialog',
                'aria-modal': 'true',
                'aria-labelledby': 'analysis-keyboard-help-title',
            },
            on: {
                click: (event: MouseEvent) => {
                    if (event.target === event.currentTarget) ctrl.closeKeyboardHelp();
                },
            },
        },
        [
            h('div.analysis-keyboard-help__content', [
                h('div.analysis-keyboard-help__header', [
                    h('h2#analysis-keyboard-help-title', _('Keyboard shortcuts')),
                    h(
                        'button.analysis-keyboard-help__close',
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
                    'div.analysis-keyboard-help__grid',
                    sections.map(section =>
                        h('section.analysis-keyboard-help__section', [
                            h('h3', section.title),
                            h('table', [
                                h(
                                    'tbody',
                                    section.items.map(item =>
                                        h('tr', [
                                            h('td.keys-cell', renderKeys(item.keys)),
                                            h('td.description-cell', item.description),
                                        ]),
                                    ),
                                ),
                            ]),
                        ]),
                    ),
                ),
            ]),
        ],
    );
}

function ensureContainer() {
    let element = document.getElementById('analysis-keyboard-help');
    if (!element) {
        element = document.createElement('div');
        element.id = 'analysis-keyboard-help';
        document.body.appendChild(element);
    }
    element.style.display = 'flex';
    return element;
}

export function showKeyboardHelp(ctrl: AnalysisController) {
    const container = ensureContainer();
    const vnode = view(ctrl);

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

export function hideKeyboardHelp() {
    const container = document.getElementById('analysis-keyboard-help');
    if (container) container.style.display = 'none';
    keyboardHelpVNode = null;
    returnFocus?.focus();
    returnFocus = null;
}
