import * as cg from 'chessgroundx/types';

const SVG_NS = 'http://www.w3.org/2000/svg';
const XLINK_NS = 'http://www.w3.org/1999/xlink';
const resourceCache = new Map<string, Promise<string>>();

function svgElement<K extends keyof SVGElementTagNameMap>(name: K): SVGElementTagNameMap[K] {
    return document.createElementNS(SVG_NS, name);
}

function transparent(color: string): boolean {
    if (!color || color === 'transparent') return true;
    const rgba = /^rgba\([^,]+,[^,]+,[^,]+,\s*([0-9.]+)\)$/.exec(color);
    return rgba !== null && Number(rgba[1]) === 0;
}

function cssUrl(backgroundImage: string): string | undefined {
    const value = backgroundImage.trim();
    if (!value.startsWith('url(') || !value.endsWith(')')) return undefined;

    let url = value.slice(4, -1).trim();
    if ((url.startsWith('"') && url.endsWith('"')) || (url.startsWith("'") && url.endsWith("'"))) {
        url = url.slice(1, -1);
    }
    return url.replace(/\\(["'])/g, '$1');
}

function blobToDataUrl(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = () => reject(reader.error ?? new Error('Unable to read image resource'));
        reader.readAsDataURL(blob);
    });
}

async function inlineResource(url: string): Promise<string> {
    if (url.startsWith('data:')) return url;

    const absolute = new URL(url, document.baseURI).href;
    let pending = resourceCache.get(absolute);
    if (!pending) {
        pending = fetch(absolute, { credentials: 'same-origin' }).then(async response => {
            if (!response.ok) throw new Error(`Unable to load ${absolute}: ${response.status}`);
            return blobToDataUrl(await response.blob());
        });
        resourceCache.set(absolute, pending);
    }
    return pending;
}

function backgroundPreserveAspectRatio(style: CSSStyleDeclaration): string {
    if (style.backgroundSize.includes('contain')) return 'xMidYMid meet';
    if (style.backgroundSize.includes('cover')) return 'xMidYMid slice';
    return 'none';
}

function cssColors(value: string): string[] {
    const colors: string[] = value.match(/#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)/g) ?? [];
    return colors.filter((color, index) => colors.indexOf(color) === index);
}

function boardDimensions(board: HTMLElement): { files: number; ranks: number } {
    const wrap = board.closest('.cg-wrap') as HTMLElement | null;
    const style = getComputedStyle(wrap ?? board);
    const files = Number.parseFloat(style.getPropertyValue('--cg-board-files'));
    const ranks = Number.parseFloat(style.getPropertyValue('--cg-board-ranks'));
    return {
        files: Number.isFinite(files) && files > 0 ? files : 8,
        ranks: Number.isFinite(ranks) && ranks > 0 ? ranks : 8,
    };
}

function appendCheckerboard(
    svg: SVGSVGElement,
    board: HTMLElement,
    colors: string[],
    width: number,
    height: number,
): void {
    if (colors.length < 2) return;

    const { files, ranks } = boardDimensions(board);
    const squareWidth = width / files;
    const squareHeight = height / ranks;

    // This matches the generated catalogue-board conic-gradient: the top-left
    // quadrant is the second colour in the gradient declaration.
    for (let rank = 0; rank < ranks; rank++) {
        for (let file = 0; file < files; file++) {
            const rect = svgElement('rect');
            rect.setAttribute('x', String(file * squareWidth));
            rect.setAttribute('y', String(rank * squareHeight));
            rect.setAttribute('width', String(squareWidth));
            rect.setAttribute('height', String(squareHeight));
            rect.setAttribute('fill', colors[(file + rank + 1) % 2]);
            svg.appendChild(rect);
        }
    }
}

function expandSvgUses(root: SVGSVGElement): void {
    const definitions = new Map(
        Array.from(root.querySelectorAll<SVGElement>('[id]')).map(element => [element.id, element]),
    );
    const expand = (use: SVGUseElement, ancestors: Set<string>): void => {
        const href = use.getAttribute('href') ?? use.getAttributeNS(XLINK_NS, 'href');
        if (!href?.startsWith('#')) return;
        const id = href.slice(1);
        const original = definitions.get(id);
        if (!original || ancestors.has(id)) return;
        let clone = original.cloneNode(true) as SVGElement;
        if (clone.localName === 'symbol') {
            // Symbols only render through <use>. An SVG viewport preserves their
            // viewBox and aspect ratio while making the expanded artwork visible.
            const viewport = svgElement('svg');
            for (const attr of Array.from(clone.attributes)) {
                viewport.setAttributeNS(attr.namespaceURI, attr.name, attr.value);
            }
            viewport.append(...Array.from(clone.childNodes));
            clone = viewport;
        }
        if (clone.localName === 'svg') {
            for (const dimension of ['width', 'height']) {
                const value = use.getAttribute(dimension);
                if (value !== null) clone.setAttribute(dimension, value);
            }
        }
        const next = new Set([...ancestors, id]);
        for (const nested of Array.from(clone.querySelectorAll<SVGUseElement>('use'))) expand(nested, next);

        const group = svgElement('g');
        const x = use.getAttribute('x') ?? '0';
        const y = use.getAttribute('y') ?? '0';
        group.setAttribute('transform', `${use.getAttribute('transform') ?? ''} translate(${x} ${y})`.trim());
        for (const attr of Array.from(use.attributes)) {
            if (['x', 'y', 'href', 'transform'].includes(attr.localName)) continue;
            group.setAttributeNS(attr.namespaceURI, attr.name, attr.value);
        }
        group.appendChild(clone);
        use.replaceWith(group);
    };
    for (const use of Array.from(root.querySelectorAll<SVGUseElement>('use'))) expand(use, new Set());
}

async function appendBoardBackground(
    svg: SVGSVGElement,
    board: HTMLElement,
    width: number,
    height: number,
): Promise<void> {
    const style = getComputedStyle(board);
    if (!transparent(style.backgroundColor)) {
        const rect = svgElement('rect');
        rect.setAttribute('width', String(width));
        rect.setAttribute('height', String(height));
        rect.setAttribute('fill', style.backgroundColor);
        svg.appendChild(rect);
    }

    const url = cssUrl(style.backgroundImage);
    if (url) {
        const dataUrl = await inlineResource(url);
        if (dataUrl.startsWith('data:image/svg+xml')) {
            // Preserve boards whose artwork uses internal SVG <use> references.
            // Nesting one SVG as an <image> can lose those references in PNGs.
            const markup = await (await fetch(dataUrl)).text();
            const source = new DOMParser().parseFromString(markup, 'image/svg+xml')
                .documentElement as unknown as SVGSVGElement;
            if (source.localName === 'svg') {
                const nested = document.importNode(source, true) as SVGSVGElement;
                expandSvgUses(nested);
                nested.setAttribute('x', '0');
                nested.setAttribute('y', '0');
                nested.setAttribute('width', String(width));
                nested.setAttribute('height', String(height));
                nested.setAttribute('preserveAspectRatio', backgroundPreserveAspectRatio(style));
                await inlineSvgImages(nested);
                svg.appendChild(nested);
                return;
            }
        }
        const image = svgElement('image');
        image.setAttribute('x', '0');
        image.setAttribute('y', '0');
        image.setAttribute('width', String(width));
        image.setAttribute('height', String(height));
        image.setAttribute('preserveAspectRatio', backgroundPreserveAspectRatio(style));
        image.setAttribute('href', dataUrl);
        svg.appendChild(image);
        return;
    }

    if (style.backgroundImage.startsWith('conic-gradient(')) {
        appendCheckerboard(svg, board, cssColors(style.backgroundImage), width, height);
    }
}

function relativeRect(element: Element, boardRect: DOMRect): DOMRect {
    const rect = element.getBoundingClientRect();
    return new DOMRect(rect.left - boardRect.left, rect.top - boardRect.top, rect.width, rect.height);
}

function appendCheckGradient(svg: SVGSVGElement, rect: DOMRect, id: string): void {
    const defs = svgElement('defs');
    const gradient = svgElement('radialGradient');
    gradient.id = id;
    for (const [offset, color, opacity] of [
        ['0%', 'rgb(255, 0, 0)', '1'],
        ['25%', 'rgb(231, 0, 0)', '1'],
        ['89%', 'rgb(169, 0, 0)', '0'],
        ['100%', 'rgb(158, 0, 0)', '0'],
    ]) {
        const stop = svgElement('stop');
        stop.setAttribute('offset', offset);
        stop.setAttribute('stop-color', color);
        stop.setAttribute('stop-opacity', opacity);
        gradient.appendChild(stop);
    }
    defs.appendChild(gradient);
    svg.appendChild(defs);

    const overlay = svgElement('rect');
    overlay.setAttribute('x', String(rect.x));
    overlay.setAttribute('y', String(rect.y));
    overlay.setAttribute('width', String(rect.width));
    overlay.setAttribute('height', String(rect.height));
    overlay.setAttribute('fill', `url(#${id})`);
    svg.appendChild(overlay);
}

function appendSquareOverlays(svg: SVGSVGElement, board: HTMLElement, boardRect: DOMRect): void {
    let checkIndex = 0;
    for (const square of Array.from(board.querySelectorAll('square'))) {
        const element = square as HTMLElement;
        const style = getComputedStyle(element);
        if (style.display === 'none' || Number(style.opacity) === 0) continue;

        const rect = relativeRect(element, boardRect);
        if (element.classList.contains('check')) {
            appendCheckGradient(svg, rect, `png-check-${checkIndex++}`);
            continue;
        }
        if (transparent(style.backgroundColor)) continue;

        const overlay = svgElement('rect');
        overlay.setAttribute('x', String(rect.x));
        overlay.setAttribute('y', String(rect.y));
        overlay.setAttribute('width', String(rect.width));
        overlay.setAttribute('height', String(rect.height));
        overlay.setAttribute('fill', style.backgroundColor);
        if (style.opacity !== '1') overlay.setAttribute('opacity', style.opacity);
        svg.appendChild(overlay);
    }
}

function isHalfTurn(transform: string): boolean {
    if (transform === 'none') return false;
    const matrix = /^matrix\(([^)]+)\)$/.exec(transform);
    if (!matrix) return transform.includes('180deg');
    const values = matrix[1].split(',').map(Number);
    return values.length >= 4 && Math.abs(values[0] + 1) < 0.001 && Math.abs(values[3] + 1) < 0.001;
}

function pieceArtworkStyle(piece: HTMLElement): {
    artwork: CSSStyleDeclaration;
    piece: CSSStyleDeclaration;
    rotate: boolean;
} {
    const pieceStyle = getComputedStyle(piece);
    const beforeStyle = getComputedStyle(piece, '::before');
    if (cssUrl(beforeStyle.backgroundImage)) {
        return { artwork: beforeStyle, piece: pieceStyle, rotate: isHalfTurn(beforeStyle.transform) };
    }
    return { artwork: pieceStyle, piece: pieceStyle, rotate: false };
}

async function appendNestedPieceSvgs(
    svg: SVGElement,
    piece: HTMLElement,
    rect: DOMRect,
    opacity: string,
): Promise<void> {
    for (const child of Array.from(piece.querySelectorAll(':scope > svg'))) {
        const nested = child.cloneNode(true) as SVGSVGElement;
        nested.setAttribute('x', String(rect.x));
        nested.setAttribute('y', String(rect.y));
        nested.setAttribute('width', String(rect.width));
        nested.setAttribute('height', String(rect.height));
        if (opacity !== '1') nested.setAttribute('opacity', opacity);
        await inlineSvgImages(nested);
        svg.appendChild(nested);
    }
}

function pieceBorderWidth(style: CSSStyleDeclaration, side: 'Top' | 'Right' | 'Bottom' | 'Left'): number {
    if (style[`border${side}Style`] === 'none') return 0;
    return Number.parseFloat(style[`border${side}Width`]) || 0;
}

function appendPieceBorder(svg: SVGElement, rect: DOMRect, style: CSSStyleDeclaration): void {
    const sides: Array<{
        side: 'Top' | 'Right' | 'Bottom' | 'Left';
        x: number;
        y: number;
        width: number;
        height: number;
    }> = [
        { side: 'Top', x: rect.x, y: rect.y, width: rect.width, height: pieceBorderWidth(style, 'Top') },
        {
            side: 'Right',
            x: rect.right - pieceBorderWidth(style, 'Right'),
            y: rect.y,
            width: pieceBorderWidth(style, 'Right'),
            height: rect.height,
        },
        {
            side: 'Bottom',
            x: rect.x,
            y: rect.bottom - pieceBorderWidth(style, 'Bottom'),
            width: rect.width,
            height: pieceBorderWidth(style, 'Bottom'),
        },
        { side: 'Left', x: rect.x, y: rect.y, width: pieceBorderWidth(style, 'Left'), height: rect.height },
    ];
    for (const { side, x, y, width, height } of sides) {
        if (width <= 0 || height <= 0) continue;
        const color = style[`border${side}Color`];
        if (transparent(color)) continue;
        const border = svgElement('rect');
        border.setAttribute('x', String(x));
        border.setAttribute('y', String(y));
        border.setAttribute('width', String(width));
        border.setAttribute('height', String(height));
        border.setAttribute('fill', color);
        svg.appendChild(border);
    }
}

async function appendPiece(svg: SVGSVGElement, piece: HTMLElement, boardRect: DOMRect): Promise<void> {
    const { artwork, piece: pieceStyle, rotate } = pieceArtworkStyle(piece);
    if (pieceStyle.display === 'none' || pieceStyle.visibility === 'hidden' || Number(pieceStyle.opacity) === 0) return;

    const rect = relativeRect(piece, boardRect);
    if (rect.width <= 0 || rect.height <= 0) return;

    const hasBackground = !transparent(pieceStyle.backgroundColor);
    const hasBorder = (['Top', 'Right', 'Bottom', 'Left'] as const).some(
        side => pieceBorderWidth(pieceStyle, side) > 0 && !transparent(pieceStyle[`border${side}Color`]),
    );
    // Alice's opposite-board pieces have a translucent light-cyan box and blue
    // border. Apply their opacity to the *whole* piece, not just its artwork.
    const decorated = hasBackground || hasBorder;
    const container = decorated ? svgElement('g') : svg;
    if (decorated) {
        if (pieceStyle.opacity !== '1') container.setAttribute('opacity', pieceStyle.opacity);
        if (hasBackground) {
            const background = svgElement('rect');
            background.setAttribute('x', String(rect.x));
            background.setAttribute('y', String(rect.y));
            background.setAttribute('width', String(rect.width));
            background.setAttribute('height', String(rect.height));
            background.setAttribute('fill', pieceStyle.backgroundColor);
            container.appendChild(background);
        }
    }

    const url = cssUrl(artwork.backgroundImage);
    if (url) {
        const image = svgElement('image');
        image.setAttribute('x', String(rect.x));
        image.setAttribute('y', String(rect.y));
        image.setAttribute('width', String(rect.width));
        image.setAttribute('height', String(rect.height));
        image.setAttribute('preserveAspectRatio', backgroundPreserveAspectRatio(artwork));
        image.setAttribute('href', await inlineResource(url));
        if (rotate) {
            const cx = rect.x + rect.width / 2;
            const cy = rect.y + rect.height / 2;
            image.setAttribute('transform', `rotate(180 ${cx} ${cy})`);
        }
        if (!decorated && pieceStyle.opacity !== '1') image.setAttribute('opacity', pieceStyle.opacity);
        if (pieceStyle.filter !== 'none') image.style.filter = pieceStyle.filter;
        container.appendChild(image);
    }

    await appendNestedPieceSvgs(container, piece, rect, decorated ? '1' : pieceStyle.opacity);
    if (hasBorder) appendPieceBorder(container, rect, pieceStyle);
    if (decorated) svg.appendChild(container);
}

async function appendPieces(svg: SVGSVGElement, board: HTMLElement, boardRect: DOMRect): Promise<void> {
    for (const piece of Array.from(board.querySelectorAll<HTMLElement>('piece')))
        await appendPiece(svg, piece, boardRect);
}

async function appendAutoPieces(svg: SVGSVGElement, wrap: HTMLElement | null, boardRect: DOMRect): Promise<void> {
    for (const piece of Array.from(wrap?.querySelectorAll<HTMLElement>('cg-auto-pieces piece') ?? [])) {
        await appendPiece(svg, piece, boardRect);
    }
}

async function inlineSvgImages(svg: SVGSVGElement): Promise<void> {
    await Promise.all(
        Array.from(svg.querySelectorAll('image')).map(async image => {
            const href = image.getAttribute('href') ?? image.getAttributeNS(XLINK_NS, 'href');
            if (!href || href.startsWith('data:')) return;
            const dataUrl = await inlineResource(href);
            image.setAttribute('href', dataUrl);
            image.removeAttributeNS(XLINK_NS, 'href');
        }),
    );
}

async function appendChessgroundSvgLayer(
    svg: SVGSVGElement,
    wrap: HTMLElement | null,
    selector: string,
    width: number,
    height: number,
): Promise<void> {
    const layer = wrap?.querySelector(selector) as SVGSVGElement | null;
    if (!layer) return;

    const clone = layer.cloneNode(true) as SVGSVGElement;
    clone.removeAttribute('class');
    clone.setAttribute('x', '0');
    clone.setAttribute('y', '0');
    clone.setAttribute('width', String(width));
    clone.setAttribute('height', String(height));
    const opacity = getComputedStyle(layer).opacity;
    if (opacity !== '1') clone.setAttribute('opacity', opacity);
    await inlineSvgImages(clone);
    svg.appendChild(clone);
}

async function buildBoardSvg(board: HTMLElement): Promise<{ svg: SVGSVGElement; width: number; height: number }> {
    const boardRect = board.getBoundingClientRect();
    const width = boardRect.width;
    const height = boardRect.height;
    if (width <= 0 || height <= 0) throw new Error('Board has no renderable size');

    const svg = svgElement('svg');
    svg.setAttribute('xmlns', SVG_NS);
    svg.setAttribute('xmlns:xlink', XLINK_NS);
    svg.setAttribute('width', String(width));
    svg.setAttribute('height', String(height));
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);

    await appendBoardBackground(svg, board, width, height);
    appendSquareOverlays(svg, board, boardRect);

    const wrap = board.closest('.cg-wrap') as HTMLElement | null;
    await appendChessgroundSvgLayer(svg, wrap, 'svg.cg-shapes-below', width, height);
    await appendChessgroundSvgLayer(svg, wrap, 'svg.cg-custom-below', width, height);
    await appendPieces(svg, board, boardRect);
    await appendChessgroundSvgLayer(svg, wrap, 'svg.cg-shapes', width, height);
    await appendAutoPieces(svg, wrap, boardRect);
    await appendChessgroundSvgLayer(svg, wrap, 'svg.cg-custom-svgs', width, height);

    return { svg, width, height };
}

