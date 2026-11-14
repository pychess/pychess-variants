import * as cg from 'chessgroundx/types';

import { ChessgroundController } from './cgCtrl';
import { Variant } from './variants';

/** How a pocket's roles are laid out: rows of `pocketLength`, one row or two. */
export function pocketShape(variant: Variant, color: cg.Color): { pieceRows: number; pocketLength: number } {
    const roles = variant.pocket?.roles[color] ?? [];
    const pieceRows = roles.length >= 8 ? 2 : 1;

    let pocketLength = roles.length;
    if (roles.length === 8) {
        pocketLength = 4;
    } else if (pieceRows === 2) {
        pocketLength = Math.min(roles.length, variant.board.dimensions.width - 2);
    }
    return { pieceRows, pocketLength };
}

function setCssVars(ctrl: ChessgroundController, color: cg.Color, pocket: HTMLElement) {
    if (ctrl.variant.pocket) {
        const { pieceRows, pocketLength } = pocketShape(ctrl.variant, color);
        pocket.style.setProperty('--piecerows', `${pieceRows}`);
        pocket.style.setProperty('--pocketLength', `${pocketLength}`);
    }
}

export function setPocketRowCssVars(ctrl: ChessgroundController): void {
    const pocket0 = document.getElementById('pocket0') as HTMLElement;
    const pocket1 = document.getElementById('pocket1') as HTMLElement;
    setCssVars(ctrl, ctrl.flipped() ? ctrl.mycolor : ctrl.oppcolor, pocket0);
    setCssVars(ctrl, ctrl.flipped() ? ctrl.oppcolor : ctrl.mycolor, pocket1);
}
