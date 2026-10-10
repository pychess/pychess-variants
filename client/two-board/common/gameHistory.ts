import type { FairyStockfish } from 'ffish-es6';
import type * as cg from 'chessgroundx/types';
import { read } from 'chessgroundx/fen';
import { letterOf } from 'chessgroundx/util';

import { uci2cg } from '../../chess';
import type { MsgBoard, Step } from '../../messages';
import type { BugBoardName } from '../../types';

// The JS binding has no piece_to_partner(). Mirror its capture demotion for the
// supported two-board variants; isCapture excludes Chess960 king-to-rook castling.
function pieceToPartner(fen: string, move: string, dimensions: cg.BoardDimensions): string {
    const pieces = read(fen, dimensions).pieces;
    const cgMove = uci2cg(move);
    const source = cgMove.slice(0, 2) as cg.Key;
    const target = cgMove.slice(2, 4) as cg.Key;
    const mover = pieces.get(source);
    let captured = pieces.get(target);
    if (!captured && mover?.role === 'p-piece' && source[0] !== target[0]) {
        // En passant captures the pawn on the destination file and origin rank.
        captured = pieces.get((target[0] + source[1]) as cg.Key);
    }
    if (!captured || captured.color === mover?.color) throw new Error('Missing captured partner piece');
    // Bughouse and Makbug promotions originate from pawns. Supply has no promotions.
    return letterOf(captured.promoted ? 'p-piece' : captured.role, captured.color === 'white');
}

export function materializeTwoBoardHistory(msg: MsgBoard, ffish: FairyStockfish): MsgBoard {
    const history = msg.twoBoardHistory;
    if (!history || msg.status < 0) return msg;
    const root = { ...msg.steps[0] };
    if (!root.fenB) throw new Error('Missing second history root');
    const dimensions = history.variant === 'supply' ? { width: 9, height: 10 } : { width: 8, height: 8 };
    const notation = history.variant === 'supply' ? ffish.Notation.XIANGQI_WXF : ffish.Notation.SAN;
    const fens = { a: root.fen, b: root.fenB };
    const lastMoves = { a: '', b: '' };
    const plies = { a: 0, b: 0 };
    const checks = { a: false, b: false };
    const steps: Step[] = [root];
    const allocated: InstanceType<FairyStockfish['Board']>[] = [];
    try {
        const boardA = new ffish.Board(history.variant, root.fen, history.chess960);
        allocated.push(boardA);
        const boardB = new ffish.Board(history.variant, root.fenB, history.chess960);
        allocated.push(boardB);
        const boards = { a: boardA, b: boardB };
        checks.a = boardA.isCheck();
        checks.b = boardB.isCheck();
        for (let index = 0; index < history.moves.length; index++) {
            try {
                const name = history.boards[index];
                if (name !== 'a' && name !== 'b') break;
                const partner: BugBoardName = name === 'a' ? 'b' : 'a';
                const board = boards[name];
                const move = history.moves[index];
                // The Python wrapper starts each operation from the current FEN,
                // including pockets supplied by the other board, without repetition history.
                board.setFen(fens[name]);
                let san = board.sanMove(move, notation);
                if (!san) break;
                const captured =
                    !move.includes('@') && board.isCapture(move) ? pieceToPartner(fens[name], move, dimensions) : '';
                if (!board.push(move)) break;
                fens[name] = board.fen(true, 0);
                if (captured) {
                    // Preserve the server's pocket insertion order until this board moves.
                    fens[partner] = fens[partner].replace(
                        /\[([^\]]*)\]/,
                        (_, pocket: string) => `[${pocket}${captured}]`,
                    );
                }
                // A board can wait for its partner's capture before escaping checkmate.
                // The archive reader only displays # when the game's status is MATE (1).
                if (msg.status !== 1) {
                    if (san.endsWith('#')) san = san.replace(/#/g, '+');
                }
                lastMoves[name] = move;
                checks[name] = board.isCheck();
                plies[name]++;
                steps.push({
                    ...history.metadata[index],
                    fen: fens.a,
                    fenB: fens.b,
                    move: lastMoves.a,
                    moveB: lastMoves.b,
                    boardName: name,
                    san,
                    // Preserve the existing archive's turn convention, including custom starts.
                    turnColor: plies[name] % 2 === 0 ? 'white' : 'black',
                    check: checks[name],
                });
            } catch (error) {
                console.warn('Stopped archived two-board replay at ply', index + 1, error);
                break;
            }
        }
    } finally {
        allocated.forEach(board => board.delete());
    }
    const complete = steps.length === history.moves.length + 1;
    return { ...msg, steps, check: complete ? checks.a : msg.check, checkB: complete ? checks.b : msg.checkB };
}
