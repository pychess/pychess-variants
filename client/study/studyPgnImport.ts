import { decodePgnUtf8Base64, parsePgnVariantTag, resolvePgnMove } from '../pgn';
import type { Notation } from 'ffish-es6';
import { Notation as BoardNotation } from 'chessgroundx/types';
import { cataloguedShowPromoted, VARIANTS } from '../variants';
import type {
    ParsedPgnDocument,
    ParsedPgnGame,
    ParsedPgnMove,
    PgnParser,
    PgnParserCapabilities,
} from '../pgnParser';
import type { StudyChapterMode } from '../types';
import {
    newStudyNodeId,
    parseStudyGamebook,
    type StudyAnnotationsDto,
    type StudyEvalDto,
    type StudyGamebookDto,
    type StudyShapeDto,
    type StudyTreeDto,
} from './studyTree';

export type StudyPgnParserCapabilities = PgnParserCapabilities;
export type ParsedStudyPgnMove = ParsedPgnMove;
export type ParsedStudyPgnGame = ParsedPgnGame;
export type ParsedStudyPgnDocument = ParsedPgnDocument;
export type StudyPgnParser = PgnParser;

interface StudyPgnBoard {
    legalMoves(): string;
    sanMove(move: string, notation?: Notation): string;
    push(move: string): boolean;
    pop(): void;
    fen(showPromoted?: boolean): string;
    isCheck(): boolean;
    delete?(): void;
}

export interface StudyPgnEngine {
    Board: new (variant: string, fen?: string, chess960?: boolean) => StudyPgnBoard;
    Notation: typeof Notation;
    loadVariantConfig(config: string): void;
}

export interface StudyPgnImportChapter {
    name: string;
    variant: string;
    chess960: boolean;
    initialFen: string;
    orientation: 'white' | 'black';
    mode: StudyChapterMode;
    concealPly?: number;
    description: string;
    tags: Record<string, string>;
    tree: StudyTreeDto;
    variantIni?: string;
}

export interface StudyPgnImportDocument {
    chapters: StudyPgnImportChapter[];
    studyName?: string;
}

export interface StudyPgnImportResponse {
    ok: boolean;
    imported?: number;
    studyId?: string;
    chapterId?: string;
    url?: string;
    error?: string;
}

export interface StudyPgnNewStudySettings {
    name: string;
    visibility: string;
    computer: string;
    explorer: string;
    cloneable: string;
    shareable: string;
}

export class StudyPgnImportError extends Error {}

export type StudyPgnImportProgressPhase = 'parsing' | 'normalizing' | 'saving';

export interface StudyPgnImportProgress {
    phase: StudyPgnImportProgressPhase;
    completed: number;
    total: number;
}

export type StudyPgnImportProgressCallback = (progress: StudyPgnImportProgress) => void;

// Lichess independently caps one authored line at 600 plies even though a chapter
// may contain up to 3,000 total nodes. Keep the same guard here so a pathological
// deep mainline cannot exhaust the browser stack or make navigation unusable.
const STUDY_PGN_MAX_LINE_PLIES = 600;

function yieldToBrowser(): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, 0));
}

export function studyPgnGameUsesAlice(game: ParsedStudyPgnGame): boolean {
    const exact = game.tags.PyChessVariant?.trim().toLowerCase();
    if (exact) return exact === 'alice';
    return parsePgnVariantTag(game.tags.Variant ?? 'chess').variant === 'alice';
}

const BRUSH_BY_CODE: Record<string, StudyShapeDto['brush']> = {
    G: 'green',
    R: 'red',
    B: 'blue',
    Y: 'yellow',
};
const INTERNAL_TAGS = new Set([
    'StudyName',
    'ChapterName',
    'ChapterURL',
    'Orientation',
    'PyChessVariant',
    'PyChessStudyVersion',
    'PyChessChapterMode',
    'PyChessConcealPly',
    'ChapterMode',
    'PyChessChess960',
    'PyChessVariantIniEncoding',
    'PyChessVariantIni',
    'PyChessChapterDescriptionEncoding',
    'PyChessChapterDescription',
]);
let snapshotAliasCounter = 0;

function requireCompleteParser(capabilities: StudyPgnParserCapabilities): void {
    const missing: string[] = [];
    if (!capabilities.recursiveVariations) missing.push('recursive variations');
    if (!capabilities.comments) missing.push('comments');
    if (!capabilities.nags) missing.push('NAGs');
    if (!capabilities.multipleGames) missing.push('multiple games');
    if (missing.length) {
        throw new StudyPgnImportError(
            `The configured PGN parser is incomplete (${missing.join(', ')}). Study import refuses to flatten or discard PGN data.`,
        );
    }
}

function decodeUtf8Base64(value: string, tagName: string): string {
    try {
        return decodePgnUtf8Base64(value);
    } catch {
        throw new StudyPgnImportError(`Invalid UTF-8/base64 value in [${tagName}] tag.`);
    }
}
function decodeExtension(tags: Record<string, string>, name: string): string | undefined {
    const value = tags[name];
    const encoding = tags[`${name}Encoding`];
    if (value === undefined) {
        if (encoding !== undefined) throw new StudyPgnImportError(`[${name}Encoding] is present without [${name}].`);
        return undefined;
    }
    if (encoding !== 'base64') {
        throw new StudyPgnImportError(`Unsupported [${name}Encoding] value; expected base64.`);
    }
    return decodeUtf8Base64(value, name);
}

