import { afterEach, beforeEach, describe, expect, jest, test } from '@jest/globals';
import { readFileSync } from 'node:fs';

import { copyBoardToPNG } from '../client/png';

interface StyleValues {
    backgroundColor?: string;
    backgroundImage?: string;
    backgroundSize?: string;
    borderColor?: string;
    borderStyle?: string;
    borderWidth?: string;
    display?: string;
    filter?: string;
    opacity?: string;
    transform?: string;
    visibility?: string;
    customProperties?: Record<string, string>;
}

function cssStyle(values: StyleValues = {}): CSSStyleDeclaration {
    return {
        backgroundColor: values.backgroundColor ?? 'rgba(0, 0, 0, 0)',
        backgroundImage: values.backgroundImage ?? 'none',
        backgroundSize: values.backgroundSize ?? 'auto',
        borderTopColor: values.borderColor ?? 'rgba(0, 0, 0, 0)',
        borderRightColor: values.borderColor ?? 'rgba(0, 0, 0, 0)',
        borderBottomColor: values.borderColor ?? 'rgba(0, 0, 0, 0)',
        borderLeftColor: values.borderColor ?? 'rgba(0, 0, 0, 0)',
        borderTopStyle: values.borderStyle ?? 'none',
        borderRightStyle: values.borderStyle ?? 'none',
        borderBottomStyle: values.borderStyle ?? 'none',
        borderLeftStyle: values.borderStyle ?? 'none',
        borderTopWidth: values.borderWidth ?? '0px',
        borderRightWidth: values.borderWidth ?? '0px',
        borderBottomWidth: values.borderWidth ?? '0px',
        borderLeftWidth: values.borderWidth ?? '0px',
        display: values.display ?? 'block',
        filter: values.filter ?? 'none',
        opacity: values.opacity ?? '1',
        transform: values.transform ?? 'none',
        visibility: values.visibility ?? 'visible',
        getPropertyValue: (name: string) => values.customProperties?.[name] ?? '',
    } as unknown as CSSStyleDeclaration;
}

function setRect(element: Element, x: number, y: number, width: number, height: number): void {
    element.getBoundingClientRect = () => new DOMRect(x, y, width, height);
}

function responseBlob(body: string): Response {
    return {
        ok: true,
        blob: async () => new Blob([body], { type: 'image/svg+xml' }),
    } as Response;
}

