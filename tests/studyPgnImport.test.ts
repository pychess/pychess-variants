import fs from 'fs';
import path from 'path';

import { beforeAll, describe, expect, test } from '@jest/globals';

import { encodePgnUtf8Base64 } from '../client/pgn';

import { pgnParser as studyPgnParser } from '../client/pgnParser';

import {
    normalizeStudyPgnDocument,
    parseStudyPgnDocumentForImportWithEngines,
    parseStudyPgnForImport,
    parseStudyPgnForImportWithEngines,
    postNewStudyPgnImport,
    postStudyPgnImport,
    StudyPgnImportError,
    type ParsedStudyPgnDocument,
} from '../client/study/studyPgnImport';

let ffish: any;

beforeAll(async () => {
    const moduleNs: any = await import('ffish-es6');
    const initFfish = moduleNs.default?.default ?? moduleNs.default ?? moduleNs;
    ffish = await initFfish({
        wasmBinary: fs.readFileSync(path.resolve(process.cwd(), 'node_modules/ffish-es6/ffish.wasm')),
        printErr: () => {},
    });
});

const complete = {
    recursiveVariations: true,
    comments: true,
    nags: true,
    multipleGames: true,
};

function parsedDocument(): ParsedStudyPgnDocument {
    return {
        capabilities: complete,
        games: [
            {
                tags: {
                    Event: 'Opening Lab',
                    Variant: 'chess',
                    ChapterName: 'Sicilian ideas',
                    Orientation: 'black',
                },
                comments: ['Root note [%csl Ge4] [%pynag 3]'],
                children: [
                    {
                        san: 'e4',
                        comments: ['King pawn [%cal Re2e4]'],
                        nags: [1],
                        children: [
                            { san: 'e5', move: 'e7e5' },
                            { san: 'c5', move: 'c7c5', nags: [5] },
                        ],
                    },
                    { san: 'd4', move: 'd2d4', nags: [6] },
                ],
            },
        ],
    };
}