function snapshotRuntimeVariant(engine: StudyPgnEngine, variant: string, ini: string): string {
    const match = /^\s*\[([^\]:]+)(:[^\]]+)?\]/m.exec(ini);
    if (!match) throw new StudyPgnImportError('PyChessVariantIni has no readable variant section.');
    if (match[1].trim() !== variant) {
        throw new StudyPgnImportError('PyChessVariantIni section name does not match the PGN variant.');
    }
    snapshotAliasCounter += 1;
    const alias = `studyimport_${snapshotAliasCounter.toString(36)}`;
    const aliased =
        ini.slice(0, match.index) + match[0].replace(match[1], alias) + ini.slice(match.index + match[0].length);
    try {
        engine.loadVariantConfig(aliased);
    } catch (error) {
        throw new StudyPgnImportError(
            `Fairy-Stockfish rejected the embedded variant snapshot: ${error instanceof Error ? error.message : String(error)}`,
        );
    }
    return alias;
}

function parseShapeToken(raw: string): StudyShapeDto | undefined {
    const token = raw.trim();
    if (token.length !== 3 && token.length !== 5) return undefined;
    const brush = BRUSH_BY_CODE[token[0].toUpperCase()];
    if (!brush) return undefined;
    const orig = token.slice(1, 3);
    if (!/^[a-p][1-9:;<=>?@]$/i.test(orig)) return undefined;
    if (token.length === 3) return { orig: orig.toLowerCase(), brush };
    const dest = token.slice(3, 5);
    if (!/^[a-p][1-9:;<=>?@]$/i.test(dest)) return undefined;
    return { orig: orig.toLowerCase(), dest: dest.toLowerCase(), brush };
}

function addUniqueShape(shapes: StudyShapeDto[], shape: StudyShapeDto): void {
    if (!shapes.some(item => item.orig === shape.orig && item.dest === shape.dest && item.brush === shape.brush)) {
        shapes.push(shape);
    }
}

interface ParsedPgnComments {
    annotations?: StudyAnnotationsDto;
    gamebook?: StudyGamebookDto;
    forceVariation?: boolean;
    whiteEval?: StudyEvalDto;
    clock?: number;
    elapsed?: number;
    clocks?: [number, number];
}

// Only interpret opaque lesson comments when their version tag opts into the
// PyChess extension. Without it, [%pygamebook ...] remains an ordinary comment.
const PYCHESS_STUDY_PGN_VERSION = '1';
const STUDY_CHAPTER_MODES = new Set<StudyChapterMode>(['normal', 'practice', 'conceal', 'gamebook']);

// Lichess's ordinary Study PGN export serializes Interactive Lesson chapters as
// [ChapterMode "gamebook"], but it does not serialize the internal Practice-with-
// computer mode. Recover that otherwise-lost mode only for Studies that the current
// lila Practice curriculum explicitly curates. The IDs mirror
// modules/practice/src/main/PracticeSections.scala (inspected 2026-09-25).
const LICHESS_PRACTICE_STUDY_IDS = new Set([
    'BJy6fEDf',
    'fE4k21MW',
    '8yadFPpU',
    'PDkQDt6u',
    '96Lij7wH',
    'Rg2cMBZ6',
    'ByhlXnmM',
    '9ogFv8Ac',
    'tuoBxVE5',
    'Qj281y1p',
    'MnsJEWnI',
    'RUQASaZm',
    'o734CNqp',
    'ITWY4GN2',
    'lyVYjhPG',
    '9cKgYrHb',
    'g1fxVZu9',
    's5pLU7Of',
    'kdKpaYLW',
    'jOZejFWk',
    '49fDW0wP',
    '0YcGiH4Y',
    'CgjKPvxQ',
    'udx042D6',
    'Grmtwuft',
    'xebrDvFe',
    'A4ujYOer',
    'pt20yRkT',
    'MkDViieT',
    'pqUSUw8Y',
    'heQDnvq7',
    'wS23j5Tm',
]);

function isCurrentLichessPracticeChapter(tags: Record<string, string>): boolean {
    const chapterUrl = tags['ChapterURL']?.trim();
    if (!chapterUrl) return false;
    const match = /^https:\/\/(?:www\.)?lichess\.org\/study\/([A-Za-z0-9]{8})(?:\/[A-Za-z0-9]{8})?\/?$/.exec(
        chapterUrl,
    );
    return match !== null && LICHESS_PRACTICE_STUDY_IDS.has(match[1]);
}

