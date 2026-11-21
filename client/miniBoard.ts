import { Api } from 'chessgroundx/api';
import { renderResized, updateBounds } from 'chessgroundx/render';

export function readMiniBoardWidth(boardWrap: HTMLElement): string {
    const computedStyle = getComputedStyle(boardWrap);
    const miniWidth = computedStyle.getPropertyValue('--mini-board-width').trim();
    if (miniWidth !== '') return miniWidth;

    const width = computedStyle.width.trim();
    if (width !== '' && width !== 'auto') return width;

    const measuredWidth = boardWrap.getBoundingClientRect().width;
    return measuredWidth > 0 ? `${measuredWidth}px` : '256px';
}

export function sizeMiniBoardHost(boardWrap: HTMLElement): HTMLElement | undefined {
    const miniWidth = readMiniBoardWidth(boardWrap);
    boardWrap.style.width = miniWidth;
    boardWrap.style.maxWidth = '100%';

    const boardHost = boardWrap.parentElement;
    if (boardHost instanceof HTMLElement) {
        boardHost.style.width = miniWidth;
        boardHost.style.maxWidth = '100%';
        return boardHost;
    }

    return undefined;
}

// Custom board styles can change a wrapper's padding-based aspect ratio after
// Chessground renders. ResizeObserver only sees its unchanged content box, so
// also react to the explicit resize signal sent when that stylesheet loads.
export function bindBoardResize(chessground: Api): () => void {
    let resizeFrame: number | undefined;

    const scheduleResize = () => {
        if (resizeFrame !== undefined) cancelAnimationFrame(resizeFrame);
        resizeFrame = requestAnimationFrame(() => {
            resizeFrame = undefined;
            updateBounds(chessground.state);
            renderResized(chessground.state);
        });
    };

    document.body.addEventListener('chessground.resize', scheduleResize);
    scheduleResize();

    return () => {
        document.body.removeEventListener('chessground.resize', scheduleResize);
        if (resizeFrame !== undefined) cancelAnimationFrame(resizeFrame);
    };
}
