import * as cg from 'chessgroundx/types';
import * as util from 'chessgroundx/util';
import { read } from 'chessgroundx/fen';

import { Variant, variantGroups } from './variants';

export const WHITE = 0;
export const BLACK = 1;

export const ranksUCI = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10'] as const;
export type UCIRank = (typeof ranksUCI)[number];
export type UCIKey = 'a0' | `${cg.File}${UCIRank}`;
export type UCIOrig = UCIKey | cg.DropOrig;
export type PromotionSuffix = cg.Letter | '+' | '-' | '';

export type UCIMove = `${UCIOrig}${UCIKey}`; // TODO: this is missing suffix for promotion which is also part of the move
export type CGMove = `${cg.Orig}${cg.Key}`; // TODO: this is missing suffix for promotion which is also part of the move

export type ColorName = 'White' | 'Black' | 'Red' | 'Blue' | 'Gold' | 'Pink' | 'Green';
export type PromotionType = 'regular' | 'shogi';
export type TimeControlType = 'incremental' | 'byoyomi';
export type CountingType = 'makruk' | 'asean';
export type MaterialPointType = 'janggi' | 'ataxx';
export type BoardMarkType = 'alice' | 'campmate' | 'racingkings' | 'kingofthehill';
export type PieceSoundType = 'regular' | 'atomic' | 'shogi';

const MAX_CUSTOM_FEN_LENGTH = 4096;
const FAIRY_STOCKFISH_MAX_ACTIVE_PIECES = 128;
const FAIRY_STOCKFISH_POCKET_SLOTS_PER_FILE = 2;

const handicapKeywords = ['HC', 'Handicap', 'Odds'];
export function isHandicap(name: string): boolean {
    return handicapKeywords.some(keyword => name.endsWith(keyword));
}

export function hasCastling(variant: Variant, color: cg.Color): boolean {
    if (variant.name === 'placement') return true;
    const castl = variant.startFen.split(' ')[2];
    if (color === 'white') {
        return castl.includes('KQ');
    } else {
        return castl.includes('kq');
    }
}

export function uci2cg(move: string): string {
    return move.replace(/10/g, ':');
}

export function uci2LastMove(move: string | undefined): cg.Orig[] | undefined {
    if (!move) return undefined;
    let moveStr = uci2cg(move);
    if (moveStr.startsWith('+')) moveStr = moveStr.slice(1);
    const comma = moveStr.indexOf(',');
    const lastMove = [moveStr.slice(0, 2) as cg.Orig, moveStr.slice(2, 4) as cg.Key];
    if (comma > -1) lastMove.push(moveStr.slice(-2) as cg.Key);
    return lastMove;
}

export function cg2uci(move: string): string {
    return move.replace(/:/g, '10');
}

// Get the latest move from FEN if ep square is given
export function lmBeforeEp(variant: Variant, fen: string): string {
    let lastMove = '';
    if (variant.rules.enPassant) {
        const parts = fen.split(' ');
        const epSquare = parts[3];
        if (epSquare !== '-') {
            const file = epSquare.slice(0, 1);
            const rank = Number(epSquare.slice(1));
            if (rank < 4) {
                lastMove = `${file}${rank - 1}${file}${rank + 1}`;
            } else {
                lastMove = `${file}${rank + 1}${file}${rank - 1}`;
            }
        }
    }
    return lastMove;
}