function chapterTeaching(
    tags: Record<string, string>,
): {
    mode: StudyChapterMode;
    concealPly?: number;
    lessonExtension: boolean;
    inferredLichessPractice: boolean;
} {
    const version = tags['PyChessStudyVersion'];
    if (version !== undefined && version !== PYCHESS_STUDY_PGN_VERSION) {
        throw new StudyPgnImportError(`Unsupported PyChess Study PGN version: ${version}.`);
    }
    const rawMode = tags['PyChessChapterMode'];
    if (rawMode !== undefined && version !== PYCHESS_STUDY_PGN_VERSION) {
        throw new StudyPgnImportError('PyChessChapterMode requires [PyChessStudyVersion "1"].');
    }
    if (rawMode !== undefined && !STUDY_CHAPTER_MODES.has(rawMode as StudyChapterMode)) {
        throw new StudyPgnImportError(`Invalid PyChess chapter mode: ${rawMode}.`);
    }
    const compatible = tags['ChapterMode'];
    if (compatible !== undefined && compatible !== 'gamebook') {
        throw new StudyPgnImportError(`Unsupported ChapterMode: ${compatible}.`);
    }
    const inferredLichessPractice =
        rawMode === undefined && compatible === undefined && isCurrentLichessPracticeChapter(tags);
    const mode =
        (rawMode as StudyChapterMode | undefined) ??
        (compatible === 'gamebook' ? 'gamebook' : inferredLichessPractice ? 'practice' : 'normal');
    if (compatible === 'gamebook' && mode !== 'gamebook') {
        throw new StudyPgnImportError('ChapterMode conflicts with PyChessChapterMode.');
    }
    const rawConcealPly = tags['PyChessConcealPly'];
    if (rawConcealPly !== undefined && version !== PYCHESS_STUDY_PGN_VERSION) {
        throw new StudyPgnImportError('PyChessConcealPly requires [PyChessStudyVersion "1"].');
    }
    if (rawConcealPly !== undefined && mode !== 'conceal') {
        throw new StudyPgnImportError('PyChessConcealPly is only valid for concealed chapters.');
    }
    if (rawConcealPly !== undefined && !/^(?:0|[1-9]\d*)$/.test(rawConcealPly.trim())) {
        throw new StudyPgnImportError('Invalid PyChess conceal boundary.');
    }
    const concealPly = rawConcealPly === undefined ? undefined : Number(rawConcealPly);
    if (concealPly !== undefined && !Number.isSafeInteger(concealPly)) {
        throw new StudyPgnImportError('Invalid PyChess conceal boundary.');
    }
    return {
        mode,
        ...(mode === 'conceal' ? { concealPly: concealPly ?? 0 } : {}),
        lessonExtension: version === PYCHESS_STUDY_PGN_VERSION,
        inferredLichessPractice,
    };
}

function parseGamebookDirective(encoded: string): StudyGamebookDto {
    let raw: unknown;
    try {
        raw = JSON.parse(decodePgnUtf8Base64(encoded.trim()));
        return parseStudyGamebook(raw);
    } catch {
        throw new StudyPgnImportError('Invalid PyChess lesson metadata in PGN comment.');
    }
}

function parsePgnClock(value: string): number | undefined {
    const normalized = value.trim().replace(',', '.');
    const parts = normalized.split(':');
    if (parts.length !== 2 && parts.length !== 3) return undefined;
    if (!/^\d+$/.test(parts[0])) return undefined;

    const hours = Number(parts[0]);
    let minutes: number;
    let seconds: number;
    if (parts.length === 3) {
        if (!/^\d{1,2}$/.test(parts[1]) || !/^\d{1,2}(?:\.\d{1,3})?$/.test(parts[2])) return undefined;
        minutes = Number(parts[1]);
        seconds = Number(parts[2]);
    } else {
        // Lichess also accepts the older H:MM and H:MM.SS forms. In the
        // latter, the decimal digits are seconds rather than a fraction of a minute.
        if (!/^\d{1,2}(?:\.\d{1,3})?$/.test(parts[1])) return undefined;
        const minutesAndSeconds = Number(parts[1]);
        minutes = Math.trunc(minutesAndSeconds);
        seconds = (minutesAndSeconds - minutes) * 100;
    }
    if (minutes >= 60 || seconds >= 60) return undefined;

    const milliseconds = Math.round((hours * 3600 + minutes * 60 + seconds) * 1000);
    return Number.isSafeInteger(milliseconds) && milliseconds >= 0 ? milliseconds : undefined;
}

function parseFullClocks(value: string): [number, number] | undefined {
    const parts = value.split(',').map(part => Number(part.trim()));
    if (
        parts.length !== 2 ||
        parts.some(clock => !Number.isSafeInteger(clock) || clock < 0)
    )
        return undefined;
    return [parts[0], parts[1]];
}

interface StudyPgnTimeControl {
    initial: number;
    increment: number;
}

function parsePgnTimeControl(value: string | undefined): StudyPgnTimeControl | undefined {
    if (!value) return undefined;
    // Match the simple sudden-death / Fischer-increment form that Lichess can
    // use to reconstruct clocks from [%emt]. Multi-stage PGN controls such as
    // 40/7200:3600 need move-boundary semantics and are therefore left alone.
    const match = /^(\d+)(?:\+(\d+))?$/.exec(value.trim());
    if (!match) return undefined;
    const initial = Number(match[1]) * 1000;
    const increment = Number(match[2] ?? '0') * 1000;
    if (!Number.isSafeInteger(initial) || !Number.isSafeInteger(increment)) return undefined;
    return { initial, increment };
}

function parseWhiteEval(value: string): StudyEvalDto | undefined {
    const score = value.split(',', 1)[0].trim();
    const mate = /^#([+-]?\d+)$/.exec(score);
    if (mate) {
        const value = Number(mate[1]);
        return Number.isSafeInteger(value) ? { mate: value } : undefined;
    }
    if (!/^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$/.test(score)) return undefined;
    const cp = Math.round(Number(score) * 100);
    return Number.isSafeInteger(cp) ? { cp } : undefined;
}

function evalForTurn(whiteEval: StudyEvalDto | undefined, turnColor: 'white' | 'black'): StudyEvalDto | undefined {
    if (!whiteEval) return undefined;
    const factor = turnColor === 'black' ? -1 : 1;
    if (whiteEval.mate !== undefined) return { mate: whiteEval.mate * factor };
    if (whiteEval.cp !== undefined) return { cp: whiteEval.cp * factor };
    return undefined;
}

