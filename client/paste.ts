import { h, VNode } from 'snabbdom';

import { FairyStockfish } from 'ffish-es6';

import { _ } from './i18n';
import { variantsIni } from './variantsIni';
import { allVariantsIni, ensureCataloguedVariantKeysLoaded, isBuiltinVariantName } from './variants';
import { cwdaEngineVariant, VARIANTS } from './variants';
import { alertDialog } from './alertDialog';
import { parseKif, resultString } from '../client/kif';
import { PyChessModel } from './types';
import { extractPgnTags, parsePgnVariantTag, resolvePgnMove, validatePgnFenTag } from './pgn';
import { importGameBugH } from '@/two-board/paste';
import { parseFirstPgnGame, type ParsedPgnMove } from './pgnParser';

const BRAINKING_SITE = '[Site "BrainKing.com (Prague, Czech Republic)"]';
const EMBASSY_FEN = '[FEN "rnbqkmcbnr/pppppppppp/10/10/10/10/PPPPPPPPPP/RNBQKMCBNR w KQkq - 0 1"]';
export function recordImportFfishError(text: string): void {
    const message = text.trim();
    if (/^Variant '.*' already exists\.$/.test(message)) return;
    console.warn(message);
}

export function pasteView(model: PyChessModel): VNode[] {
    const ffish: FairyStockfish = model.ffish;

    const importGame = async (model: PyChessModel, ffish: any) => {
        const e = document.getElementById('pgnpaste') as HTMLInputElement;
        //console.log('PGN:', e.value);
        let pgn = e.value;

        if (shouldImportAsBughouseBpgn(pgn)) {
            importGameBugH(pgn, model['home']);
            return;
        }

        // Add missing Variant tag and switch short/long castling notations
        if (pgn.indexOf(BRAINKING_SITE) !== -1 && pgn.indexOf(EMBASSY_FEN) !== -1) {
            const lines = pgn.split(/\n/);

            // fix FEN
            const fenIndex = lines.findIndex(elem => {
                return elem.startsWith('[FEN ');
            });
            lines[fenIndex] = `[FEN "${VARIANTS['embassy'].startFen}"]`;

            const variantIndex = lines.findIndex(elem => {
                return elem.startsWith('[Variant ');
            });
            if (variantIndex < 0) {
                // add missing variant tag
                lines.splice(variantIndex, 0, '[Variant "Capablanca"]');
            } else {
                // change variant to Capa
                lines.splice(variantIndex, 1, '[Variant "Capablanca"]');
            }

            lines.forEach((line, idx) => {
                if (idx > fenIndex)
                    lines[idx] = line.replace(/(O-O-O|O-O)/g, match => {
                        return match === 'O-O' ? 'O-O-O' : 'O-O';
                    });
            });
            pgn = lines.join('\n');
        }

        if (ffish !== null) {
            let namedVariant: string | undefined;
            try {
                const tag = parseFirstPgnGame(pgn)?.tags['Variant'];
                if (
                    tag &&
                    (tag.trim().toLowerCase().endsWith('960') || !isBuiltinVariantName(parsePgnVariantTag(tag).variant))
                ) {
                    namedVariant = tag.trim().toLowerCase();
                }
            } catch {
                // Keep malformed-PGN reporting in the existing import validation.
            }
            if (namedVariant && !VARIANTS[namedVariant]) {
                try {
                    await ensureCataloguedVariantKeysLoaded([namedVariant]);
                } catch (error) {
                    console.warn('Failed to load PGN variant metadata', error);
                }
            }
            ffish.loadVariantConfig(allVariantsIni(variantsIni));
            const XHR = new XMLHttpRequest();
            const FD = new FormData();
            let variant: string;
            let initialFen: string;
            let board;
            let mainlineMoves: string[] = [];

            try {
                const firstLine = pgn.slice(0, pgn.indexOf('\n'));

                // Fullwidth Colon(!) is used to separate game tag key-value pairs in Shogi KIF files :
                if (firstLine.includes('：') || firstLine.toUpperCase().includes('KIF')) {
                    const kif = parseKif(pgn);
                    //console.log(kif['moves'].join(', '));
                    const handicap = kif['handicap'];
                    const moves = kif['moves'];
                    let status = kif['status'];
                    let result = kif['result'];
                    const as = VARIANTS['shogi'].alternateStart;
                    const isHandicap = handicap !== '' && as![handicap] !== undefined;
                    if (isHandicap) {
                        FD.append('FEN', as![handicap].fen);
                    }

                    const fen = isHandicap ? as![handicap].fen : VARIANTS['shogi'].startFen;
                    board = new ffish.Board('shogi', fen);
                    let move;

                    for (let idx = 0; idx < moves.length; ++idx) {
                        move = moves[idx];
                        const pushed = board.push(move);
                        if (!pushed) {
                            void alertDialog({ text: 'Illegal move ' + move });
                            status = 10;
                            // LOSS for the moving player
                            result = resultString(false, idx + 1, isHandicap);
                            break;
                        }
                        mainlineMoves.push(move);
                    }

                    FD.append('Variant', 'shogi');
                    FD.append('Date', kif['date']);
                    FD.append('White', kif['sente']);
                    FD.append('Black', kif['gote']);
                    FD.append('TimeControl', kif['tc']);
                    FD.append('moves', mainlineMoves.join(' '));
                    FD.append('Result', result);
                    FD.append('Status', '' + status);
                    FD.append('final_fen', board.fen());
                    FD.append('username', model['username']);

                    board.delete();
                } else {
                    const game = parseFirstPgnGame(pgn);
                    if (!game) throw new Error(_('Invalid PGN'));

                    const variantInfo = parsePgnVariantTag(game.tags['Variant'] ?? 'chess');
                    variant = variantInfo.variant;

                    if (variant === 'alice') {
                        // TODO
                        const error = _('Importing Alice PGN is not supported');
                        e.setCustomValidity(error);
                        void alertDialog({ text: error });
                        return;
                    }
                    if (!(variant in VARIANTS)) {
                        throw new Error(`Unsupported PGN Variant tag: ${variantInfo.raw}`);
                    }

                    initialFen = VARIANTS[variant].startFen;
                    const f = game.tags['FEN'];
                    if (f) {
                        const fenValidation = validatePgnFenTag(ffish, f, variantInfo.variant, variantInfo.chess960);
                        if (fenValidation !== null) {
                            throw new Error(fenValidation);
                        }
                        initialFen = f;
                    }

                    const t = game.tags['Termination'];
                    //console.log("Termination:", t);
                    if (t) {
                        const status = getStatus(t.toLowerCase());
                        FD.append('Status', '' + status);
                    }

                    board = new ffish.Board(
                        variant === 'cwda' ? cwdaEngineVariant(initialFen) : variant,
                        initialFen,
                        variantInfo.chess960,
                    );

                    let node: ParsedPgnMove | undefined = game.children[0];
                    let ply = 1;
                    while (node) {
                        const resolved = resolvePgnMove(board, node, `ply ${ply}`);
                        if (!board.push(resolved.move)) {
                            throw new Error(`Illegal move at ply ${ply}: ${node.san}`);
                        }
                        mainlineMoves.push(resolved.move);
                        node = node.children?.[0];
                        ply += 1;
                    }

                    Object.entries(game.tags).forEach(([tag, value]) => {
                        FD.append(tag, value);
                    });
                    FD.append('moves', mainlineMoves.join(' '));
                    FD.append('final_fen', board.fen());
                    FD.append('username', model['username']);

                    board.delete();
                }
            } catch (err) {
                const message = buildImportErrorMessage(err, pgn, ffish);
                e.setCustomValidity(message);
                void alertDialog({ text: message });
                return;
            }

            XHR.onreadystatechange = function () {
                if (this.readyState !== 4) return;

                let response: Record<string, string> = {};
                if (this.responseText) {
                    try {
                        response = JSON.parse(this.responseText);
                    } catch {
                        response = {};
                    }
                }

                if (this.status === 200) {
                    if (response['gameId'] !== undefined) {
                        window.location.assign(model['home'] + '/' + response['gameId']);
                        return;
                    }
                    if (response['error'] !== undefined) {
                        void alertDialog({ text: response['error'] });
                        return;
                    }
                    void alertDialog({ text: _('Import failed') });
                    return;
                }

                void alertDialog({ text: response['error'] ?? `${_('Import failed')} (${this.status})` });
            };
            XHR.onerror = function () {
                void alertDialog({ text: _('Import failed') });
            };
            XHR.open('POST', '/import', true);
            XHR.send(FD);
        }
    };

    return [
        h('div.paste', [
            h('div.container', [
                h('strong', _('Paste the PGN text here')),
                h('textarea#pgnpaste', { attrs: { spellcheck: 'false' } }),
                h('div.import', [
                    h('button#import', { on: { click: () => importGame(model, ffish) } }, [
                        h('i', { class: { icon: true, 'icon-cloud-upload': true } }, _('IMPORT GAME')),
                    ]),
                ]),
            ]),
        ]),
    ];
}

