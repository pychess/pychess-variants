import fs from 'fs';
import path from 'path';

import { beforeAll, expect, test } from '@jest/globals';
import type { FairyStockfish, Notation } from 'ffish-es6';

import { materializeGameHistory } from '../client/analysis/gameHistory';
import type { MsgBoard } from '../client/messages';
import { variantsIni } from '../client/variantsIni';

let ffish: FairyStockfish;
let alice: FairyStockfish;

beforeAll(async () => {
    const modules = await Promise.all([import('ffish-es6'), import('ffish-alice-es6')]);
    [ffish, alice] = await Promise.all(
        modules.map(async (moduleNs: any, index) => {
            const init = moduleNs.default?.default ?? moduleNs.default ?? moduleNs;
            const packageName = index ? 'ffish-alice-es6' : 'ffish-es6';
            const engine = await init({
                wasmBinary: fs.readFileSync(
                    path.resolve('node_modules', packageName, index ? 'ffish-alice.wasm' : 'ffish.wasm'),
                ),
                printErr: () => {},
            });
            engine.loadVariantConfig(variantsIni);
            return engine;
        }),
    );
});

// Captured from Game.create_steps(), including cold-load archive conventions.
// These fixtures compare the browser engine with the existing server replay,
// rather than deriving expectations with the browser implementation under test.
const fixtures = JSON.parse(fs.readFileSync(path.resolve('tests/gameHistoryFixtures.json'), 'utf8')) as Array<{
    name: string;
    message: MsgBoard;
    expected: unknown[][];
}>;

function notation(engine: FairyStockfish, variant: string): Notation {
    if (variant.includes('shogi')) return engine.Notation.SHOGI_HODGES_NUMBER;
    if (variant === 'janggi') return engine.Notation.JANGGI;
    if (variant === 'xiangqi' || variant === 'jieqi') return engine.Notation.XIANGQI_WXF;
    return engine.Notation.SAN;
}

test.each(fixtures)('$name replay matches server positions, notation, checks, clocks, and analysis', fixture => {
    const engine = fixture.name === 'alice' ? alice : ffish;
    const before = JSON.stringify(fixture.message);
    const result = materializeGameHistory(fixture.message, engine, notation(engine, fixture.message.history!.variant));
    expect(
        result.steps.map(step => [
            step.fen,
            step.san ?? null,
            step.turnColor,
            step.check,
            step.clocks ?? null,
            step.analysis ?? null,
        ]),
    ).toEqual(fixture.expected);
    expect(result.fen).toBe(fixture.message.fen);
    expect(result.check).toBe(fixture.expected[fixture.expected.length - 1][3]);
    expect(result.pgn).toBe(fixture.message.pgn);
    expect(JSON.stringify(fixture.message)).toBe(before);
});

test('invalid historical moves keep the valid prefix and stored final state', () => {
    const source = fixtures[0].message;
    const msg = {
        ...source,
        history: { ...source.history!, moves: ['e2e4', 'e2e4', 'e7e5'] },
    };
    const result = materializeGameHistory(msg, ffish, ffish.Notation.SAN);
    expect(result.steps).toHaveLength(2);
    expect(result.steps[1].san).toBe('e4');
    expect(result.fen).toBe(source.fen);
});

test('active and already materialized board messages do not replay', () => {
    const msg = { ...fixtures[0].message, status: -1 };
    expect(materializeGameHistory(msg, ffish, ffish.Notation.SAN)).toBe(msg);
    const plain = { ...msg, status: 3, history: undefined };
    expect(materializeGameHistory(plain, ffish, ffish.Notation.SAN)).toBe(plain);
});

test('Jieqi reveals movers and captured covered identities independently', () => {
    const msg = fixtures.find(fixture => fixture.name === 'jieqi')!.message;
    const result = materializeGameHistory(msg, ffish, ffish.Notation.XIANGQI_WXF);
    expect(result.steps[1].move).toBe('a1a2c');
    expect(result.steps[1].san).toContain('=c');
    expect(result.steps[1].san).not.toContain('=n');
    expect(result.jieqiCaptureStack).toEqual(['n']);
    expect(result.jieqiCaptures).toEqual(['n']);
});

test('long histories retain every ply through repeated positions', () => {
    const source = fixtures[0].message;
    const msg = {
        ...source,
        history: {
            ...source.history!,
            moves: Array.from({ length: 200 }, () => ['g1f3', 'g8f6', 'f3g1', 'f6g8']).flat(),
            analysis: undefined,
            clocksWhite: undefined,
            clocksBlack: undefined,
        },
    };
    const result = materializeGameHistory(msg, ffish, ffish.Notation.SAN);
    expect(result.steps).toHaveLength(801);
    expect(result.steps[800].fen.split(' ')[0]).toBe(result.steps[0].fen.split(' ')[0]);
});