// TODO Will be deprecated after WASM Fairy integration
export function validFen(variant: Variant, fen: string): boolean {
    if (fen.length > MAX_CUSTOM_FEN_LENGTH) return false;

    const as = variant.alternateStart;
    if (as !== undefined) {
        if (
            Object.keys(as).some(key => {
                return as[key].fen.includes(fen);
            })
        )
            return true;
    }
    const variantName = variant.name;
    if (variantName === 'alice') return true;

    const startfen = variant.startFen;
    const start = startfen.split(' ');
    // console.log(start);
    const parts = fen.split(' ');
    // console.log(parts);
    // Need starting color
    if (parts.length < 2) return false;

    // Allowed characters in placement part
    const placement = parts[0];
    const startPlacement = start[0];
    let good =
        startPlacement +
        (variantName === 'orda' ? 'Hq' : '') +
        (variantName === 'dobutsu' ? 'Hh' : '') +
        (variantName === 'duck' || variantName === 'ataxx' || variant.rules.arrowing ? '*' : '') +
        '~+0123456789[]-';
    const alien = (element: string) => !good.includes(element);
    if (placement.split('').some(alien)) return false;

    if (variant.pocket && !pocketVariantMaterialFitsEngine(variant, placement)) return false;

    if (variantName === 'duck' && lc(placement, '*', false) > 1) return false;

    // RK currently not implemented due to not being able to check for checks
    // if (variantName === "racingkings") return false;

    // Brackets paired
    if (lc(placement, '[', false) !== lc(placement, ']', false)) return false;

    // Check with chessgroundx's parsing
    const dimensions = variant.board.dimensions;
    const width = dimensions.width;
    const height = dimensions.height;
    const boardState = read(placement, dimensions);

    // Correct board size
    if (lc(placement, '/', false) < height - 1) return false;
    for (const [k, _] of boardState.pieces) {
        const pos = util.key2pos(k);
        if (pos[0] > width - 1 || pos[1] > height - 1) return false;
    }

    // Starting colors
    if (parts[1] !== 'b' && parts[1] !== 'w') return false;

    // ataxx has no kings at all
    if (variantName === 'ataxx' || variantName === 'borderlands') return true;

    // Touching kings
    if (variantName !== 'atomic' && touchingKings(boardState.pieces)) return false;

    // Castling rights (piece virginity)
    good = variantName === 'seirawan' || variantName === 'shouse' ? 'KQABCDEFGHkqabcdefgh-' : start[2] + '-';
    const wrong = (element: string) => !good.includes(element);
    const rookStart: { [right: string]: cg.Pos } = {
        K: variantName === 'shako' ? [width - 2, 1] : [width - 1, 0],
        Q: variantName === 'shako' ? [1, 1] : [0, 0],
        k: variantName === 'shako' ? [width - 2, height - 2] : [width - 1, height - 1],
        q: variantName === 'shako' ? [1, height - 2] : [0, height - 1],
    };
    if (parts.length > 2 && variantName !== 'dobutsu') {
        if (parts[2].split('').some(wrong)) return false;

        // TODO: Checking S-chess960 FEN is tricky
        // Editor and Analysis board needs chess960 checkbox similar to new game dialog first

        // It is better to enable castling right validation for seirawan and shouse as well to be safe
        //if (variantName !== 'seirawan' && variantName !== 'shouse') {
        // Castling right need rooks and king placed in starting square
        // capablanca: "rnabqkbcnr/pppppppppp/10/10/10/10/PPPPPPPPPP/RNABQKBCNR w KQkq - 0 1",
        // shako: "c8c/ernbqkbnre/pppppppppp/10/10/10/10/PPPPPPPPPP/ERNBQKBNRE/C8C w KQkq - 0 1",
        for (const c of parts[2]) {
            const piece = rookStart[c] ? boardState.pieces.get(util.pos2key(rookStart[c])) : undefined;
            const color = c === c.toUpperCase() ? 'white' : 'black';
            switch (c) {
                case 'K':
                case 'Q':
                case 'k':
                case 'q':
                    if (!piece || !util.samePiece(piece, { role: 'r-piece', color: color })) return false;
                    // TODO check king position
                    break;
                // TODO Gating right
            }
        }
        //}
    }

    // Amazons has no royal pieces, so there is no king-count invariant to apply.
    if (variant.rules.arrowing) return true;

    // Number of kings
    const king = util.letterOf(variant.kingRoles[0]);
    const bK = countOcurrences(placement, king);
    const wK = countOcurrences(placement, king.toUpperCase());
    switch (variantName) {
        case 'spartan':
            if (bK === 0 || bK > 2 || wK !== 1) return false;
            break;
        case 'xiangfu':
            if (bK === 0 || bK > 2 || wK === 0 || wK > 2) return false;
            break;
        case 'horde':
            if (bK !== 1 || wK !== 0) return false;
            break;
        default:
            if (bK !== 1 || wK !== 1) return false;
    }

    return true;
}