const PGN_ATTRIBUTION_MAX_LENGTH = 256;
const PGN_ATTRIBUTION_ID_MAX_LENGTH = 128;
const PGN_ANNO_RE = /\[%anno\s+(?:"([^"]*)"|([^\],]+))\s*(?:,\s*([^\]\s]+))?\s*\]/i;

function cleanPgnAttribution(value: string | undefined, maxLength: number): string | undefined {
    if (value === undefined) return undefined;
    const cleaned = [...value.replace(/[\r\n]+/g, ' ')]
        .filter(char => {
            const code = char.charCodeAt(0);
            return code >= 32 && code !== 127;
        })
        .join('')
        .trim();
    return cleaned && cleaned.length <= maxLength ? cleaned : undefined;
}

interface PgnCommentAttribution {
    sourceAuthor?: string;
    sourceAuthorId?: string;
}

function samePgnCommentAttribution(a: PgnCommentAttribution, b: PgnCommentAttribution): boolean {
    return a.sourceAuthor === b.sourceAuthor && a.sourceAuthorId === b.sourceAuthorId;
}

function stripPgnCommentAttribution(
    text: string,
    defaultSourceAuthor: string | undefined,
): { text: string; attribution: PgnCommentAttribution } {
    const match = PGN_ANNO_RE.exec(text);
    if (!match) {
        return {
            text,
            attribution: defaultSourceAuthor ? { sourceAuthor: defaultSourceAuthor } : {},
        };
    }
    const sourceAuthor = cleanPgnAttribution(match[1] ?? match[2], PGN_ATTRIBUTION_MAX_LENGTH);
    const sourceAuthorId = cleanPgnAttribution(match[3], PGN_ATTRIBUTION_ID_MAX_LENGTH);
    if (!sourceAuthor) {
        // Do not silently discard malformed attribution metadata. Keeping the
        // directive in the visible text is safer than inventing an author.
        return {
            text,
            attribution: defaultSourceAuthor ? { sourceAuthor: defaultSourceAuthor } : {},
        };
    }
    return {
        text: `${text.slice(0, match.index)}${text.slice(match.index + match[0].length)}`,
        attribution: { sourceAuthor, ...(sourceAuthorId ? { sourceAuthorId } : {}) },
    };
}

function commentsFromPgn(
    comments: readonly string[],
    rawNags: readonly number[] = [],
    lessonExtension = false,
    defaultSourceAuthor?: string,
): ParsedPgnComments {
    const shapes: StudyShapeDto[] = [];
    const nags: number[] = [];
    for (const raw of rawNags) {
        if (!Number.isInteger(raw) || raw < 1 || raw > 255) throw new StudyPgnImportError(`Invalid PGN NAG: ${raw}.`);
        if (!nags.includes(raw)) nags.push(raw);
    }

    let whiteEval: StudyEvalDto | undefined;
    let clock: number | undefined;
    let elapsed: number | undefined;
    let clocks: [number, number] | undefined;
    let gamebook: StudyGamebookDto | undefined;
    let forceVariation = false;
    const visibleComments: Array<{ text: string; attribution: PgnCommentAttribution }> = [];
    for (const original of comments) {
        const attributed = stripPgnCommentAttribution(original, defaultSourceAuthor);
        let text = attributed.text;
        text = text.replace(/\[%csl\s+([^\]]+)\]/gi, (full, body: string) => {
            const parsed = body.split(',').map(parseShapeToken);
            if (parsed.some(shape => shape === undefined)) return full;
            parsed.forEach(shape => addUniqueShape(shapes, shape!));
            return '';
        });
        text = text.replace(/\[%cal\s+([^\]]+)\]/gi, (full, body: string) => {
            const parsed = body.split(',').map(parseShapeToken);
            if (parsed.some(shape => !shape?.dest)) return full;
            parsed.forEach(shape => addUniqueShape(shapes, shape!));
            return '';
        });
        text = text.replace(/\[%pynag\s+([^\]]+)\]/gi, (full, body: string) => {
            const parsed = body.split(',').map(value => Number(value.trim()));
            if (parsed.some(nag => !Number.isInteger(nag) || nag < 1 || nag > 255)) return full;
            parsed.forEach(nag => {
                if (!nags.includes(nag)) nags.push(nag);
            });
            return '';
        });
        text = text.replace(/\[%eval\s+([^\]]+)\]/gi, (full, body: string) => {
            const parsed = parseWhiteEval(body);
            if (!parsed) return full;
            whiteEval = parsed;
            return '';
        });
        text = text.replace(/\[%clk\s+([^\]]+)\]/gi, (full, body: string) => {
            const parsed = parsePgnClock(body);
            if (parsed === undefined) return full;
            clock = parsed;
            return '';
        });
        text = text.replace(/\[%emt\s+([^\]]+)\]/gi, (full, body: string) => {
            const parsed = parsePgnClock(body);
            if (parsed === undefined) return full;
            elapsed = parsed;
            return '';
        });
        text = text.replace(/\[%pyclocks\s+([^\]]+)\]/gi, (full, body: string) => {
            const parsed = parseFullClocks(body);
            if (!parsed) return full;
            clocks = parsed;
            return '';
        });
        if (lessonExtension) {
            text = text.replace(/\[%pygamebook\s+([^\]]+)\]/gi, (_full, body: string) => {
                if (gamebook) throw new StudyPgnImportError('Duplicate PyChess lesson metadata on one position.');
                gamebook = parseGamebookDirective(body);
                return '';
            });
            if (/\[%pygamebook\b/i.test(text)) {
                throw new StudyPgnImportError('Malformed PyChess lesson metadata in PGN comment.');
            }
            text = text.replace(/\[%pyforcevariation\s*\]/gi, () => {
                forceVariation = true;
                return '';
            });
            if (/\[%pyforcevariation\b/i.test(text)) {
                throw new StudyPgnImportError('Malformed PyChess forced-variation metadata in PGN comment.');
            }
        }
        const cleaned = text.trim();
        if (cleaned) visibleComments.push({ text: cleaned, attribution: attributed.attribution });
    }

    const annotations: StudyAnnotationsDto = {
        shapes,
        comments: visibleComments.map(({ text, attribution }) => ({
            id: newStudyNodeId(),
            author: 'import',
            text,
            ...attribution,
        })),
        nags,
    };
    return {
        ...(annotations.shapes.length || annotations.comments.length || annotations.nags.length ? { annotations } : {}),
        ...(gamebook ? { gamebook } : {}),
        ...(forceVariation ? { forceVariation: true } : {}),
        ...(whiteEval ? { whiteEval } : {}),
        ...(clock !== undefined ? { clock } : {}),
        ...(elapsed !== undefined ? { elapsed } : {}),
        ...(clocks ? { clocks } : {}),
    };
}

