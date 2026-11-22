import { _ } from '../i18n';
import type { DrawShape, Drawable } from 'chessgroundx/draw';
import { read } from 'chessgroundx/fen';
import { glyphToSvg } from 'chessgroundx/glyph';
import type { State } from 'chessgroundx/state';
import type { Key, Pieces } from 'chessgroundx/types';
import type { AnalysisTreeNode } from './analysisTree';
import { moveSquares } from './variationShapes';

// Adapted from lila public/glyphs.json (copyright the lila authors, AGPL-3.0).
export const GLYPH_GROUPS = {
    move: [
        { id: 1, symbol: '!', name: () => _('Good move') },
        { id: 2, symbol: '?', name: () => _('Mistake') },
        { id: 3, symbol: '!!', name: () => _('Brilliant move') },
        { id: 4, symbol: '??', name: () => _('Blunder') },
        { id: 5, symbol: '!?', name: () => _('Interesting move') },
        { id: 6, symbol: '?!', name: () => _('Dubious move') },
        { id: 7, symbol: '□', name: () => _('Only move') },
        { id: 22, symbol: '⨀', name: () => _('Zugzwang') },
    ],
    position: [
        { id: 10, symbol: '=', name: () => _('Equal position') },
        { id: 13, symbol: '∞', name: () => _('Unclear position') },
        { id: 14, symbol: '⩲', name: () => _('White is slightly better') },
        { id: 15, symbol: '⩱', name: () => _('Black is slightly better') },
        { id: 16, symbol: '±', name: () => _('White is better') },
        { id: 17, symbol: '∓', name: () => _('Black is better') },
        { id: 18, symbol: '+−', name: () => _('White is winning') },
        { id: 19, symbol: '−+', name: () => _('Black is winning') },
    ],
    observation: [
        { id: 146, symbol: 'N', name: () => _('Novelty') },
        { id: 32, symbol: '↑↑', name: () => _('Development') },
        { id: 36, symbol: '↑', name: () => _('Initiative') },
        { id: 40, symbol: '→', name: () => _('Attack') },
        { id: 132, symbol: '⇆', name: () => _('Counterplay') },
        { id: 138, symbol: '⊕', name: () => _('Time trouble') },
        { id: 44, symbol: '=∞', name: () => _('With compensation') },
        { id: 140, symbol: '∆', name: () => _('With the idea') },
    ],
} as const;

export const GLYPHS = Object.values(GLYPH_GROUPS).flat();

export function visibleNags(node: AnalysisTreeNode, showServerAnalysis = true): number[] {
    const nags = node.annotations?.nags ?? [];
    const advice = node.step.analysis?.advice;
    return !showServerAnalysis && advice ? nags.filter(nag => nag !== advice.nag) : nags;
}

type AnnotationBoard = Pick<State, 'dimensions' | 'kingRoles'> & {
    drawable?: Pick<Drawable, 'checkCounters'>;
    boardState?: State['boardState'];
};
const maxGlyphs = 4;
const glyphSvgs = glyphToSvg(maxGlyphs);

function annotationSquare(
    node: AnalysisTreeNode,
    parent: AnalysisTreeNode | undefined,
    board: AnnotationBoard,
    pieces: Pieces,
): Key | undefined {
    const move = node.step.move && moveSquares(node.step.move, board.dimensions);
    if (!move) return undefined;
    if (!(node.step.sanSAN ?? node.step.san)?.startsWith('O-O')) return move.dest;
    if (!parent) return undefined;

    // Castling can be encoded as king-to-rook (or rook-to-king with gating).
    // Use the resolved positions and configured royal roles, including stationary
    // Chess960 kings, rather than Lichess's c/g files and ranks 1/8.
    const before = read(parent.step.fen, board.dimensions).pieces;
    const royals = [...pieces].filter(
        ([, piece]) => piece.color === parent.step.turnColor && board.kingRoles.includes(piece.role),
    );
    const moved = royals.filter(([key, piece]) => {
        const old = before.get(key);
        return old?.color !== piece.color || old.role !== piece.role;
    });
    if (moved.length === 1) return moved[0][0];
    if (moved.length) return undefined;
    return [move.orig, move.dest].find(
        key =>
            key &&
            royals.some(([at, piece]) => {
                const old = before.get(key);
                return at === key && old?.color === piece.color && old.role === piece.role;
            }),
    );
}

// Adapted from lila ui/lib/src/game/glyphs.ts::annotationShapes
// (copyright the lila authors, AGPL-3.0). Numeric NAGs and FSF placement are local.
export function annotationShapes(
    node: AnalysisTreeNode,
    parent: AnalysisTreeNode | undefined,
    board: AnnotationBoard,
    nags: number[],
    existingShapes: DrawShape[] = [],
): DrawShape[] {
    if (!nags.length || !node.step.move || !(node.step.sanSAN ?? node.step.san)) return [];
    const pieces = read(node.step.fen, board.dimensions).pieces;
    const orig = annotationSquare(node, parent, board, pieces);
    if (!orig) return [];
    let stacked = existingShapes.filter(shape => shape.orig === orig && shape.customSvg).length;
    let limit = maxGlyphs;
    if (board.drawable?.checkCounters) {
        // ChessgroundX adds its check counter after caller shapes. Reserve a stack
        // slot for that existing badge without changing the counter renderer.
        const color = pieces.get(orig)?.color;
        let counter: Key | undefined;
        for (const [key, piece] of board.boardState?.pieces ?? pieces) {
            if (piece.color === color && board.kingRoles.includes(piece.role)) counter = key;
        }
        if (counter === orig) {
            stacked++;
            limit--;
        }
    }
    return nags
        .slice(0, limit)
        .map((nag, idx) => {
            const symbol = GLYPHS.find(glyph => glyph.id === nag)?.symbol ?? `$${nag}`;
            const svg = glyphSvgs[symbol]?.(idx + stacked);
            return {
                orig,
                brush: svg ? '' : undefined,
                customSvg: svg ? { html: svg } : undefined,
                label: svg ? undefined : { text: symbol, fill: 'purple' },
            };
        })
        .reverse();
}

export function toggleGlyph(nags: number[], id: number): number[] {
    if (nags.includes(id)) return nags.filter(nag => nag !== id);
    const exclusive = [GLYPH_GROUPS.move, GLYPH_GROUPS.position].find(group => group.some(glyph => glyph.id === id));
    return [...nags.filter(nag => !exclusive?.some(glyph => glyph.id === nag)), id];
}