function loadImage(url: string): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = () => reject(new Error('Unable to rasterize board SVG'));
        image.src = url;
    });
}

function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
    return new Promise((resolve, reject) => {
        canvas.toBlob(blob => {
            if (blob) resolve(blob);
            else reject(new Error('Unable to encode board PNG'));
        }, 'image/png');
    });
}

async function renderBoardPng(board: HTMLElement): Promise<Blob> {
    const { svg, width, height } = await buildBoardSvg(board);
    const svgBlob = new Blob([new XMLSerializer().serializeToString(svg)], {
        type: 'image/svg+xml;charset=utf-8',
    });
    const svgUrl = URL.createObjectURL(svgBlob);

    try {
        const image = await loadImage(svgUrl);
        const pixelRatio = window.devicePixelRatio || 1;
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(width * pixelRatio));
        canvas.height = Math.max(1, Math.round(height * pixelRatio));
        const context = canvas.getContext('2d');
        if (!context) throw new Error('Canvas 2D context is unavailable');
        context.scale(pixelRatio, pixelRatio);
        context.drawImage(image, 0, 0, width, height);
        return canvasToBlob(canvas);
    } finally {
        URL.revokeObjectURL(svgUrl);
    }
}

function downloadBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.download = filename;
    link.href = url;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
}

export async function copyBoardToPNG(fen: cg.FEN): Promise<void> {
    const board = document.getElementsByTagName('cg-board')[0] as HTMLElement | undefined;
    if (!board) return;

    resourceCache.clear();
    try {
        const png = await renderBoardPng(board);
        downloadBlob(png, fen.split(' ')[0].replace(/\+/g, '.') + '.png');
    } catch (error) {
        console.error('Unable to export board PNG', error);
    } finally {
        resourceCache.clear();
    }
}