function pocketVariantMaterialFitsEngine(variant: Variant, placement: string): boolean {
    const countMaterial = (fenPlacement: string): [Map<string, number>, number] => {
        const counts = new Map<string, number>();
        let total = 0;

        for (let i = 0; i < fenPlacement.length; i++) {
            const piece = fenPlacement[i];
            if (!/[A-Za-z]/.test(piece)) continue;

            // In capture-to-hand variants, "~" marks a promoted pawn that
            // returns to its base type when captured.
            const role = fenPlacement[i + 1] === '~' ? 'p' : piece.toLowerCase();
            counts.set(role, (counts.get(role) ?? 0) + 1);
            total++;
        }
        return [counts, total];
    };

    const pocketStart = placement.indexOf('[');
    const pocket =
        pocketStart >= 0
            ? placement.slice(pocketStart + 1, placement.indexOf(']', pocketStart))
            : placement.split('/').length > variant.board.dimensions.height
              ? placement.slice(placement.lastIndexOf('/') + 1)
              : '';
    const pocketCounts = new Map<string, number>();
    for (const piece of pocket) {
        if (!/[A-Za-z]/.test(piece)) continue;
        pocketCounts.set(piece, (pocketCounts.get(piece) ?? 0) + 1);
    }

    const pocketSlotsPerRole = FAIRY_STOCKFISH_POCKET_SLOTS_PER_FILE * variant.board.dimensions.width;
    if ([...pocketCounts.values()].some(count => count > pocketSlotsPerRole)) return false;

    const [counts, total] = countMaterial(placement);
    if (total > FAIRY_STOCKFISH_MAX_ACTIVE_PIECES) return false;

    const [startCounts] = countMaterial(variant.startFen.split(' ')[0]);
    return [...counts].every(([role, count]) => count <= Math.max(pocketSlotsPerRole, startCounts.get(role) ?? 0));
}

function countOcurrences(str: string, word: string): number {
    const escapedWord = word.replace(/[+]/g, '\\$&');
    const regex = new RegExp(escapedWord, 'g');
    return (str.match(regex) || []).length;
}

function diff(a: number, b: number): number {
    return Math.abs(a - b);
}

export function adjacent(key1: cg.Key, key2: cg.Key): boolean {
    return diff(key1.charCodeAt(0), key2.charCodeAt(0)) <= 1 && diff(key1.charCodeAt(1), key2.charCodeAt(1)) <= 1;
}

function touchingKings(pieces: cg.Pieces): boolean {
    let wk: cg.Key = 'a1',
        bk: cg.Key = 'h8';
    for (const [k, p] of pieces) {
        if (p.role === 'k-piece') {
            if (p.color === 'white') wk = k;
            if (p.color === 'black') bk = k;
        }
    }
    return adjacent(wk, bk);
}

// turn color part of the FEN
export function getTurnColor(fen: string): cg.Color {
    const c = fen.split(' ')[1];
    return c === 'w' ? 'white' : 'black';
}

// pocket part of the FEN (including brackets)
export function getPockets(fen: string): string {
    const placement = fen.split(' ')[0];
    let pockets = '';
    const bracketPos = placement.indexOf('[');
    if (bracketPos !== -1) pockets = placement.slice(bracketPos);
    return pockets;
}

// Get counting information for makruk et al
export function getCounting(fen: string): [number, number, string, string] {
    const parts = fen.split(' ');

    let countingPly = Number(parts[4]);
    if (isNaN(countingPly)) countingPly = 0;

    let countingLimit = Number(parts[3]);
    if (isNaN(countingLimit)) countingLimit = 0;

    const board = parts[0];
    const whitePieces = (board.match(/[A-Z]/g) || []).length;
    const blackPieces = (board.match(/[a-z]/g) || []).length;
    const pawns = (board.match(/[Pp]/g) || []).length;
    const countingType =
        countingLimit === 0 ? 'none' : pawns === 0 && (whitePieces <= 1 || blackPieces <= 1) ? 'piece' : 'board';

    const sideToMove = parts[1];
    const opponent = sideToMove === 'w' ? 'b' : 'w';
    const countingSide =
        countingType === 'none' || countingPly === 0 ? '' : countingPly % 2 === 0 ? sideToMove : opponent;

    return [countingPly, countingLimit, countingSide, countingType];
}

// Get janggi material points
export function getJanggiPoints(board: string): number[] {
    let choPoint = 0;
    let hanPoint = 1.5;
    for (const c of board) {
        switch (c) {
            case 'P':
                choPoint += 2;
                break;
            case 'A':
            case 'B':
                choPoint += 3;
                break;
            case 'N':
                choPoint += 5;
                break;
            case 'C':
                choPoint += 7;
                break;
            case 'R':
                choPoint += 13;
                break;

            case 'p':
                hanPoint += 2;
                break;
            case 'a':
            case 'b':
                hanPoint += 3;
                break;
            case 'n':
                hanPoint += 5;
                break;
            case 'c':
                hanPoint += 7;
                break;
            case 'r':
                hanPoint += 13;
                break;
        }
    }
    return [choPoint, hanPoint];
}

