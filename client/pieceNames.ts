import * as cg from 'chessgroundx/types';
import * as util from 'chessgroundx/util';

import { _, N_ } from './i18n';
import type { Variant } from './variants';

// English names keyed by piece letter ('r', '+p'), translated only when shown.
export type PieceNameTable = Readonly<Record<string, string>>;

const CHESS: PieceNameTable = {
    k: N_('king'),
    q: N_('queen'),
    r: N_('rook'),
    b: N_('bishop'),
    n: N_('knight'),
    p: N_('pawn'),
};

const XIANGQI: PieceNameTable = {
    k: N_('king'),
    a: N_('advisor'),
    b: N_('elephant'),
    n: N_('horse'),
    r: N_('chariot'),
    c: N_('cannon'),
    p: N_('pawn'),
};

// Piece families whose k, q, r, b, n, p are the chess pieces (checked against their rules pages).
const FAMILY_TABLES: Readonly<Record<string, PieceNameTable>> = {
    standard: CHESS,
    capa: CHESS,
    seirawan: CHESS,
    shogun: CHESS,
    orda: CHESS,
    xiangqi: XIANGQI,
    janggi: XIANGQI,
};

/** A piece's full name, from the variant's own table, then its family's, else its letter. */
export function pieceName(variant: Variant, role: cg.Role, color: cg.Color): string {
    const letter = util.letterOf(role);
    const name =
        variant.pieceNamesByColor?.[color]?.[letter] ??
        variant.pieceNames?.[letter] ??
        FAMILY_TABLES[variant.pieceFamily]?.[letter];
    return name === undefined ? letter : _(name);
}