function canonicalTags(rawTags: Record<string, string>): Record<string, string> {
    const tags: Record<string, string> = {};
    for (const [name, value] of Object.entries(rawTags)) {
        if (INTERNAL_TAGS.has(name)) continue;
        if (!/^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(name)) {
            throw new StudyPgnImportError(`Invalid PGN tag name: ${name}.`);
        }
        if (typeof value !== 'string') throw new StudyPgnImportError(`Invalid value for PGN tag ${name}.`);
        const cleaned = value.replace(/[\r\n]+/g, ' ').trim();
        if (cleaned) tags[name] = cleaned;
    }
    return tags;
}

function chapterName(tags: Record<string, string>, index: number): string {
    const explicit = tags['ChapterName']?.trim();
    if (explicit) return explicit;
    const white = tags['White']?.trim();
    const black = tags['Black']?.trim();
    if (white && black) return `${white} - ${black}`;
    if (white) return white;
    if (black) return black;
    const event = tags['Event']?.trim();
    return event || `Imported chapter ${index + 1}`;
}

function resolveVariant(tags: Record<string, string>): { variant: string; chess960: boolean } {
    const fromVariant = parsePgnVariantTag(tags['Variant'] ?? tags['PyChessVariant'] ?? 'chess');
    const exact = tags['PyChessVariant']?.trim().toLowerCase();
    if (exact && tags['Variant']) {
        const normalizedExact = parsePgnVariantTag(exact);
        if (normalizedExact.variant !== fromVariant.variant) {
            throw new StudyPgnImportError(
                `Ambiguous PGN variant: [Variant "${tags['Variant']}"] conflicts with [PyChessVariant "${tags['PyChessVariant']}"].`,
            );
        }
    }
    const raw960 = tags['PyChessChess960'];
    if (raw960 !== undefined && raw960 !== '0' && raw960 !== '1') {
        throw new StudyPgnImportError('PyChessChess960 must be 0 or 1.');
    }
    return {
        variant: exact || fromVariant.variant,
        chess960: raw960 === undefined ? fromVariant.chess960 : raw960 === '1',
    };
}

function turnColorFromFen(fen: string): 'white' | 'black' {
    const turn = fen.trim().split(/\s+/)[1];
    if (turn === 'w') return 'white';
    if (turn === 'b') return 'black';
    throw new StudyPgnImportError('Fairy-Stockfish returned a FEN without a valid side to move.');
}

function oppositeColor(color: 'white' | 'black'): 'white' | 'black' {
    return color === 'white' ? 'black' : 'white';
}

function lastMainlineTurnColor(
    initialFen: string,
    nodes: readonly StudyTreeDto['nodes'][number][],
): 'white' | 'black' {
    let color = turnColorFromFen(initialFen);
    let parentId: string | null = null;
    while (true) {
        const next = nodes.find(node => node.parentId === parentId && node.order === 0);
        if (!next) return color;
        color = next.turnColor;
        parentId = next.id;
    }
}

function pgnHasOutcome(tags: Record<string, string>): boolean {
    const result = tags['Result']?.trim();
    return result === '1-0' || result === '0-1' || result === '1/2-1/2';
}

function importedChapterOrientation(
    tags: Record<string, string>,
    mode: StudyChapterMode,
    initialFen: string,
    nodes: readonly StudyTreeDto['nodes'][number][],
    hasRootComment: boolean,
): 'white' | 'black' {
    const explicit = tags['Orientation']?.trim().toLowerCase();
    if (explicit === 'white' || explicit === 'black') return explicit;

    const rootTurn = turnColorFromFen(initialFen);
    // Match the recoverable parts of Lichess's automatic Study orientation when
    // its default PGN export omits the Orientation tag. Conceal and computer Practice
    // start from the root side to move. In Practice the saved children are discarded
    // and the learner plays an open-ended game from the root, so using the exported
    // mainline's final turn can incorrectly make the engine play the learner's first
    // move. Ordinary finished games use White by convention. Gamebooks are handled
    // first because a Study export can retain the source game's Result; that result is
    // game metadata and does not identify the learner side.
    if (mode === 'conceal' || mode === 'practice') return rootTurn;
    const finalTurn = lastMainlineTurnColor(initialFen, nodes);
    if (mode === 'gamebook') {
        // Lichess's outcome-less lesson example starts with a root prompt for the
        // learner but ends after an automatic opponent reply, so the root comment
        // remains a useful fallback in that narrower case. Real puzzle-pack exports
        // with a game outcome can also have root introductory text before a scripted
        // opponent move, so do not let such comments override the authored line.
        if (!pgnHasOutcome(tags) && hasRootComment) return rootTurn;
        return nodes.length ? oppositeColor(finalTurn) : rootTurn;
    }
    if (pgnHasOutcome(tags)) return 'white';
    return finalTurn;
}