// Get ataxx material points
export function getAtaxxPoints(board: string): number[] {
    let redPoint = 0;
    let bluePoint = 0;
    for (const c of board) {
        switch (c) {
            case 'P':
                redPoint += 1;
                break;
            case 'p':
                bluePoint += 1;
                break;
        }
    }
    return [redPoint, bluePoint];
}

export function capturedRole(variant: Variant, piece: cg.Piece): cg.Role {
    return variant.pocket?.dropLoop ? piece.role : unpromotedRole(variant, piece);
}

export function unpromotedRole(variant: Variant, piece: cg.Piece): cg.Role {
    if (piece.promoted) {
        if (variant.promotion.type === 'shogi') return piece.role.slice(1) as cg.Role;
        else return 'p-piece';
    } else {
        return piece.role;
    }
}

export function promotedRole(variant: Variant, piece: cg.Piece): cg.Role {
    if (!piece.promoted && variant.promotion.roles.includes(piece.role)) {
        if (variant.promotion.type === 'shogi') return ('p' + piece.role) as cg.Role;
        else return util.roleOf(variant.promotion.order[0] as cg.Letter);
    } else {
        return piece.role;
    }
}

function neighbours(key: cg.Key) {
    const pos = util.key2pos(key);
    return [
        util.pos2key([pos[0] - 1, pos[1] - 1]),
        util.pos2key([pos[0] + 0, pos[1] - 1]),
        util.pos2key([pos[0] + 1, pos[1] - 1]),
        util.pos2key([pos[0] - 1, pos[1]]),
        util.pos2key([pos[0] + 1, pos[1]]),
        util.pos2key([pos[0] - 1, pos[1] + 1]),
        util.pos2key([pos[0] + 0, pos[1] + 1]),
        util.pos2key([pos[0] + 1, pos[1] + 1]),
    ];
}

// Convert a list of moves to chessground destination
export function moveDests(legalMoves: UCIMove[], fakeDrops: boolean, pieces: cg.Pieces, color: cg.Color): cg.Dests {
    const dests: cg.Dests = new Map();
    legalMoves.map(uci2cg).forEach(move => {
        const orig = move.slice(0, 2) as cg.Orig;
        const dest = move.slice(2, 4) as cg.Key;
        // fakeDrops parameter is used for ataxx only!
        if (fakeDrops) {
            // ataxx has infinite drop but has no pockets in FEN, so
            // we will enable moving to drop dests as well
            // and create drop moves in GameController.onUserMove()
            if (orig === 'P@') {
                const candidates = neighbours(dest);
                candidates.forEach(key => {
                    const piece = pieces.get(key);
                    if (piece && piece.role === 'p-piece' && piece.color === color) {
                        if (dests.has(key)) {
                            dests.get(key)!.push(dest);
                        } else {
                            dests.set(key, [dest]);
                        }
                    }
                });
            } else {
                if (dests.has(orig)) {
                    dests.get(orig)!.push(dest);
                } else {
                    dests.set(orig, [dest]);
                }
            }
        } else {
            if (dests.has(orig)) {
                dests.get(orig)!.push(dest);
            } else {
                dests.set(orig, [dest]);
            }
        }
    });
    return dests;
}

export function promotionSuffix(move: UCIMove | CGMove): PromotionSuffix {
    if (move.startsWith('+')) {
        return '+';
    } else {
        const comma = move.indexOf(',');
        if (comma > -1) move = move.substring(0, comma) as UCIMove;
        const last = move.slice(-1);
        if (last.match(/[a-z+-]/)) return last as PromotionSuffix;
        else return '';
    }
}

// Count given letter occurrences in a string
export function lc(str: string, letter: string, uppercase: boolean): number {
    if (uppercase) letter = letter.toUpperCase();
    else letter = letter.toLowerCase();
    let letterCount = 0;
    for (let position = 0; position < str.length; position++) if (str.charAt(position) === letter) letterCount += 1;
    return letterCount;
}

// Convert the string to uppercase if color is white,
// or convert it to lowercase if color is black
export function colorCase(color: cg.Color, str: string): string {
    if (color === 'white') return str.toUpperCase();
    else return str.toLowerCase();
}

export function colorIcon(variant: string, color: string) {
    if (variantGroups.shogi.variants.includes(variant)) {
        return color === 'Black' ? 'icon-sente' : 'icon-gote';
    } else {
        return `icon-${color.toLowerCase()}`;
    }
}