/*
    ABORTED,
    MATE,
    RESIGN,
    STALEMATE,
    TIMEOUT,
    DRAW,
    FLAG,
    ABANDON,
    CHEAT,
    BYEGAME,
    INVALIDMOVE,
    UNKNOWNFINISH,
    VARIANTEND,
    CLAIM,
*/
function getStatus(termination: string) {
    if (termination.includes('checkmate')) return '1';
    if (termination.includes('resign')) return '2';
    if (termination.includes('stalemate')) return '3';
    if (termination.includes('draw')) return '5';
    if (termination.includes('repetition')) return '5';
    if (termination.includes('insufficient')) return '5';
    if (termination.includes('time')) return '6';
    if (termination.includes('abandon')) return '7';
    return '11'; // unknown
}

function buildImportErrorMessage(err: unknown, pgn: string, ffish: FairyStockfish): string {
    const tags = extractPgnTags(pgn);
    const variantInfo = parsePgnVariantTag(tags['Variant'] ?? 'chess');

    if (!(variantInfo.variant in VARIANTS)) {
        return `Unsupported PGN Variant tag: ${variantInfo.raw}.`;
    }

    const fen = tags['FEN'];
    if (fen) {
        const fenValidation = validatePgnFenTag(ffish, fen, variantInfo.variant, variantInfo.chess960);
        if (fenValidation !== null) return fenValidation;
    }

    const errorMessage = err instanceof Error ? err.message : typeof err === 'string' ? err : '';
    if (!errorMessage) return _('Invalid PGN');
    if (errorMessage.includes('memory access out of bounds')) {
        return 'Failed to parse PGN. Check [Variant], [FEN], and move text formatting.';
    }
    return errorMessage;
}

function shouldImportAsBughouseBpgn(pgn: string): boolean {
    if (/\[\s*WhiteA\s+["“]/i.test(pgn)) return true;
    if (/\[\s*Variant\s+["“]\s*Bughouse(?:\s*960|960)?\s*["”]\s*\]/i.test(pgn)) return true;

    const tags = extractPgnTags(pgn);
    const variant = tags['Variant']?.trim().toLowerCase();
    if (!variant) return false;

    return variant === 'bughouse' || variant === 'bughouse960' || variant === 'bughouse 960';
}
