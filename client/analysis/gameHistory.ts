import type { FairyStockfish, Notation } from 'ffish-es6';
import type * as cg from 'chessgroundx/types';
import { read, writeBoard } from 'chessgroundx/fen';
import { roleOf } from 'chessgroundx/util';

import { getTurnColor, uci2cg } from '../chess';
import type { MsgBoard, Step } from '../messages';

// Finished-game positions are display data. Replay them with the browser's
// already loaded engine, leaving the server's authoritative final state alone.
export function materializeGameHistory(msg: MsgBoard, ffish: FairyStockfish, notation: Notation): MsgBoard {
    const history = msg.history;
    if (!history || msg.status < 0) return msg;

    const root = { ...msg.steps[0], move: undefined };
    const steps: Step[] = [root];
    const board = new ffish.Board(history.variant, root.fen, history.chess960);
    const covered = history.jieqiCovered ? { ...history.jieqiCovered } : undefined;
    const captures: Array<string | null> = [];
    let fen = root.fen;
    let countStarted = history.countStarted;
    let intervalIndex = 0;
    let intervalStart = -1;
    let intervalEnd = -1;
    if (history.analysis?.[0]) root.analysis = history.analysis[0];

    try {
        for (let index = 0; index < history.moves.length; index++) {
            try {
                const ply = index + 1;
                if (history.countIntervals !== undefined) {
                    if (ply >= intervalEnd) {
                        const interval = history.countIntervals[intervalIndex++];
                        countStarted = interval ? -1 : 0;
                        [intervalStart, intervalEnd] = interval ?? [0, Infinity];
                    }
                    if (ply === intervalStart) countStarted = index;
                }

                let move = history.moves[index];
                const engineMove = covered ? move.replace(/[a-z]$/i, '') : move;
                let san = board.sanMove(engineMove, notation);
                const sanSAN = board.sanMove(engineMove);
                if (!san) break;

                if (covered) {
                    // Jieqi reveal identities are separate from the engine FEN.
                    // Match the server's transform instead of treating reveals
                    // as promotion moves in the native engine.
                    const cgMove = uci2cg(engineMove);
                    const source = cgMove.slice(0, 2) as cg.Key;
                    const target = cgMove.slice(2, 4) as cg.Key;
                    const dimensions = { width: 9, height: 10 } as const;
                    const pieces = read(fen, dimensions).pieces;
                    const piece = pieces.get(source);
                    if (!piece) break;
                    const squares = engineMove.match(/^([a-i]\d+)([a-i]\d+)/);
                    if (!squares) break;
                    const reveal = covered[squares[1]];
                    captures.push(covered[squares[2]]?.toLowerCase() ?? null);
                    if (reveal) {
                        move = engineMove + reveal.toLowerCase();
                        san += '=' + reveal.toLowerCase();
                        pieces.set(target, { color: piece.color, role: roleOf(reveal.toLowerCase() as cg.Letter) });
                    } else {
                        pieces.set(target, piece);
                    }
                    pieces.delete(source);
                    delete covered[squares[1]];
                    delete covered[squares[2]];
                    const parts = fen.split(' ');
                    parts[0] = writeBoard(pieces, dimensions);
                    parts[1] = parts[1] === 'w' ? 'b' : 'w';
                    fen = parts.join(' ');
                    board.setFen(fen);
                } else {
                    if (!board.push(move)) break;
                    fen = board.fen(history.showPromoted, countStarted);
                    // Manual count intervals affect subsequent FEN counters.
                    if (history.countIntervals !== undefined) board.setFen(fen);
                }

                let turnColor = getTurnColor(fen);
                if (history.usi) turnColor = turnColor === 'white' ? 'black' : 'white';
                const step: Step = { fen, move, san, sanSAN, turnColor, check: board.isCheck() };
                const whiteClock = history.clocksWhite?.[Math.ceil(ply / 2)];
                const blackClock = history.clocksBlack?.[Math.floor(ply / 2)];
                if (whiteClock !== undefined && blackClock !== undefined) step.clocks = [whiteClock, blackClock];
                const analysis = history.analysis?.[ply];
                if (analysis) step.analysis = analysis;
                steps.push(step);
            } catch (error) {
                console.warn('Stopped archived game replay at ply', index + 1, error);
                break;
            }
        }
    } finally {
        board.delete();
    }

    return {
        ...msg,
        steps,
        check: steps.length === history.moves.length + 1 ? steps[steps.length - 1].check : msg.check,
        ...(covered
            ? {
                  jieqiCaptureStack: captures,
                  jieqiCaptures: captures.filter((piece): piece is string => piece !== null),
              }
            : {}),
    };
}