type ClockState = [number | undefined, number | undefined];

function sameShape(a: StudyShapeDto, b: StudyShapeDto): boolean {
    return a.orig === b.orig && a.dest === b.dest && a.brush === b.brush;
}

function mergeAnnotations(
    current: StudyAnnotationsDto | undefined,
    incoming: StudyAnnotationsDto | undefined,
): StudyAnnotationsDto | undefined {
    if (!incoming) return current;
    if (!current) return incoming;

    const shapes = [...current.shapes];
    for (const shape of incoming.shapes) {
        if (!shapes.some(existing => sameShape(existing, shape))) shapes.push(shape);
    }

    const comments = [...current.comments];
    for (const comment of incoming.comments) {
        if (
            !comments.some(
                existing =>
                    existing.author === comment.author &&
                    existing.text === comment.text &&
                    existing.sourceAuthor === comment.sourceAuthor &&
                    existing.sourceAuthorId === comment.sourceAuthorId,
            )
        ) {
            comments.push(comment);
        }
    }

    const nags = [...current.nags];
    for (const nag of incoming.nags) {
        if (!nags.includes(nag)) nags.push(nag);
    }
    return { shapes, comments, nags };
}

function coalesceImportedComments(annotations: StudyAnnotationsDto | undefined): StudyAnnotationsDto | undefined {
    if (!annotations || annotations.comments.length < 2) return annotations;

    const comments: StudyAnnotationsDto['comments'] = [];
    for (const comment of annotations.comments) {
        const existing = comments.find(
            candidate =>
                candidate.author === comment.author &&
                samePgnCommentAttribution(candidate, comment),
        );
        if (existing) existing.text = `${existing.text}\n${comment.text}`;
        else comments.push({ ...comment });
    }
    return { ...annotations, comments };
}

function displayNotation(engine: StudyPgnEngine, variant: string): Notation | undefined {
    switch (VARIANTS[variant]?.notation) {
        case BoardNotation.SHOGI_ARBNUM:
            return engine.Notation.SHOGI_HODGES_NUMBER;
        case BoardNotation.JANGGI:
            return engine.Notation.JANGGI;
        case BoardNotation.XIANGQI_ARBNUM:
            return engine.Notation.XIANGQI_WXF;
        default:
            return undefined;
    }
}

function normalizeChildren(
    board: StudyPgnBoard,
    notation: Notation | undefined,
    showPromoted: boolean,
    parsedChildren: readonly ParsedStudyPgnMove[],
    parentId: string | null,
    nodes: StudyTreeDto['nodes'],
    path: string,
    parentClocks: ClockState = [undefined, undefined],
    increment = 0,
    lessonExtension = false,
    defaultSourceAuthor?: string,
    plyDepth = 0,
): void {
    const normalizedSiblings = nodes.filter(node => node.parentId === parentId);
    for (let sourceOrder = 0; sourceOrder < parsedChildren.length; sourceOrder++) {
        const parsed = parsedChildren[sourceOrder];
        const location = path ? `${path}.${sourceOrder + 1}` : `${sourceOrder + 1}`;
        const childPlyDepth = plyDepth + 1;
        if (childPlyDepth > STUDY_PGN_MAX_LINE_PLIES) {
            throw new StudyPgnImportError(
                `PGN line exceeds ${STUDY_PGN_MAX_LINE_PLIES} plies at ${location}. Split or shorten the chapter before importing it.`,
            );
        }
        const resolved = resolvePgnMove(board, parsed, location);
        // PGN SAN and display notation are different for Shogi/Janggi/Xiangqi.
        // Both must be generated from the parent position, before pushing the move.
        const san = notation === undefined ? resolved.san : board.sanMove(resolved.move, notation);
        if (!board.push(resolved.move)) throw new StudyPgnImportError(`Illegal move at ${location}: ${parsed.san}.`);
        try {
            const fen = board.fen(showPromoted);
            const turnColor = turnColorFromFen(fen);
            const parsedComments = commentsFromPgn(
                parsed.comments ?? [],
                parsed.nags ?? [],
                lessonExtension,
                defaultSourceAuthor,
            );
            const clockState: ClockState = parsedComments.clocks ? [...parsedComments.clocks] : [...parentClocks];
            let clockChanged = parsedComments.clocks !== undefined;
            if (!parsedComments.clocks) {
                const mover = turnColor === 'black' ? 0 : 1;
                if (parsedComments.clock !== undefined) {
                    clockState[mover] = parsedComments.clock;
                    clockChanged = true;
                } else if (parsedComments.elapsed !== undefined && clockState[mover] !== undefined) {
                    const computed = clockState[mover] - parsedComments.elapsed + increment;
                    // Lichess treats reconstructed non-positive clocks as unknown.
                    // Do the same instead of persisting an impossible negative state.
                    clockState[mover] = Number.isSafeInteger(computed) && computed > 0 ? computed : undefined;
                    clockChanged = true;
                }
            }
            const clocks =
                clockChanged && clockState[0] !== undefined && clockState[1] !== undefined
                    ? ([clockState[0], clockState[1]] as [number, number])
                    : undefined;
            const evalScore = evalForTurn(parsedComments.whiteEval, turnColor);
            const existing = normalizedSiblings.find(node => node.move === resolved.move);

            if (existing) {
                existing.annotations = mergeAnnotations(existing.annotations, parsedComments.annotations);
                if (!existing.annotations) delete existing.annotations;
                if (parsedComments.gamebook) existing.gamebook = parsedComments.gamebook;
                if (parsedComments.forceVariation) existing.forceVariation = true;
                if (evalScore) existing.eval = evalScore;
                if (clocks) existing.clocks = clocks;
                normalizeChildren(
                    board,
                    notation,
                    showPromoted,
                    parsed.children ?? [],
                    existing.id,
                    nodes,
                    location,
                    clockState,
                    increment,
                    lessonExtension,
                    defaultSourceAuthor,
                    childPlyDepth,
                );
                continue;
            }

            const id = newStudyNodeId();
            const node: StudyTreeDto['nodes'][number] = {
                id,
                parentId,
                order: normalizedSiblings.length,
                move: resolved.move,
                fen,
                turnColor,
                check: board.isCheck(),
                san,
                sanSAN: resolved.san,
                ...(parsedComments.annotations ? { annotations: parsedComments.annotations } : {}),
                ...(parsedComments.gamebook ? { gamebook: parsedComments.gamebook } : {}),
                ...(parsedComments.forceVariation ? { forceVariation: true } : {}),
                ...(evalScore ? { eval: evalScore } : {}),
                ...(clocks ? { clocks } : {}),
            };
            nodes.push(node);
            normalizedSiblings.push(node);
            normalizeChildren(
                board,
                notation,
                showPromoted,
                parsed.children ?? [],
                id,
                nodes,
                location,
                clockState,
                increment,
                lessonExtension,
                defaultSourceAuthor,
                childPlyDepth,
            );
        } finally {
            board.pop();
        }
    }
}

