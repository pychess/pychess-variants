import type { DrawShape } from 'chessgroundx/draw';

import { uci2cg } from '../chess';

// Lichess displays at most three moves by the maneuvering piece, including
// the first move (which analysisCtrl already draws as the best-move arrow).
const MAX_MANEUVER_ARROWS = 3;

/** Reject overlapping maneuver paths, following Lichess's drawing rules.
 *  On non-8x8 boards, apply the same consecutive-origin rule without assuming
 *  that squares have standard chess geometry.
 */
function interferingArrow(from: string, to: string, occupied: Set<string>): boolean {
    if (from === to) return true;
    const square = (value: string): [number, number] | undefined => {
        if (!/^[a-h][1-8]$/.test(value)) return undefined;
        return [value.charCodeAt(0) - 97, Number(value[1]) - 1];
    };
    const a = square(from);
    const b = square(to);
    if (!a || !b) return occupied.has(to);

    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const knight = (Math.abs(dx) === 1 && Math.abs(dy) === 2) ||
        (Math.abs(dx) === 2 && Math.abs(dy) === 1);
    const straight = dx === 0 || dy === 0 || Math.abs(dx) === Math.abs(dy);
    if (!knight && !straight) return true;

    const path = [from];
    if (straight) {
        const stepX = Math.sign(dx);
        const stepY = Math.sign(dy);
        for (let x = a[0] + stepX, y = a[1] + stepY;
            x !== b[0] || y !== b[1]; x += stepX, y += stepY) {
            path.push(String.fromCharCode(97 + x) + String(y + 1));
        }
    }
    path.push(to);
    // The starting square can have been visited as a previous destination.
    // Lichess records occupied origins but only checks intervening and final squares.
    if (path.slice(1).some(sq => occupied.has(sq))) return true;
    path.forEach(sq => occupied.add(sq));
    return false;
}

/** Additional arrows for *consecutive* moves of the first PV piece.
 *  Opponent replies may intervene, but a move by any other friendly piece
 *  ends the maneuver immediately. The initial PV arrow is drawn elsewhere.
 */
export function maneuverArrows(pv: string): DrawShape[] {
    const moves = pv.trim().split(/\s+/);
    if (moves.length < 3) return [];
    const first = uci2cg(moves[0]);
    if (!/^[a-z][0-9:][a-z][0-9:]$/.test(first)) return [];

    const occupied = new Set<string>();
    if (interferingArrow(first.slice(0, 2), first.slice(2, 4), occupied)) return [];
    let square = first.slice(2, 4);
    const result: DrawShape[] = [];
    for (let i = 2; i < moves.length && result.length < MAX_MANEUVER_ARROWS - 1; i += 2) {
        const move = uci2cg(moves[i]);
        if (!/^[a-z][0-9:][a-z][0-9:]$/.test(move)) break;
        const orig = move.slice(0, 2);
        const dest = move.slice(2, 4);
        if (orig !== square || interferingArrow(orig, dest, occupied)) break;
        result.push({
            orig: orig as DrawShape['orig'],
            dest: dest as NonNullable<DrawShape['dest']>,
            brush: 'paleGreen',
            modifiers: { lineWidth: 6 },
        });
        square = dest;
    }
    return result;
}
