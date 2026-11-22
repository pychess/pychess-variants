import type { DrawModifiers, DrawShape } from 'chessgroundx/draw';
import { read } from 'chessgroundx/fen';
import type { State } from 'chessgroundx/state';
import type { BoardDimensions, Key } from 'chessgroundx/types';
import { pos2key } from 'chessgroundx/util';

import type { AnalysisTreeNode } from './analysisTree';

type Board = Pick<State, 'dimensions' | 'boardState' | 'turnColor'>;
const square = '([a-p])([1-9][0-9]?|[:;<=>?@])';
const dropMove = new RegExp('^\\+?[A-Z]@' + square + '$');
const normalMove = new RegExp(
    '^' + square + square + '(?:[a-zA-Z+-](?:' + square + ')?)?(?:,' + square + square + ')?$',
);

// FSF uses decimal ranks; ChessgroundX uses single-character ranks through 16.
// Used only for drawings: the saved engine move remains untouched.
export function moveSquares(
    move: string,
    dimensions: BoardDimensions,
): { orig?: Key; dest: Key; wall?: Key } | undefined {
    const key = (file: string, rank: string): Key | undefined => {
        const x = file.charCodeAt(0) - 97;
        const y = /^\d+$/.test(rank) ? Number(rank) - 1 : rank.charCodeAt(0) - 49;
        return x < dimensions.width && y >= 0 && y < dimensions.height ? pos2key([x, y]) : undefined;
    };
    const drop = dropMove.exec(move);
    const normal = normalMove.exec(move);
    if (drop) {
        const dest = key(drop[1], drop[2]);
        return dest ? { dest } : undefined;
    }
    if (!normal) return undefined;
    const orig = key(normal[1], normal[2]);
    const dest = key(normal[3], normal[4]);
    const wall = normal[9] ? key(normal[9], normal[10]) : undefined;
    if (!orig || !dest || (normal[9] && !wall)) return undefined;
    return { orig, dest, wall };
}

export function shapesFromVariation(
    node: AnalysisTreeNode,
    board: Board,
    brush: string,
    modifiers?: DrawModifiers,
): DrawShape[] {
    const move = node.step.move && moveSquares(node.step.move, board.dimensions);
    if (!move) return [];
    const { orig, dest, wall } = move;
    const shapes: DrawShape[] = [{ orig: orig ?? dest, dest: orig ? dest : undefined, brush, modifiers }];
    // Read the engine-resolved position for promotions/demotions and promoted drops.
    // A suffix can also mean gating, so interpreting it as a promotion is unsafe.
    const piece = read(node.step.fen, board.dimensions).pieces.get(dest);
    if (
        piece?.color === board.turnColor &&
        (!orig || (!node.step.san?.startsWith('O-O') && piece.role !== board.boardState.pieces.get(orig)?.role))
    ) {
        shapes.push({ orig: dest, brush: 'green', piece: { ...piece, scale: 0.8 } });
    }
    if (wall) shapes.push({ orig: wall, brush, modifiers });
    return shapes;
}

// Adapted from lila ui/analyse/src/autoShape.ts::hiliteVariations
// (copyright the lila authors, AGPL-3.0). Visibility is decided by the host.
export function hiliteVariations(
    visible: AnalysisTreeNode[],
    selectedPath: string | undefined,
    autoShapes: DrawShape[],
    board: Board,
    gamebookEditor = false,
): DrawShape[] {
    const shapes = autoShapes.map(s => ({ ...s, modifiers: s.modifiers && { ...s.modifiers } }));
    if (visible.length < 2) return shapes;
    for (const [i, node] of visible.entries()) {
        const selected = node.path === selectedPath;
        const brush = !gamebookEditor ? 'variation' : i === 0 ? 'paleGreen' : 'paleRed';
        const moveShapes = shapesFromVariation(node, board, brush);
        const primary = moveShapes[0];
        if (!primary) continue;
        const hilite = selected ? '#3291ff' : primary.dest ? '#aaa' : undefined;
        const existing = autoShapes.findIndex(
            s => primary.dest && !s.piece && !s.customSvg && s.orig === primary.orig && s.dest === primary.dest,
        );
        if (existing >= 0) {
            // Retain the engine arrow's width, brush and layer; only outline it.
            shapes[existing].modifiers = { ...shapes[existing].modifiers, hilite: selected ? 'white' : undefined };
        }
        for (const shape of existing >= 0 ? moveShapes.slice(1) : moveShapes) {
            if (shape.piece && autoShapes.some(s => s.orig === shape.orig && s.piece?.role === shape.piece!.role))
                continue;
            shapes.push({ ...shape, modifiers: shape.piece ? shape.modifiers : { hilite }, below: true });
        }
    }
    return shapes;
}
