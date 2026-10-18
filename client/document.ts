import { VNode, init, classModule, attributesModule, propsModule, eventListenersModule, styleModule } from 'snabbdom';
import type { Hooks } from 'snabbdom';

import { sanitizeURL } from './url';

export const patch = init([classModule, attributesModule, propsModule, eventListenersModule, styleModule]);

// Open a <dialog> as modal; close() before removal so the browser returns focus to the opener.
export const modalDialogHooks: Hooks = {
    insert: vnode => (vnode.elm as HTMLDialogElement).showModal(),
    destroy: vnode => (vnode.elm as HTMLDialogElement).close(),
};

export function downloadText(filename: string, text: string) {
    const element = document.createElement('a');
    element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(text));
    element.setAttribute('download', filename);

    element.style.display = 'none';
    document.body.appendChild(element);

    element.click();

    document.body.removeChild(element);
}

export function downloadPgnText(filename: string) {
    const text = document.getElementById('pgntext')?.textContent ?? '';
    downloadText(filename, text);
}

export function getDocumentData(name: string): string | null {
    const elm = document.getElementById('pychess-variants');
    if (elm) {
        return elm.getAttribute('data-' + name.toLowerCase());
    } else {
        return null;
    }
}

export function debounce(callback: any, wait: number) {
    let timeout: ReturnType<typeof setTimeout>;
    return function (this: unknown, ...args: unknown[]) {
        clearTimeout(timeout);
        timeout = setTimeout(() => callback.apply(this, args), wait);
    };
}

export function getCookie(name: string) {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
        const pair = cookies[i].trim().split('=');
        if (pair[0] === name) return pair[1];
    }
    return '';
}

export function setCookie(cname: string, cvalue: string, exdays: number) {
    const d = new Date();
    d.setTime(d.getTime() + exdays * 24 * 60 * 60 * 1000);
    const expires = 'expires=' + d.toUTCString();
    document.cookie = cname + '=' + cvalue + ';' + expires + ';path=/';
}

export function ensureBoardStyleOverride() {
    if (document.getElementById('board-style-override')) return;

    const style = document.createElement('style');
    style.id = 'board-style-override';
    style.textContent = '[data-board-variant] cg-board { background-image: var(--board-image); }';
    document.head.appendChild(style);
}

function cataloguedBoardCssId(variantName: string): string {
    return `board-set-catalogued-${variantName}`;
}

let chessgroundResizeFrame: number | undefined;

export function notifyChessgroundResize(): void {
    if (chessgroundResizeFrame !== undefined) cancelAnimationFrame(chessgroundResizeFrame);
    chessgroundResizeFrame = requestAnimationFrame(() => {
        chessgroundResizeFrame = undefined;
        document.body?.dispatchEvent(new Event('chessground.resize'));
    });
}

export function ensureCataloguedBoardCSS(variantName: string, revision?: string): void {
    const cssId = cataloguedBoardCssId(variantName);
    const query = revision ? `?v=${encodeURIComponent(revision)}` : '';
    const href = `/api/catalogued-variants/${encodeURIComponent(variantName)}/board-css.css${query}`;
    const existing = document.getElementById(cssId) as HTMLLinkElement | null;
    if (existing) {
        if (existing.getAttribute('href') !== href) {
            existing.addEventListener('load', notifyChessgroundResize, { once: true });
            existing.setAttribute('href', href);
        }
        return;
    }

    const link = document.createElement('link');
    link.id = cssId;
    link.rel = 'stylesheet';
    link.addEventListener('load', notifyChessgroundResize, { once: true });
    link.setAttribute('href', href);
    document.head.appendChild(link);
}

export function removeCataloguedBoardCSS(variantName: string): void {
    document.getElementById(cataloguedBoardCssId(variantName))?.remove();
}

export function pieceStyleClass(family: string, cssFile: string) {
    if (cssFile === 'letters' || cssFile === 'invisible') return `piece-style-${cssFile}`;
    if (family.startsWith('catalogued-') && cssFile.startsWith('custom')) {
        return `piece-style-${family}-custom`;
    }
    return `piece-style-${family}-${cssFile}`;
}

export function ensurePieceCSS(assetUrl: string, family: string, cssFile: string) {
    const cssId =
        cssFile === 'letters' || cssFile === 'invisible' ? `piece-set-${cssFile}` : `piece-set-${family}-${cssFile}`;
    let newUrl = sanitizeURL(`${assetUrl}/piece-css/${family}/${cssFile}.css`);
    if (family.startsWith('catalogued-') && cssFile.startsWith('custom')) {
        const revision = cssFile.startsWith('custom-') ? cssFile.slice('custom-'.length) : '';
        const query = revision ? `?v=${encodeURIComponent(revision)}` : '';
        newUrl = `/api/catalogued-variants/${encodeURIComponent(family.slice('catalogued-'.length))}/piece-css.css${query}`;
    } else if (family.startsWith('catalogued-') && cssFile === 'disguised') {
        newUrl = `/api/catalogued-variants/${encodeURIComponent(family.slice('catalogued-'.length))}/piece-disguised.css`;
    }
    if (cssFile === 'letters') newUrl = sanitizeURL(`${assetUrl}/piece-css/letters.css`);
    if (cssFile === 'invisible') newUrl = sanitizeURL(`${assetUrl}/piece-css/invisible.css`);

    if (document.getElementById(cssId)) return;

    const link = document.createElement('link');
    link.id = cssId;
    link.rel = 'stylesheet';
    link.setAttribute('href', newUrl);

    const anchor = document.querySelector('link[rel="stylesheet"][href*="extensions.css"]');
    if (anchor && anchor.parentNode) {
        anchor.parentNode.insertBefore(link, anchor);
    } else {
        document.head.appendChild(link);
    }
}

export function bind(eventName: string, f: (e: Event) => void, redraw: null | (() => void)) {
    return {
        insert(vnode: VNode) {
            vnode.elm?.addEventListener(eventName, (e: Event) => {
                const res = f(e);
                if (redraw) redraw();
                return res;
            });
        },
    };
}