function normalizeGame(engine: StudyPgnEngine, game: ParsedStudyPgnGame, index: number): StudyPgnImportChapter {
    const tags = { ...game.tags };
    const { variant, chess960 } = resolveVariant(tags);
    const teaching = chapterTeaching(tags);
    const variantIni = decodeExtension(tags, 'PyChessVariantIni');
    const description = decodeExtension(tags, 'PyChessChapterDescription') ?? '';
    const runtimeVariant = variantIni ? snapshotRuntimeVariant(engine, variant, variantIni) : variant;
    if (chess960 && !tags['FEN']) throw new StudyPgnImportError('Chess960 PGN import requires an explicit [FEN] tag.');

    let board: StudyPgnBoard | undefined;
    try {
        board = new engine.Board(runtimeVariant, tags['FEN']?.trim() || '', chess960);
        const showPromoted = variantIni
            ? cataloguedShowPromoted(variantIni, board.fen())
            : (VARIANTS[variant]?.ui.showPromoted ?? false);
        const initialFen = board.fen(showPromoted);
        if (!initialFen) throw new StudyPgnImportError(`Unable to initialize PGN variant ${variant}.`);
        const nodes: StudyTreeDto['nodes'] = [];
        const defaultSourceAuthor = cleanPgnAttribution(tags['Annotator'], PGN_ATTRIBUTION_MAX_LENGTH);
        const rootComments = commentsFromPgn(
            game.comments ?? [],
            [],
            teaching.lessonExtension,
            defaultSourceAuthor,
        );
        const timeControl = parsePgnTimeControl(tags['TimeControl']);
        const rootEval = evalForTurn(rootComments.whiteEval, turnColorFromFen(initialFen));
        const rootClocks: [number, number] | undefined = rootComments.clocks
            ? [...rootComments.clocks]
            : timeControl
              ? [timeControl.initial, timeControl.initial]
              : undefined;
        normalizeChildren(
            board,
            displayNotation(engine, runtimeVariant),
            showPromoted,
            game.children,
            null,
            nodes,
            '',
            rootClocks ? [...rootClocks] : [undefined, undefined],
            timeControl?.increment ?? 0,
            teaching.lessonExtension,
            defaultSourceAuthor,
        );
        rootComments.annotations = coalesceImportedComments(rootComments.annotations);
        for (const node of nodes) node.annotations = coalesceImportedComments(node.annotations);
        if (nodes.filter(node => node.forceVariation).length > 1) {
            throw new StudyPgnImportError('PyChess Study PGN contains more than one forced-variation marker.');
        }
        const importedTags = canonicalTags(tags);
        // Lichess PracticeGoal defaults an absent/unrecognized Termination tag to
        // mate. Keep PyChess's stricter explicit-goal rule for authored Practice
        // Studies, but materialize the missing default when importing a chapter
        // whose Practice mode itself had to be recovered from the official Lichess
        // curriculum. Existing non-empty Termination values remain untouched so a
        // malformed source goal is still visible to PyChess validation.
        if (teaching.inferredLichessPractice && importedTags.Termination === undefined) {
            importedTags.Termination = 'mate';
        }
        return {
            name: chapterName(tags, index),
            variant,
            chess960,
            initialFen,
            orientation: importedChapterOrientation(
                tags,
                teaching.mode,
                initialFen,
                nodes,
                Boolean(rootComments.annotations?.comments.length),
            ),
            mode: teaching.mode,
            ...(teaching.mode === 'conceal' ? { concealPly: teaching.concealPly ?? 0 } : {}),
            description,
            tags: importedTags,
            tree: {
                nodes,
                ...(rootComments.annotations ? { rootAnnotations: rootComments.annotations } : {}),
                ...(rootComments.gamebook ? { rootGamebook: rootComments.gamebook } : {}),
                ...(rootEval ? { rootEval } : {}),
                ...(rootClocks ? { rootClocks } : {}),
            },
            ...(variantIni ? { variantIni } : {}),
        };
    } catch (error) {
        if (error instanceof StudyPgnImportError) throw error;
        throw new StudyPgnImportError(
            `Could not replay imported PGN chapter ${index + 1}: ${error instanceof Error ? error.message : String(error)}`,
        );
    } finally {
        board?.delete?.();
    }
}