describe('board PNG export', () => {
    let serializeSpy: ReturnType<typeof jest.spyOn>;
    let clickedDownload = '';
    let clickedHref = '';

    beforeEach(() => {
        document.body.textContent = '';
        clickedDownload = '';
        clickedHref = '';

        Object.defineProperty(window, 'devicePixelRatio', { configurable: true, value: 2 });
        Object.defineProperty(globalThis, 'Image', {
            configurable: true,
            value: class {
                onload: (() => void) | null = null;
                onerror: (() => void) | null = null;
                private value = '';

                set src(url: string) {
                    this.value = url;
                    queueMicrotask(() => this.onload?.());
                }

                get src(): string {
                    return this.value;
                }
            },
        });

        Object.defineProperty(URL, 'createObjectURL', {
            configurable: true,
            value: jest.fn(() => 'blob:pychess-test'),
        });
        Object.defineProperty(URL, 'revokeObjectURL', {
            configurable: true,
            value: jest.fn(),
        });

        jest.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => {
            return {
                scale: jest.fn(),
                drawImage: jest.fn(),
            } as unknown as CanvasRenderingContext2D;
        });
        jest.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(callback => {
            callback(new Blob(['png'], { type: 'image/png' }));
        });
        jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
            clickedDownload = this.download;
            clickedHref = this.href;
        });

        serializeSpy = jest.spyOn(XMLSerializer.prototype, 'serializeToString');
    });

    afterEach(() => {
        jest.restoreAllMocks();
        document.body.textContent = '';
    });

    test('composes the board, overlays, pieces, arrows, auto-pieces, and custom SVGs before rasterizing', async () => {
        document.body.innerHTML = `
            <div class="cg-wrap">
                <cg-board>
                    <square class="check"></square>
                    <square class="selected"></square>
                    <piece data-style="piece"></piece>
                    <piece data-style="piece">
                        <svg viewBox="0 0 10 10"><image href="/nested.svg" /></svg>
                    </piece>
                </cg-board>
                <svg class="cg-shapes"><image href="/arrow.svg" /></svg>
                <cg-auto-pieces><piece data-style="piece"></piece></cg-auto-pieces>
                <svg class="cg-custom-svgs"><circle cx="5" cy="5" r="2" /></svg>
            </div>`;

        const wrap = document.querySelector<HTMLElement>('.cg-wrap')!;
        const board = document.querySelector<HTMLElement>('cg-board')!;
        const [check, selected] = Array.from(board.querySelectorAll<HTMLElement>('square'));
        const [piece1, piece2] = Array.from(board.querySelectorAll<HTMLElement>('piece'));
        const autoPiece = document.querySelector<HTMLElement>('cg-auto-pieces piece')!;
        const shapes = document.querySelector<SVGSVGElement>('svg.cg-shapes')!;
        const custom = document.querySelector<SVGSVGElement>('svg.cg-custom-svgs')!;

        setRect(board, 10, 20, 200, 200);
        setRect(check, 10, 20, 100, 100);
        setRect(selected, 110, 20, 100, 100);
        setRect(piece1, 10, 120, 100, 100);
        setRect(piece2, 110, 120, 100, 100);
        setRect(autoPiece, 60, 70, 50, 50);

        jest.spyOn(window, 'getComputedStyle').mockImplementation((element, pseudoElement) => {
            if (element === wrap) {
                return cssStyle({ customProperties: { '--cg-board-files': '2', '--cg-board-ranks': '2' } });
            }
            if (element === board) {
                return cssStyle({
                    backgroundImage: 'conic-gradient(rgb(10, 20, 30), rgb(40, 50, 60))',
                });
            }
            if (element === check) return cssStyle();
            if (element === selected) return cssStyle({ backgroundColor: 'rgba(255, 255, 0, 0.5)', opacity: '0.5' });
            if (element === piece1 || element === piece2 || element === autoPiece) {
                if (pseudoElement === '::before') return cssStyle();
                return cssStyle({ backgroundImage: 'url("/piece.svg")', backgroundSize: 'contain' });
            }
            if (element === shapes) return cssStyle({ opacity: '0.6' });
            if (element === custom) return cssStyle();
            return cssStyle();
        });

        const fetchMock = jest.fn(async (input: RequestInfo | URL) =>
            responseBlob(String(input).includes('piece.svg') ? '<svg>piece</svg>' : '<svg />'),
        );
        Object.defineProperty(globalThis, 'fetch', { configurable: true, writable: true, value: fetchMock });

        await copyBoardToPNG('8/8/8/3Q4/8/8/8/8 w - - 0 1');

        expect(clickedDownload).toBe('8/8/8/3Q4/8/8/8/8.png');
        expect(clickedHref).toBe('blob:pychess-test');
        expect(serializeSpy).toHaveBeenCalledTimes(1);

        const rendered = serializeSpy.mock.calls[0][0] as SVGSVGElement;
        expect(rendered.getAttribute('viewBox')).toBe('0 0 200 200');

        const checkerboardRects = Array.from(rendered.querySelectorAll('rect')).filter(rect =>
            ['rgb(10, 20, 30)', 'rgb(40, 50, 60)'].includes(rect.getAttribute('fill') ?? ''),
        );
        expect(checkerboardRects).toHaveLength(4);
        expect(checkerboardRects.map(rect => rect.getAttribute('fill'))).toEqual([
            'rgb(40, 50, 60)',
            'rgb(10, 20, 30)',
            'rgb(10, 20, 30)',
            'rgb(40, 50, 60)',
        ]);

        expect(rendered.querySelector('radialGradient#png-check-0')).not.toBeNull();
        expect(rendered.querySelector('rect[fill="rgba(255, 255, 0, 0.5)"]')?.getAttribute('opacity')).toBe('0.5');

        const topLevelPieceImages = Array.from(rendered.children).filter(
            child => child.tagName.toLowerCase() === 'image' && child.getAttribute('width') === '100',
        );
        expect(topLevelPieceImages).toHaveLength(2);
        expect(topLevelPieceImages.every(image => image.getAttribute('href')?.startsWith('data:image/svg+xml'))).toBe(
            true,
        );

        const shapeClone = rendered.querySelector('svg:not([viewBox]) image[href^="data:image/svg+xml"]');
        expect(shapeClone).not.toBeNull();
        expect(rendered.querySelector('svg[opacity="0.6"]')).not.toBeNull();
        expect(rendered.querySelector('circle[cx="5"][cy="5"][r="2"]')).not.toBeNull();

        const nestedImage = rendered.querySelector('svg[viewBox="0 0 10 10"] image');
        expect(nestedImage?.getAttribute('href')).toMatch(/^data:image\/svg\+xml/);

        const pieceFetches = fetchMock.mock.calls.filter(([input]) => String(input).endsWith('/piece.svg'));
        expect(pieceFetches).toHaveLength(1);
        expect(fetchMock).toHaveBeenCalledTimes(3);

        const canvas = document.querySelector('canvas');
        expect(canvas).toBeNull();
        expect(HTMLCanvasElement.prototype.getContext).toHaveBeenCalled();
    });

    test('exports Alice as one board with translucent opposite-board pieces and their styled borders', async () => {
        document.body.innerHTML = `
            <section class="alice"><div class="cg-wrap"><cg-board>
                <piece class="white q-piece"></piece>
                <piece class="mirror black n-piece"></piece>
            </cg-board></div></section>`;
        const board = document.querySelector<HTMLElement>('cg-board')!;
        const [normal, mirror] = Array.from(board.querySelectorAll<HTMLElement>('piece'));
        setRect(board, 10, 20, 160, 160);
        setRect(normal, 10, 20, 20, 20);
        setRect(mirror, 30, 40, 20, 20);

        jest.spyOn(window, 'getComputedStyle').mockImplementation((element, pseudoElement) => {
            if (element === normal && pseudoElement !== '::before') {
                return cssStyle({ backgroundImage: 'url("/queen.svg")' });
            }
            if (element === mirror && pseudoElement !== '::before') {
                return cssStyle({
                    backgroundImage: 'url("/knight.svg")',
                    backgroundColor: 'rgb(224, 255, 255)',
                    borderColor: 'rgb(0, 0, 255)',
                    borderStyle: 'solid',
                    borderWidth: '1px',
                    opacity: '0.2',
                });
            }
            return cssStyle();
        });
        Object.defineProperty(globalThis, 'fetch', {
            configurable: true,
            writable: true,
            value: jest.fn(async () => responseBlob('<svg />')),
        });

        await copyBoardToPNG('Q|n6/8/8/8/8/8/8/8 w - - 0 1');
        const rendered = serializeSpy.mock.calls[0][0] as SVGSVGElement;
        expect(rendered.getAttribute('viewBox')).toBe('0 0 160 160');
        expect(rendered.querySelectorAll('image')).toHaveLength(2);
        expect(rendered.querySelector('image[x="0"][y="0"]')?.getAttribute('opacity')).toBeNull();

        const ghost = rendered.querySelector('g[opacity="0.2"]')!;
        expect(ghost).not.toBeNull();
        expect(ghost.querySelector('rect[fill="rgb(224, 255, 255)"]')).not.toBeNull();
        const borders = ghost.querySelectorAll('rect[fill="rgb(0, 0, 255)"]');
        expect(borders).toHaveLength(4);
        expect(ghost.querySelector('image[x="20"][y="20"]')?.getAttribute('opacity')).toBeNull();
        expect(rendered.querySelectorAll('g[opacity="0.2"]')).toHaveLength(1);
    });

    test('expands internal SVG board references so board textures survive PNG rasterization', async () => {
        document.body.innerHTML = '<div class="cg-wrap"><cg-board></cg-board></div>';
        const board = document.querySelector<HTMLElement>('cg-board')!;
        setRect(board, 0, 0, 160, 160);
        jest.spyOn(window, 'getComputedStyle').mockImplementation(element =>
            element === board ? cssStyle({ backgroundImage: 'url("/brown.svg")' }) : cssStyle(),
        );
        const boardSvg =
            '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 8 8">' +
            '<rect width="8" height="8" fill="brown"/><g id="light" fill="beige"><rect width="1" height="1"/></g>' +
            '<use xlink:href="#light" x="2" y="2"/></svg>';
        Object.defineProperty(globalThis, 'fetch', {
            configurable: true,
            writable: true,
            value: jest.fn(async (input: RequestInfo | URL) =>
                String(input).startsWith('data:')
                    ? ({ text: async () => boardSvg } as Response)
                    : responseBlob(boardSvg),
            ),
        });

        await copyBoardToPNG('8/8/8/8/8/8/8/8 w - - 0 1');
        const rendered = serializeSpy.mock.calls[0][0] as SVGSVGElement;
        expect(rendered.querySelector('svg[viewBox="0 0 8 8"]')).not.toBeNull();
        expect(rendered.querySelector('use')).toBeNull();
        expect(rendered.querySelector('g[transform="translate(2 2)"] rect')).not.toBeNull();
    });

    test.each(['g', 'symbol'])('preserves scaled %s board references and symbol viewports', async tag => {
        document.body.innerHTML = '<div class="cg-wrap"><cg-board></cg-board></div>';
        const board = document.querySelector<HTMLElement>('cg-board')!;
        setRect(board, 0, 0, 160, 160);
        jest.spyOn(window, 'getComputedStyle').mockImplementation(element =>
            element === board ? cssStyle({ backgroundImage: 'url("/scaled-board.svg")' }) : cssStyle(),
        );
        const boardSvg =
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80"><defs>' +
            `<${tag} id="tile" viewBox="0 0 10 10" preserveAspectRatio="xMinYMin meet" width="10" height="10">` +
            `<rect width="10" height="10" fill="beige"/></${tag}></defs>` +
            '<use id="instance" href="#tile" x="2" y="3" transform="scale(2)" width="20" height="30" opacity="0.5"/></svg>';
        Object.defineProperty(globalThis, 'fetch', {
            configurable: true,
            writable: true,
            value: jest.fn(async (input: RequestInfo | URL) =>
                String(input).startsWith('data:')
                    ? ({ text: async () => boardSvg } as Response)
                    : responseBlob(boardSvg),
            ),
        });

        await copyBoardToPNG('8/8/8/8/8/8/8/8 w - - 0 1');
        const rendered = serializeSpy.mock.calls[0][0] as SVGSVGElement;
        const instance = rendered.querySelector('#instance')!;
        expect(instance.getAttribute('transform')).toBe('scale(2) translate(2 3)');
        expect(instance.getAttribute('opacity')).toBe('0.5');
        expect(instance.querySelector('rect[fill="beige"]')).not.toBeNull();
        expect(instance.querySelector('symbol, use')).toBeNull();
        if (tag === 'symbol') {
            const viewport = instance.querySelector('svg')!;
            expect(viewport.getAttribute('viewBox')).toBe('0 0 10 10');
            expect(viewport.getAttribute('preserveAspectRatio')).toBe('xMinYMin meet');
            expect(viewport.getAttribute('width')).toBe('20');
            expect(viewport.getAttribute('height')).toBe('30');
        }
    });

    test('keeps all default Borderlands board tiles renderable after expanding references', async () => {
        document.body.innerHTML = '<div class="cg-wrap"><cg-board></cg-board></div>';
        const board = document.querySelector<HTMLElement>('cg-board')!;
        setRect(board, 0, 0, 450, 500);
        jest.spyOn(window, 'getComputedStyle').mockImplementation(element =>
            element === board ? cssStyle({ backgroundImage: 'url("/borderlands-cobalt.svg")' }) : cssStyle(),
        );
        const boardSvg = readFileSync('static/images/board/borderlands-cobalt.svg', 'utf8');
        Object.defineProperty(globalThis, 'fetch', {
            configurable: true,
            writable: true,
            value: jest.fn(async (input: RequestInfo | URL) =>
                String(input).startsWith('data:')
                    ? ({ text: async () => boardSvg } as Response)
                    : responseBlob(boardSvg),
            ),
        });

        await copyBoardToPNG('9/9/9/9/9/9/9/9/9/9 w - - 0 1');
        const rendered = serializeSpy.mock.calls[0][0] as SVGSVGElement;
        expect(rendered.querySelector('use, g > symbol')).toBeNull();
        expect(rendered.querySelectorAll('g > svg')).toHaveLength(90);
        expect(rendered.querySelector('#use340')?.getAttribute('transform')).toBe(
            'matrix(1.019997,0,0,1.0199975,-111.99854,-3.9995587) translate(500 100)',
        );
    });

    test('uses rotated ::before artwork when a piece style renders its image there', async () => {
        document.body.innerHTML = `
            <div class="cg-wrap">
                <cg-board><piece></piece></cg-board>
            </div>`;
        const wrap = document.querySelector<HTMLElement>('.cg-wrap')!;
        const board = document.querySelector<HTMLElement>('cg-board')!;
        const piece = document.querySelector<HTMLElement>('piece')!;

        setRect(board, 0, 0, 80, 80);
        setRect(piece, 0, 0, 80, 80);

        jest.spyOn(window, 'getComputedStyle').mockImplementation((element, pseudoElement) => {
            if (element === wrap) {
                return cssStyle({ customProperties: { '--cg-board-files': '1', '--cg-board-ranks': '1' } });
            }
            if (element === board) return cssStyle({ backgroundColor: 'rgb(1, 2, 3)' });
            if (element === piece && pseudoElement === '::before') {
                return cssStyle({
                    backgroundImage: 'url("/rotated.svg")',
                    backgroundSize: 'contain',
                    transform: 'matrix(-1, 0, 0, -1, 0, 0)',
                });
            }
            if (element === piece) return cssStyle({ opacity: '0.75', filter: 'brightness(0.8)' });
            return cssStyle();
        });
        const fetchMock = jest.fn(async () => responseBlob('<svg />'));
        Object.defineProperty(globalThis, 'fetch', { configurable: true, writable: true, value: fetchMock });

        await copyBoardToPNG('Q7/8/8/8/8/8/8/8 w - - 0 1');

        const rendered = serializeSpy.mock.calls[0][0] as SVGSVGElement;
        const image = rendered.querySelector('image');
        expect(image?.getAttribute('transform')).toBe('rotate(180 40 40)');
        expect(image?.getAttribute('opacity')).toBe('0.75');
        expect(image?.style.filter).toBe('brightness(0.8)');
    });

    test('exports lower SVG planes before pieces and retains upper drawing order', async () => {
        document.body.innerHTML = `
            <div class="cg-wrap">
                <cg-board><piece></piece></cg-board>
                <svg class="cg-shapes-below" viewBox="-4 -4 8 8"><g data-plane="lower-shapes"><line x1="0" x2="1" /></g></svg>
                <svg class="cg-custom-below" viewBox="-3.5 -3.5 8 8"><g data-plane="lower-custom"><rect width="1" height="1" /></g></svg>
                <svg class="cg-shapes"><g data-plane="upper-shapes" /></svg>
                <cg-auto-pieces></cg-auto-pieces>
                <svg class="cg-custom-svgs"><g data-plane="upper-custom" /></svg>
            </div>`;
        const board = document.querySelector<HTMLElement>('cg-board')!;
        const piece = board.querySelector('piece')!;
        setRect(board, 0, 0, 400, 400);
        setRect(piece, 0, 0, 50, 50);
        jest.spyOn(window, 'getComputedStyle').mockImplementation(element => {
            if (element === board) return cssStyle({ backgroundColor: 'rgb(10, 20, 30)' });
            if (element === piece) return cssStyle({ backgroundImage: 'url("data:image/svg+xml;base64,PHN2Zy8+")' });
            if (element.classList.contains('cg-shapes-below')) return cssStyle({ opacity: '0.6' });
            return cssStyle();
        });
        await copyBoardToPNG('8/8/8/8/8/8/8/R7 w - - 0 1');
        const rendered = serializeSpy.mock.calls[0][0] as SVGSVGElement;
        const order = [...rendered.children].map(
            child => child.querySelector('[data-plane]')?.getAttribute('data-plane') ?? child.tagName.toLowerCase(),
        );
        expect(order).toEqual(['rect', 'lower-shapes', 'lower-custom', 'image', 'upper-shapes', 'upper-custom']);
        expect(rendered.querySelector('svg[viewBox="-4 -4 8 8"]')?.getAttribute('opacity')).toBe('0.6');
        expect(rendered.querySelector('svg[viewBox="-3.5 -3.5 8 8"]')).not.toBeNull();
    });
});
