import fs from 'fs';
import path from 'path';
import { beforeAll, expect, jest, test } from '@jest/globals';
import type { FairyStockfish } from 'ffish-es6';

import { materializeTwoBoardHistory } from '../client/two-board/common/gameHistory';
import type { MsgBoard, Step } from '../client/messages';
import { variantsIni } from '../client/variantsIni';

let ffish: FairyStockfish;
beforeAll(async () => {
    const moduleNs: any = await import('ffish-es6');
    const init = moduleNs.default?.default ?? moduleNs.default ?? moduleNs;
    ffish = await init({
        wasmBinary: fs.readFileSync(path.resolve('node_modules/ffish-es6/ffish.wasm')),
        printErr: () => {},
    });
    ffish.loadVariantConfig(variantsIni);
});

// Frozen from the previous load_game_bug_from_doc reader, before changing replay.
// Python tests separately assert that the actual compact wire payload carries these
// normalized moves and metadata, and that backend replay still reproduces these steps.
const fixtures = JSON.parse(fs.readFileSync(path.resolve('tests/twoBoardHistoryFixtures.json'), 'utf8')) as Array<{
    name: string;
    message: MsgBoard;
    expected: Step[];
}>;

test.each(fixtures)('$name matches the previous server on both boards after every move', fixture => {
    const msg = fixture.message;
    const before = JSON.stringify(msg);
    const actual = materializeTwoBoardHistory(msg, ffish);
    expect(actual.steps).toEqual(fixture.expected);
    expect(actual.fen).toBe(fixture.message.fen);
    expect(actual.check).toBe(fixture.message.check);
    expect(actual.checkB).toBe(fixture.message.checkB);
    expect(actual.steps.at(-1)!.fen + ' | ' + actual.steps.at(-1)!.fenB).toBe(actual.fen);
    expect(JSON.stringify(msg)).toBe(before);
});

test('already derived and active histories never allocate replay engines', () => {
    const msg = fixtures[0].message;
    const engine = {
        Board: jest.fn(() => {
            throw new Error('Unexpected replay');
        }),
    } as unknown as FairyStockfish;
    expect(materializeTwoBoardHistory({ ...msg, status: -1 }, engine).status).toBe(-1);
    const derived = { ...msg, twoBoardHistory: undefined };
    expect(materializeTwoBoardHistory(derived, engine)).toBe(derived);
    expect(engine.Board).not.toHaveBeenCalled();
});

test('an invalid move keeps the valid prefix and authoritative final state', () => {
    const source = fixtures[0].message;
    const msg = {
        ...source,
        twoBoardHistory: { ...source.twoBoardHistory!, moves: ['e2e4', 'e2e4'], boards: ['a', 'a'] as ('a' | 'b')[] },
    };
    const actual = materializeTwoBoardHistory(msg, ffish);
    expect(actual.steps).toHaveLength(2);
    expect(actual.steps[1].san).toBe('e4');
    expect(actual.fen).toBe(msg.fen);
    expect(actual.check).toBe(msg.check);
    expect(actual.checkB).toBe(msg.checkB);
});
