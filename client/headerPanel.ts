import { toVNode, type VNode } from 'snabbdom';

import { patch } from './document';

function removeFormattingWhitespace(node: Node): void {
    Array.from(node.childNodes).forEach(child => {
        if (child.nodeType === Node.TEXT_NODE && !child.textContent?.trim()) child.remove();
        else removeFormattingWhitespace(child);
    });
}

/**
 * Upgrade a server-rendered header panel without replacing its stable controls.
 *
 * The header button shells are present in the initial HTML to avoid a flash of
 * missing controls during full-page navigation. Jinja indentation produces
 * whitespace text nodes that are absent from the client VNodes, so discard only
 * that formatting whitespace before converting the live DOM for Snabbdom.
 */
export function hydrateHeaderPanel(panel: HTMLElement, view: VNode): HTMLElement {
    removeFormattingWhitespace(panel);
    return patch(toVNode(panel), view).elm as HTMLElement;
}

/**
 * Opens or closes a header panel's button: the `shown` class and `aria-expanded` always change
 * together. The buttons are never re-patched, so a later render does not undo the attribute.
 */
export function setHeaderPanelExpanded(buttonId: string, open: boolean): void {
    const button = document.getElementById(buttonId);
    if (button === null) return;
    button.classList.toggle('shown', open);
    button.setAttribute('aria-expanded', String(open));
}

/** What closing a header dropdown needs to know; opening stays with each control. */
export interface HeaderDropdown {
    root: Element; // a click inside it does not close it
    button: HTMLElement; // focus returns here on Escape
    isOpen: () => boolean;
    close: () => void;
}

const dropdowns: HeaderDropdown[] = [];

/**
 * One dismissal for every header dropdown — the nav menus, the login chooser and the Settings,
 * Notifications and Challenges panels: a click outside closes it, and Escape closes it and hands
 * focus back to its button.
 */
export function registerHeaderDropdown(dropdown: HeaderDropdown): void {
    if (dropdowns.length === 0) {
        document.addEventListener('click', e => {
            const target = e.target as Node;
            dropdowns.forEach(d => {
                if (d.isOpen() && !d.root.contains(target)) d.close();
            });
        });
        document.addEventListener('keydown', e => {
            if (e.key !== 'Escape') return;
            const open = dropdowns.filter(d => d.isOpen());
            open.forEach(d => d.close());
            open[open.length - 1]?.button.focus();
        });
    }
    dropdowns.push(dropdown);
}