export function normalizeStudyPgnDocument(
    engine: StudyPgnEngine,
    parsed: ParsedStudyPgnDocument,
): StudyPgnImportChapter[] {
    requireCompleteParser(parsed.capabilities);
    if (!parsed.games.length) throw new StudyPgnImportError('PGN contains no games.');
    return parsed.games.map((game, index) => normalizeGame(engine, game, index));
}

export async function parseStudyPgnForImport(
    parser: StudyPgnParser,
    engine: StudyPgnEngine,
    pgn: string,
    onProgress?: StudyPgnImportProgressCallback,
): Promise<StudyPgnImportChapter[]> {
    return parseStudyPgnForImportWithEngines(parser, () => engine, pgn, onProgress);
}

function importedStudyName(parsed: ParsedStudyPgnDocument): string | undefined {
    const names = parsed.games.map(game => game.tags['StudyName']?.replace(/[\r\n]+/g, ' ').trim());
    if (!names.length || names.some(name => !name)) return undefined;
    const first = names[0]!;
    if (!names.every(name => name === first)) return undefined;
    return first.slice(0, 100);
}

export async function parseStudyPgnDocumentForImportWithEngines(
    parser: StudyPgnParser,
    engineForGame: (game: ParsedStudyPgnGame, index: number) => StudyPgnEngine | Promise<StudyPgnEngine>,
    pgn: string,
    onProgress?: StudyPgnImportProgressCallback,
): Promise<StudyPgnImportDocument> {
    if (!pgn.trim()) throw new StudyPgnImportError('PGN text is empty.');
    onProgress?.({ phase: 'parsing', completed: 0, total: 1 });
    // Give the browser one paint before the synchronous structural parse begins.
    if (onProgress) await yieldToBrowser();
    const parsed = await parser.parse(pgn);
    requireCompleteParser(parsed.capabilities);
    if (!parsed.games.length) throw new StudyPgnImportError('PGN contains no games.');
    onProgress?.({ phase: 'parsing', completed: 1, total: 1 });

    const chapters: StudyPgnImportChapter[] = [];
    onProgress?.({ phase: 'normalizing', completed: 0, total: parsed.games.length });
    for (const [index, game] of parsed.games.entries()) {
        // Replay is CPU-bound. Yield between chapters so the dialog, progress bar,
        // and the rest of the page remain responsive during large Study imports.
        if (onProgress) await yieldToBrowser();
        chapters.push(normalizeGame(await engineForGame(game, index), game, index));
        onProgress?.({ phase: 'normalizing', completed: index + 1, total: parsed.games.length });
    }
    const studyName = importedStudyName(parsed);
    return { chapters, ...(studyName ? { studyName } : {}) };
}

export async function parseStudyPgnForImportWithEngines(
    parser: StudyPgnParser,
    engineForGame: (game: ParsedStudyPgnGame, index: number) => StudyPgnEngine | Promise<StudyPgnEngine>,
    pgn: string,
    onProgress?: StudyPgnImportProgressCallback,
): Promise<StudyPgnImportChapter[]> {
    return (await parseStudyPgnDocumentForImportWithEngines(parser, engineForGame, pgn, onProgress)).chapters;
}

export async function postStudyPgnImport(
    studyId: string,
    chapters: StudyPgnImportChapter[],
    fetcher: typeof fetch = fetch,
    sync?: boolean,
): Promise<StudyPgnImportResponse> {
    const response = await fetcher(`/study/${studyId}/import-pgn`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapters, ...(sync === undefined ? {} : { sync }) }),
    });
    let payload: StudyPgnImportResponse;
    try {
        payload = (await response.json()) as StudyPgnImportResponse;
    } catch {
        payload = { ok: false, error: `Study PGN import failed (${response.status})` };
    }
    if (!response.ok || !payload.ok) {
        throw new StudyPgnImportError(payload.error || `Study PGN import failed (${response.status})`);
    }
    return payload;
}

export async function postNewStudyPgnImport(
    settings: StudyPgnNewStudySettings,
    chapters: StudyPgnImportChapter[],
    fetcher: typeof fetch = fetch,
): Promise<StudyPgnImportResponse> {
    const response = await fetcher('/study/import-pgn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...settings, chapters }),
    });
    let payload: StudyPgnImportResponse;
    try {
        payload = (await response.json()) as StudyPgnImportResponse;
    } catch {
        payload = { ok: false, error: `Study PGN import failed (${response.status})` };
    }
    if (!response.ok || !payload.ok) {
        throw new StudyPgnImportError(payload.error || `Study PGN import failed (${response.status})`);
    }
    return payload;
}
