import { h, VNode } from 'snabbdom';

/** A heading for screen readers to jump to, hidden because the page already shows what it names. */
export function srHeading(level: 'h1' | 'h2' | 'h3', text: string): VNode {
    return h(`${level}.sr-only`, text);
}

/** The page's h1: the title the server composed for the tab ("Crazyhouse • Alice vs Bob"). */
export function pageHeading(): VNode {
    return srHeading('h1', document.title.replace(/ • PyChess$/, ''));
}