describe('Study PGN import core', () => {
    test.each(['makruk', 'cambodian', 'makpong'])('retains promoted pawn FEN markers for %s', variant => {
        const fen = '7k/8/P7/8/8/8/8/7K w - - 0 1';
        const [chapter] = normalizeStudyPgnDocument(ffish, {
            capabilities: complete,
            games: [{ tags: { Variant: variant, FEN: fen }, children: [{ move: 'a6a7m', san: '' }] }],
        });
        expect(chapter.tree.nodes[0].fen.split(' ')[0]).toContain('M~');
        const [restored] = normalizeStudyPgnDocument(ffish, {
            capabilities: complete,
            games: [{ tags: { Variant: variant, FEN: chapter.tree.nodes[0].fen }, children: [] }],
        });
        expect(restored.initialFen.split(' ')[0]).toContain('M~');
    });

    test('retains embedded snapshot promotion markers independently of the live variant', () => {
        const ini = '[importpromoted:chess]\npieceDemotion = true\n';
        const [chapter] = normalizeStudyPgnDocument(ffish, {
            capabilities: complete,
            games: [
                {
                    tags: {
                        Variant: 'importpromoted',
                        FEN: '7k/P7/8/8/8/8/8/7K w - - 0 1',
                        PyChessVariantIniEncoding: 'base64',
                        PyChessVariantIni: encodePgnUtf8Base64(ini),
                    },
                    children: [{ move: 'a7a8q', san: '' }],
                },
            ],
        });
        expect(chapter.tree.nodes[0].fen.split(' ')[0]).toContain('Q~');
    });

    test('keeps ordinary chess promotion FENs in the server format', () => {
        const [chapter] = normalizeStudyPgnDocument(ffish, {
            capabilities: complete,
            games: [
                {
                    tags: { FEN: '7k/P7/8/8/8/8/8/7K w - - 0 1' },
                    children: [{ move: 'a7a8q', san: '' }],
                },
            ],
        });
        expect(chapter.tree.nodes[0].fen.split(' ')[0]).toBe('Q6k/8/8/8/8/8/8/7K');
    });

    test.each([
        ['shogi', 'SHOGI_HODGES_NUMBER'],
        ['janggi', 'JANGGI'],
        ['xiangqi', 'XIANGQI_WXF'],
    ])('preserves display notation and PGN SAN for %s variations', (variant, notation) => {
        const board = new ffish.Board(variant);
        try {
            const moves: string[] = board.legalMoves().split(' ').slice(0, 2);
            const expected = moves.map(move => ({
                san: board.sanMove(move, ffish.Notation[notation]),
                sanSAN: board.sanMove(move),
            }));
            const [chapter] = normalizeStudyPgnDocument(ffish, {
                capabilities: complete,
                games: [{ tags: { Variant: variant }, children: moves.map(move => ({ move, san: '' })) }],
            });
            expect(chapter.tree.nodes.map(({ san, sanSAN }) => ({ san, sanSAN }))).toEqual(expected);
            expect(expected.some(node => node.san !== node.sanSAN)).toBe(true);
        } finally {
            board.delete();
        }
    });

    test('refuses parsers that can silently lose PGN structure', () => {
        const parsed = parsedDocument();
        parsed.capabilities = { ...complete, recursiveVariations: false };
        expect(() => normalizeStudyPgnDocument(ffish, parsed)).toThrow(/refuses to flatten or discard/);
    });

    test('replays a recursive parser AST into authoritative Study DTO data', () => {
        const [chapter] = normalizeStudyPgnDocument(ffish, parsedDocument());

        expect(chapter.name).toBe('Sicilian ideas');
        expect(chapter.variant).toBe('chess');
        expect(chapter.orientation).toBe('black');
        expect(chapter.initialFen).toBe('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1');
        expect(chapter.tags.Event).toBe('Opening Lab');
        expect(chapter.tags.ChapterName).toBeUndefined();
        expect(chapter.tags.Orientation).toBeUndefined();

        expect(chapter.tree.nodes).toHaveLength(4);
        const roots = chapter.tree.nodes.filter(node => node.parentId === null).sort((a, b) => a.order - b.order);
        expect(roots.map(node => node.move)).toEqual(['e2e4', 'd2d4']);
        const e4Children = chapter.tree.nodes
            .filter(node => node.parentId === roots[0].id)
            .sort((a, b) => a.order - b.order);
        expect(e4Children.map(node => node.move)).toEqual(['e7e5', 'c7c5']);
        expect(e4Children[1].annotations?.nags).toEqual([5]);

        expect(chapter.tree.rootAnnotations?.nags).toEqual([3]);
        expect(chapter.tree.rootAnnotations?.shapes).toEqual([{ orig: 'e4', brush: 'green' }]);
        expect(chapter.tree.rootAnnotations?.comments[0].text).toBe('Root note');
        expect(roots[0].annotations?.nags).toEqual([1]);
        expect(roots[0].annotations?.shapes).toEqual([{ orig: 'e2', dest: 'e4', brush: 'red' }]);
        expect(roots[0].annotations?.comments[0].text).toBe('King pawn');
    });

    test('infers Lichess-style automatic orientation when external PGN omits the tag', async () => {
        const [normal] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[Event "Automatic orientation"]

1. e4 e5 2. Nf3 *`,
        );
        expect(normal.orientation).toBe('black');

        const [finished] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[Event "Finished game"]
[Result "1-0"]

1. e4 1-0`,
        );
        expect(finished.orientation).toBe('white');

        const [gamebook] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[Event "Interactive lesson"]
[ChapterMode "gamebook"]

1. e4 e5 *`,
        );
        expect(gamebook.orientation).toBe('black');
    });

    test('uses a root lesson prompt to recover the learner side when Lichess omitted orientation', async () => {
        const [chapter] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[Event "Lichess lesson example"]
[ChapterMode "gamebook"]

{ Play the most common opening move. }
1. e4 e5 2. Nf3 Nc6 *`,
        );

        expect(chapter.orientation).toBe('white');
    });

    test('keeps the final-mover gamebook heuristic when the first prompt follows an opponent move', async () => {
        const [chapter] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[FEN "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1"]
[SetUp "1"]
[ChapterMode "gamebook"]

1... e5 { Now find White's reply. } 2. Nf3 *`,
        );

        expect(chapter.orientation).toBe('white');
    });

    test('does not let a source-game result force Lichess puzzle-pack gamebooks to face White', async () => {
        const [blackPuzzle, whitePuzzle] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[Event "World Blitz 2025 Open"]
[Result "0-1"]
[Variant "From Position"]
[FEN "8/5pk1/5p2/P3q3/1Q6/KP6/8/8 w - - 3 56"]
[SetUp "1"]
[ChapterMode "gamebook"]

56. a6 { Let's start off with an easy one. } 56... Qa1# 0-1

[Event "WRBC 2025 Rapid Open"]
[Result "1-0"]
[Variant "From Position"]
[FEN "3RRbk1/pbq3p1/1p3rQB/2p5/5P2/8/PP4P1/7K b - - 6 26"]
[SetUp "1"]
[ChapterMode "gamebook"]

{ Find the combination. } 26... Qxd8 27. Qxg7# 1-0`,
        );

        expect(blackPuzzle.orientation).toBe('black');
        expect(whitePuzzle.orientation).toBe('white');
    });

    test('keeps the root side for move-less lessons whose exported orientation is unknowable', async () => {
        const [chapter] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[Variant "From Position"]
[FEN "8/8/8/8/8/8/4K3/7k b - - 0 1"]
[SetUp "1"]
[ChapterMode "gamebook"]

{ Introduction only. } *`,
        );

        expect(chapter.orientation).toBe('black');
    });

    test('parses raw PGN through Fairy-Stockfish and merges duplicate legal branches like Lichess', async () => {
        const [chapter] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[Event "Duplicate variations"]

1. e4 e5 2. Nf3 Nc6
    (2... Nc6 3. Bb5 a6)
    (2... Nc6 3. Bc4 Nf6)
    (2... d6 3. d4 exd4)
3. d4 exd4 *`,
        );

        const children = (parentId: string | null) =>
            chapter.tree.nodes.filter(node => node.parentId === parentId).sort((a, b) => a.order - b.order);
        const e4 = children(null)[0];
        const e5 = children(e4.id)[0];
        const nf3 = children(e5.id)[0];
        const [nc6, d6] = children(nf3.id);

        expect(children(null).map(node => node.san)).toEqual(['e4']);
        expect(children(nf3.id).map(node => node.san)).toEqual(['Nc6', 'd6']);
        expect(children(nc6.id).map(node => node.san)).toEqual(['d4', 'Bb5', 'Bc4']);
        expect(children(d6.id).map(node => node.san)).toEqual(['d4']);
    });

    test('recursively merges duplicate branches below an already merged move', async () => {
        const [chapter] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            '1. e4 e5 2. Nf3 Nc6 (2... Nc6 3. Bc4 Bc5 4. c3) 3. Bc4 Bc5 4. d3 *',
        );

        const children = (parentId: string | null) =>
            chapter.tree.nodes.filter(node => node.parentId === parentId).sort((a, b) => a.order - b.order);
        let node = children(null)[0];
        for (const san of ['e5', 'Nf3', 'Nc6', 'Bc4', 'Bc5']) {
            const next = children(node.id);
            expect(next[0].san).toBe(san);
            node = next[0];
        }
        expect(children(node.id).map(child => child.san)).toEqual(['d3', 'c3']);
    });

    test('merges annotations from duplicate branches while keeping the original branch order', async () => {
        const [chapter] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `1. e4! {same note [%csl Ge4]}
                (1. e4!? {same note} {variation note [%cal Re2e4]} 1... c5)
             1... e5 *`,
        );

        const roots = chapter.tree.nodes.filter(node => node.parentId === null).sort((a, b) => a.order - b.order);
        expect(roots).toHaveLength(1);
        const e4 = roots[0];
        const children = chapter.tree.nodes.filter(node => node.parentId === e4.id).sort((a, b) => a.order - b.order);

        expect(children.map(node => node.san)).toEqual(['e5', 'c5']);
        expect(e4.annotations?.nags).toEqual([1, 5]);
        expect(e4.annotations?.comments.map(comment => comment.text)).toEqual(['same note\nvariation note']);
        expect(e4.annotations?.shapes).toEqual([
            { orig: 'e4', brush: 'green' },
            { orig: 'e2', dest: 'e4', brush: 'red' },
        ]);
    });

    test('preserves real Lichess event metadata while consuming Study structural tags', async () => {
        const imported = await parseStudyPgnDocumentForImportWithEngines(
            studyPgnParser,
            () => ffish,
            `[Event "World Blitz 2025 Open"]
[Site "https://lichess.org/broadcast/example"]
[Date "2025.12.26"]
[Round "1.7"]
[White "Musovic, Armin"]
[Black "Sanal, Vahap"]
[Result "0-1"]
[WhiteElo "2274"]
[WhiteTitle "FM"]
[WhiteFideId "939935"]
[BlackElo "2563"]
[BlackTitle "GM"]
[BlackFideId "6300545"]
[TimeControl "15 mins + 10 sec increment"]
[Variant "From Position"]
[ECO "?"]
[Opening "?"]
[StudyName "FIDE World Rapid & Blitz 2025 - Puzzle Pack"]
[ChapterName "Musovic, Armin - Sanal, Vahap"]
[ChapterURL "https://lichess.org/study/9LjyYZ9N/FXMbkAeX"]
[Annotator "https://lichess.org/@/Lichess"]
[FEN "8/5pk1/5p2/P3q3/1Q6/KP6/8/8 w - - 3 56"]
[SetUp "1"]
[ChapterMode "gamebook"]

56. a6 56... Qa1# 0-1`,
        );
        const [chapter] = imported.chapters;

        expect(imported.studyName).toBe('FIDE World Rapid & Blitz 2025 - Puzzle Pack');
        expect(chapter.name).toBe('Musovic, Armin - Sanal, Vahap');
        expect(chapter.variant).toBe('chess');
        expect(chapter.mode).toBe('gamebook');
        expect(chapter.tags).toMatchObject({
            Event: 'World Blitz 2025 Open',
            Site: 'https://lichess.org/broadcast/example',
            Date: '2025.12.26',
            Round: '1.7',
            White: 'Musovic, Armin',
            Black: 'Sanal, Vahap',
            Result: '0-1',
            WhiteElo: '2274',
            WhiteTitle: 'FM',
            WhiteFideId: '939935',
            BlackElo: '2563',
            BlackTitle: 'GM',
            BlackFideId: '6300545',
            TimeControl: '15 mins + 10 sec increment',
            Variant: 'From Position',
            ECO: '?',
            Opening: '?',
            Annotator: 'https://lichess.org/@/Lichess',
            FEN: '8/5pk1/5p2/P3q3/1Q6/KP6/8/8 w - - 3 56',
            SetUp: '1',
        });
        expect(chapter.tags.StudyName).toBeUndefined();
        expect(chapter.tags.ChapterName).toBeUndefined();
        expect(chapter.tags.ChapterURL).toBeUndefined();
        expect(chapter.tags.ChapterMode).toBeUndefined();
    });

    test('recovers current Lichess Practice computer mode that ordinary Study PGN omits', async () => {
        const [chapter] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[StudyName "Lichess Practice: Checkmate Patterns I"]
[ChapterName "Back Rank Mate"]
[ChapterURL "https://lichess.org/study/fE4k21MW/AbCd1234"]
[Termination "mate in 2"]

1. e4 e5 *`,
        );

        expect(chapter.mode).toBe('practice');
        expect(chapter.tags.Termination).toBe('mate in 2');
        expect(chapter.tags.ChapterURL).toBeUndefined();
    });

    test('keeps Lichess computer Practice on the root side when the exported mainline has odd length', async () => {
        const [chapter] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[StudyName "Lichess Practice: The Fork"]
[ChapterName "Fork Challenge #6 P"]
[ChapterURL "https://lichess.org/study/Qj281y1p/TsdeLDey"]
[Termination "-30cp in 3"]
[FEN "r1bq1rk1/3np1bp/p2p1pp1/1PpP3n/4PP1B/2N2Q2/PP1N2PP/R3KB1R b KQ - 1 1"]
[SetUp "1"]

1... Nxf4 2. Qxf4 g5 3. Qf2 gxh4 *`,
        );

        expect(chapter.mode).toBe('practice');
        expect(chapter.orientation).toBe('black');
        expect(chapter.tags.Termination).toBe('-30cp in 3');
    });

    test('materializes Lichess Practice default mate without changing unrelated or gamebook imports', async () => {
        const [missingGoal, gamebook, unrelated] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[StudyName "Lichess Practice: Piece Checkmates I"]
[ChapterURL "https://lichess.org/study/BJy6fEDf/AaBbCcDd"]

*

[StudyName "Lichess Practice: 7th-Rank Rook Pawn"]
[ChapterURL "https://lichess.org/study/MkDViieT/EeFfGgHh"]
[ChapterMode "gamebook"]

{ Interactive introduction. } *

[StudyName "Ordinary Lichess Study"]
[ChapterURL "https://lichess.org/study/9LjyYZ9N/FXMbkAeX"]

*`,
        );

        expect(missingGoal.mode).toBe('practice');
        expect(missingGoal.tags.Termination).toBe('mate');
        expect(gamebook.mode).toBe('gamebook');
        expect(gamebook.tags.Termination).toBeUndefined();
        expect(unrelated.mode).toBe('normal');
        expect(unrelated.tags.Termination).toBeUndefined();
    });

    test('keeps explicit PyChess chapter mode authoritative over Lichess Practice inference', () => {
        const parsed = parsedDocument();
        parsed.games[0].tags.PyChessStudyVersion = '1';
        parsed.games[0].tags.PyChessChapterMode = 'normal';
        parsed.games[0].tags.ChapterURL = 'https://lichess.org/study/fE4k21MW/AbCd1234';

        const [chapter] = normalizeStudyPgnDocument(ffish, parsed);

        expect(chapter.mode).toBe('normal');
        expect(chapter.tags.Termination).toBeUndefined();
    });

    test('normalizes multiple raw PGN games into separate chapters', async () => {
        const chapters = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[Event "First"]
[White "Alice"]
[Black "Bob"]

1. e4 e5 *

[Event "Second"]

1. d4 d5 *`,
        );

        expect(chapters).toHaveLength(2);
        expect(chapters.map(chapter => chapter.name)).toEqual(['Alice - Bob', 'Second']);
        expect(chapters.map(chapter => chapter.tree.nodes[0].move)).toEqual(['e2e4', 'd2d4']);
    });

    test('keeps raw move tokens variant-neutral until Fairy-Stockfish resolves them', async () => {
        const [chapter] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[Variant "Crazyhouse"]
[FEN "4k3/8/8/8/8/8/8/4K3[P] w - - 0 1"]

1. P@e4 *`,
        );

        expect(chapter.variant).toBe('crazyhouse');
        expect(chapter.tree.nodes).toHaveLength(1);
        expect(chapter.tree.nodes[0]).toMatchObject({ move: 'P@e4', san: 'P@e4' });
    });

    test('imports result, clock and evaluation directives without turning them into visible comments', () => {
        const parsed = parsedDocument();
        parsed.games[0].tags.Result = '1-0';
        parsed.games[0].comments = ['Root note [%csl Ge4] [%pynag 3] [%eval 0.25] [%pyclocks 300000,300000]'];
        const e4 = parsed.games[0].children[0];
        e4.comments = ['King pawn [%cal Re2e4] [%eval 0.42] [%clk 0:04:59] [%pyclocks 298765,300000]'];
        const e5 = e4.children![0];
        e5.comments = ['[%eval #3] [%clk 0:04:57] [%pyclocks 298765,297234]'];

        const [chapter] = normalizeStudyPgnDocument(ffish, parsed);
        const roots = chapter.tree.nodes.filter(node => node.parentId === null).sort((a, b) => a.order - b.order);
        const e4Node = roots[0];
        const e5Node = chapter.tree.nodes.find(node => node.parentId === e4Node.id && node.order === 0)!;

        expect(chapter.tags.Result).toBe('1-0');
        expect(chapter.tree.rootEval).toEqual({ cp: 25 });
        expect(chapter.tree.rootClocks).toEqual([300000, 300000]);
        expect(e4Node.eval).toEqual({ cp: -42 });
        expect(e4Node.clocks).toEqual([298765, 300000]);
        expect(e4Node.annotations?.comments.map(comment => comment.text)).toEqual(['King pawn']);
        expect(e5Node.eval).toEqual({ mate: 3 });
        expect(e5Node.clocks).toEqual([298765, 297234]);
        expect(e5Node.annotations).toBeUndefined();
    });

    test('stores root evaluations from the initial side-to-move point of view', async () => {
        const [chapter] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[FEN "4k3/8/8/8/8/8/8/4K3 b - - 0 1"]

{[%eval 0.25]} *`,
        );

        expect(chapter.tree.rootEval).toEqual({ cp: -25 });
    });

    test('imports standard clock directives by carrying known clocks down each variation', () => {
        const parsed = parsedDocument();
        parsed.games[0].comments = ['[%pyclocks 300000,300000]'];
        parsed.games[0].children[0].comments = ['[%clk 0:04:58]'];
        parsed.games[0].children[0].children![0].comments = ['[%clk 0:04:57]'];
        parsed.games[0].children[1].comments = ['[%clk 0:04:56]'];

        const [chapter] = normalizeStudyPgnDocument(ffish, parsed);
        const roots = chapter.tree.nodes.filter(node => node.parentId === null).sort((a, b) => a.order - b.order);
        const e4 = roots[0];
        const d4 = roots[1];
        const e5 = chapter.tree.nodes.find(node => node.parentId === e4.id && node.order === 0)!;

        expect(e4.clocks).toEqual([298000, 300000]);
        expect(e5.clocks).toEqual([298000, 297000]);
        expect(d4.clocks).toEqual([296000, 300000]);
    });

    test('reconstructs Lichess-style elapsed move clocks from a simple TimeControl tag', async () => {
        const [chapter] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[TimeControl "180+2"]

1. e4 {[%emt 0:00:10]} e5 {[%emt 0:00:12]} 2. Nf3 {[%emt 0:00:05]} *`,
        );
        const mainline = chapter.tree.nodes.sort((a, b) => a.order - b.order);

        expect(chapter.tags.TimeControl).toBe('180+2');
        expect(chapter.tree.rootClocks).toEqual([180000, 180000]);
        expect(mainline[0].clocks).toEqual([172000, 180000]);
        expect(mainline[1].clocks).toEqual([172000, 170000]);
        expect(mainline[2].clocks).toEqual([169000, 170000]);
        expect(mainline.every(node => node.annotations === undefined)).toBe(true);
    });

    test('uses explicit clocks as anchors before reconstructing later elapsed move times', async () => {
        const [chapter] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `1. d4 {[%clk 1:59:59] [%emt 0:00:30]} d5 {[%clk 1:59:50]}
2. c4 {[%emt 0:00:12]} Nf6 {[%emt 0:00:13]} *`,
        );
        const [d4, d5, c4, nf6] = chapter.tree.nodes;

        expect(chapter.tree.rootClocks).toBeUndefined();
        expect(d4.clocks).toBeUndefined();
        expect(d5.clocks).toEqual([7199000, 7190000]);
        expect(c4.clocks).toEqual([7187000, 7190000]);
        expect(nf6.clocks).toEqual([7187000, 7177000]);
        expect(chapter.tree.nodes.every(node => node.annotations === undefined)).toBe(true);
    });

    test('reconstructs elapsed clocks independently in sibling variations', async () => {
        const [chapter] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[TimeControl "60+1"]

1. e4 {[%emt 0:00:10]} e5 {[%emt 0:00:11]} (1... c5 {[%emt 0:00:20]})
2. Nf3 {[%emt 0:00:05]} *`,
        );
        const e4 = chapter.tree.nodes.find(node => node.parentId === null)!;
        const replies = chapter.tree.nodes
            .filter(node => node.parentId === e4.id)
            .sort((a, b) => a.order - b.order);
        const nf3 = chapter.tree.nodes.find(node => node.parentId === replies[0].id)!;

        expect(e4.clocks).toEqual([51000, 60000]);
        expect(replies.map(node => [node.san, node.clocks])).toEqual([
            ['e5', [51000, 50000]],
            ['c5', [51000, 41000]],
        ]);
        expect(nf3.clocks).toEqual([47000, 50000]);
    });

    test('leaves unsupported multi-stage TimeControl clocks unguessed while consuming valid emt metadata', async () => {
        const [chapter] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[TimeControl "40/7200:3600"]

1. e4 {[%emt 0:00:10]} *`,
        );

        expect(chapter.tags.TimeControl).toBe('40/7200:3600');
        expect(chapter.tree.rootClocks).toBeUndefined();
        expect(chapter.tree.nodes[0].clocks).toBeUndefined();
        expect(chapter.tree.nodes[0].annotations).toBeUndefined();
    });

    test('imports versioned PyChess lesson mode and root/node metadata losslessly', () => {
        const rootLesson = { hint: 'Find } the idea\nwith Unicode ✓' };
        const nodeLesson = { deviation: 'Wrong } answer\nTry again' };
        const parsed = parsedDocument();
        parsed.games[0].tags.PyChessStudyVersion = '1';
        parsed.games[0].tags.PyChessChapterMode = 'gamebook';
        parsed.games[0].tags.ChapterMode = 'gamebook';
        parsed.games[0].comments = [
            `Introduction [%pygamebook ${encodePgnUtf8Base64(JSON.stringify(rootLesson))}]`,
        ];
        parsed.games[0].children[0].comments = [
            `Correct feedback [%pygamebook ${encodePgnUtf8Base64(JSON.stringify(nodeLesson))}]`,
        ];

        const [chapter] = normalizeStudyPgnDocument(ffish, parsed);
        const first = chapter.tree.nodes.find(node => node.parentId === null && node.order === 0)!;

        expect(chapter.mode).toBe('gamebook');
        expect(chapter.tree.rootGamebook).toEqual(rootLesson);
        expect(first.gamebook).toEqual(nodeLesson);
        expect(chapter.tree.rootAnnotations?.comments.map(comment => comment.text)).toEqual(['Introduction']);
        expect(first.annotations?.comments.map(comment => comment.text)).toEqual(['Correct feedback']);
        expect(chapter.tags.PyChessStudyVersion).toBeUndefined();
        expect(chapter.tags.PyChessChapterMode).toBeUndefined();
        expect(chapter.tags.ChapterMode).toBeUndefined();
    });

    test('preserves a Lichess comment-only gamebook chapter at the root position', async () => {
        const [chapter] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `[Event "Comment-only lesson"]
[Variant "From Position"]
[ChapterName "Introduction"]
[Annotator "https://lichess.org/@/NoseKnowsAll"]
[FEN "R7/K5k1/P7/8/8/8/8/1r6 w - - 21 11"]
[SetUp "1"]
[ChapterMode "gamebook"]

{ Welcome to the study. This chapter introduces the lesson without any moves. }
*`,
        );

        expect(chapter.mode).toBe('gamebook');
        expect(chapter.orientation).toBe('white');
        expect(chapter.tree.nodes).toEqual([]);
        expect(chapter.tree.rootAnnotations?.comments).toEqual([
            expect.objectContaining({
                text: 'Welcome to the study. This chapter introduces the lesson without any moves.',
                sourceAuthor: 'https://lichess.org/@/NoseKnowsAll',
            }),
        ]);
    });

    test('imports the versioned conceal boundary and strips its internal tag', () => {
        const parsed = parsedDocument();
        parsed.games[0].tags.PyChessStudyVersion = '1';
        parsed.games[0].tags.PyChessChapterMode = 'conceal';
        parsed.games[0].tags.PyChessConcealPly = '1';

        const [chapter] = normalizeStudyPgnDocument(ffish, parsed);

        expect(chapter.mode).toBe('conceal');
        expect(chapter.concealPly).toBe(1);
        expect(chapter.tags.PyChessConcealPly).toBeUndefined();
    });

    test('does not interpret lesson directives without the PyChess extension version tag', () => {
        const encoded = encodePgnUtf8Base64(JSON.stringify({ hint: 'Opaque hint' }));
        const parsed = parsedDocument();
        parsed.games[0].comments = [`Visible note [%pygamebook ${encoded}]`];

        const [chapter] = normalizeStudyPgnDocument(ffish, parsed);

        expect(chapter.mode).toBe('normal');
        expect(chapter.tree.rootGamebook).toBeUndefined();
        expect(chapter.tree.rootAnnotations?.comments[0].text).toContain('[%pygamebook');
    });

    test('does not interpret forced-variation directives without the PyChess extension version tag', async () => {
        const [chapter] = await parseStudyPgnForImport(
            studyPgnParser,
            ffish,
            `1. e4 { visible note [%pyforcevariation] } *`,
        );

        expect(chapter.tree.nodes[0].forceVariation).toBeUndefined();
        expect(chapter.tree.nodes[0].annotations?.comments[0].text).toContain('[%pyforcevariation]');
    });

    test('preserves lesson metadata in normal mode and accepts the ChapterMode gamebook compatibility tag', () => {
        const encoded = encodePgnUtf8Base64(JSON.stringify({ hint: 'Draft hint' }));
        const normal = parsedDocument();
        normal.games[0].tags.PyChessStudyVersion = '1';
        normal.games[0].tags.PyChessChapterMode = 'normal';
        normal.games[0].comments = [`[%pygamebook ${encoded}]`];
        expect(normalizeStudyPgnDocument(ffish, normal)[0]).toMatchObject({
            mode: 'normal',
            tree: { rootGamebook: { hint: 'Draft hint' } },
        });

        const compatible = parsedDocument();
        compatible.games[0].tags.ChapterMode = 'gamebook';
        expect(normalizeStudyPgnDocument(ffish, compatible)[0].mode).toBe('gamebook');
    });

    test('rejects unsupported or malformed PyChess lesson extensions instead of silently dropping them', () => {
        const unsupported = parsedDocument();
        unsupported.games[0].tags.PyChessStudyVersion = '2';
        expect(() => normalizeStudyPgnDocument(ffish, unsupported)).toThrow(/Unsupported PyChess Study PGN version/);

        const badMode = parsedDocument();
        badMode.games[0].tags.PyChessStudyVersion = '1';
        badMode.games[0].tags.PyChessChapterMode = 'mystery';
        expect(() => normalizeStudyPgnDocument(ffish, badMode)).toThrow(/Invalid PyChess chapter mode/);

        const conflict = parsedDocument();
        conflict.games[0].tags.PyChessStudyVersion = '1';
        conflict.games[0].tags.PyChessChapterMode = 'normal';
        conflict.games[0].tags.ChapterMode = 'gamebook';
        expect(() => normalizeStudyPgnDocument(ffish, conflict)).toThrow(/conflicts/);

        const concealWithoutVersion = parsedDocument();
        concealWithoutVersion.games[0].tags.PyChessChapterMode = 'conceal';
        concealWithoutVersion.games[0].tags.PyChessConcealPly = '1';
        expect(() => normalizeStudyPgnDocument(ffish, concealWithoutVersion)).toThrow(/requires/);

        const concealOnNormal = parsedDocument();
        concealOnNormal.games[0].tags.PyChessStudyVersion = '1';
        concealOnNormal.games[0].tags.PyChessChapterMode = 'normal';
        concealOnNormal.games[0].tags.PyChessConcealPly = '1';
        expect(() => normalizeStudyPgnDocument(ffish, concealOnNormal)).toThrow(/only valid/);

        const malformedConceal = parsedDocument();
        malformedConceal.games[0].tags.PyChessStudyVersion = '1';
        malformedConceal.games[0].tags.PyChessChapterMode = 'conceal';
        malformedConceal.games[0].tags.PyChessConcealPly = '-1';
        expect(() => normalizeStudyPgnDocument(ffish, malformedConceal)).toThrow(/conceal boundary/);

        const malformed = parsedDocument();
        malformed.games[0].tags.PyChessStudyVersion = '1';
        malformed.games[0].comments = ['[%pygamebook definitely-not-base64]'];
        expect(() => normalizeStudyPgnDocument(ffish, malformed)).toThrow(/Invalid PyChess lesson metadata/);

        const malformedForce = parsedDocument();
        malformedForce.games[0].tags.PyChessStudyVersion = '1';
        malformedForce.games[0].children[0].comments = ['[%pyforcevariation nope]'];
        expect(() => normalizeStudyPgnDocument(ffish, malformedForce)).toThrow(/forced-variation metadata/);

        const multipleForce = parsedDocument();
        multipleForce.games[0].tags.PyChessStudyVersion = '1';
        multipleForce.games[0].children[0].comments = ['[%pyforcevariation]'];
        multipleForce.games[0].children[0].children = [{ san: 'e5', comments: ['[%pyforcevariation]'] }];
        expect(() => normalizeStudyPgnDocument(ffish, multipleForce)).toThrow(/more than one forced-variation marker/);

        const oversized = parsedDocument();
        oversized.games[0].tags.PyChessStudyVersion = '1';
        oversized.games[0].comments = [
            `[%pygamebook ${encodePgnUtf8Base64(JSON.stringify({ hint: 'x'.repeat(4001) }))}]`,
        ];
        expect(() => normalizeStudyPgnDocument(ffish, oversized)).toThrow(/Invalid PyChess lesson metadata/);
    });

    test('round-trips PyChess custom variant and description extension tags', () => {
        const ini = '[pgncustom:chess]\nstartFen = rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1\n';
        const description = 'Plans ✓\nsecond line';
        const encodedIni = Buffer.from(ini, 'utf8').toString('base64');
        const encodedDescription = Buffer.from(description, 'utf8').toString('base64');
        const [chapter] = normalizeStudyPgnDocument(ffish, {
            capabilities: complete,
            games: [
                {
                    tags: {
                        Variant: 'pgncustom',
                        PyChessVariant: 'pgncustom',
                        PyChessVariantIniEncoding: 'base64',
                        PyChessVariantIni: encodedIni,
                        PyChessChapterDescriptionEncoding: 'base64',
                        PyChessChapterDescription: encodedDescription,
                    },
                    children: [{ san: 'e4' }],
                },
            ],
        });

        expect(chapter.variant).toBe('pgncustom');
        expect(chapter.variantIni).toBe(ini);
        expect(chapter.description).toBe(description);
        expect(chapter.tree.nodes[0].move).toBe('e2e4');
        expect(chapter.tags.PyChessVariantIni).toBeUndefined();
    });

    test('reports ambiguous variant metadata instead of guessing', () => {
        const parsed = parsedDocument();
        parsed.games[0].tags.PyChessVariant = 'crazyhouse';
        expect(() => normalizeStudyPgnDocument(ffish, parsed)).toThrow(/Ambiguous PGN variant/);
    });

    test('parses through an injected future rich-parser adapter', async () => {
        const parser = { parse: async (_pgn: string) => parsedDocument() };
        const chapters = await parseStudyPgnForImport(parser, ffish, '[Event "ignored by fake parser"]');
        expect(chapters).toHaveLength(1);
        await expect(parseStudyPgnForImport(parser, ffish, '   ')).rejects.toBeInstanceOf(StudyPgnImportError);
    });

    test('can select a Fairy-Stockfish engine independently for every imported game', async () => {
        const seenEvents: string[] = [];
        const chapters = await parseStudyPgnForImportWithEngines(
            studyPgnParser,
            async game => {
                seenEvents.push(game.tags.Event ?? '');
                return ffish;
            },
            `[Event "First"]

1. e4 e5 *

[Event "Second"]

1. d4 d5 *`,
        );

        expect(seenEvents).toEqual(['First', 'Second']);
        expect(chapters).toHaveLength(2);
        expect(chapters.map(chapter => chapter.tree.nodes[0].move)).toEqual(['e2e4', 'd2d4']);
    });

    test('reports parsing and per-chapter normalization progress', async () => {
        const progress: Array<{ phase: string; completed: number; total: number }> = [];
        const chapters = await parseStudyPgnForImportWithEngines(
            studyPgnParser,
            async () => ffish,
            '1.e4 e5 *\n\n1.d4 d5 *',
            update => progress.push(update),
        );

        expect(chapters).toHaveLength(2);
        expect(progress).toEqual([
            { phase: 'parsing', completed: 0, total: 1 },
            { phase: 'parsing', completed: 1, total: 1 },
            { phase: 'normalizing', completed: 0, total: 2 },
            { phase: 'normalizing', completed: 1, total: 2 },
            { phase: 'normalizing', completed: 2, total: 2 },
        ]);
    });

    test('rejects a single authored line beyond the Lichess 600-ply Study guard before stack exhaustion', async () => {
        const sans: string[] = [];
        for (let ply = 0; ply < 601; ply++) sans.push(['Nf3', 'Nf6', 'Ng1', 'Ng8'][ply % 4]);

        await expect(parseStudyPgnForImport(studyPgnParser, ffish, `${sans.join(' ')} *`)).rejects.toThrow(
            /line exceeds 600 plies/,
        );
    });

    test('posts only normalized chapter data to the Study batch endpoint', async () => {
        const chapters = normalizeStudyPgnDocument(ffish, parsedDocument());
        let requestUrl = '';
        let requestInit: RequestInit | undefined;
        const fetcher = (async (url: RequestInfo | URL, init?: RequestInit) => {
            requestUrl = String(url);
            requestInit = init;
            return {
                ok: true,
                status: 200,
                json: async () => ({
                    ok: true,
                    imported: 1,
                    studyId: 'study001',
                    chapterId: 'chapter2',
                    url: '/study/study001/chapter2',
                }),
            } as Response;
        }) as typeof fetch;

        const result = await postStudyPgnImport('study001', chapters, fetcher, true);
        expect(result.imported).toBe(1);
        expect(requestUrl).toBe('/study/study001/import-pgn');
        expect(requestInit?.method).toBe('POST');
        const body = JSON.parse(String(requestInit?.body));
        expect(body.chapters[0].tree.nodes).toHaveLength(4);
        expect(body.sync).toBe(true);
    });
    test('posts normalized chapters and Study settings when PGN creates a new Study', async () => {
        const chapters = normalizeStudyPgnDocument(ffish, parsedDocument());
        let requestUrl = '';
        let requestInit: RequestInit | undefined;
        const fetcher = (async (url: RequestInfo | URL, init?: RequestInit) => {
            requestUrl = String(url);
            requestInit = init;
            return {
                ok: true,
                status: 200,
                json: async () => ({
                    ok: true,
                    imported: 1,
                    studyId: 'study001',
                    chapterId: 'chapter1',
                    url: '/study/study001/chapter1',
                }),
            } as Response;
        }) as typeof fetch;

        const result = await postNewStudyPgnImport(
            {
                name: 'Imported repertoire',
                visibility: 'unlisted',
                computer: 'member',
                explorer: 'owner',
                cloneable: 'contributor',
                shareable: 'nobody',
            },
            chapters,
            fetcher,
        );

        expect(result.imported).toBe(1);
        expect(requestUrl).toBe('/study/import-pgn');
        expect(requestInit?.method).toBe('POST');
        const body = JSON.parse(String(requestInit?.body));
        expect(body.name).toBe('Imported repertoire');
        expect(body.visibility).toBe('unlisted');
        expect(body.computer).toBe('member');
        expect(body.explorer).toBe('owner');
        expect(body.cloneable).toBe('contributor');
        expect(body.shareable).toBe('nobody');
        expect(body.chapters[0].tree.nodes).toHaveLength(4);
    });

});
