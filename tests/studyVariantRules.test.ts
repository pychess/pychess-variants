import { expect, test, beforeAll, afterEach } from '@jest/globals';
import { TextEncoder } from 'node:util';
import { webcrypto } from 'node:crypto';
import { buildStudyEngineRules } from '../client/study/variantRules';
import { activateStudyEngineRules, moddedVariant, variantConfigIni } from '../client/variants';
import { externalRulesIni } from '../client/analysis/externalRules';

beforeAll(() => {
    Object.assign(globalThis, { TextEncoder });
    Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true });
});
afterEach(() => activateStudyEngineRules(undefined));

test('historical versions have stable distinct runtime keys across all analysis backends', async () => {
    const old = await buildStudyEngineRules('saved', '', [{ ini: '[saved:chess]\ndoubleStep = false\n' }]);
    const current = await buildStudyEngineRules('saved', '', [{ ini: '[saved:chess]\ndoubleStep = true\n' }]);
    const again = await buildStudyEngineRules('saved', '', [{ ini: '[saved:chess]\ndoubleStep = false\n' }]);
    expect(old.engineVariant).not.toBe(current.engineVariant);
    expect(old).toEqual(again);
    activateStudyEngineRules(old);
    expect(moddedVariant('saved', false, new Map(), '-')).toBe(old.engineVariant);
    expect(variantConfigIni('', 'saved')).toBe(old.ini);
    expect(externalRulesIni(old.ini, old.engineVariant)).toBe(old.ini);
    expect(moddedVariant('saved', false, new Map(), '-')).not.toBe(current.engineVariant);
    activateStudyEngineRules(current);
    expect(moddedVariant('saved', false, new Map(), '-')).toBe(current.engineVariant);
});

test('ancestor changes invalidate the child key and inherited references use the pinned ancestor', async () => {
    const child = { ini: '[child:parent]\npieceDrops = true\n' };
    const first = await buildStudyEngineRules('child', '', [{ ini: '[parent:chess]\ndoubleStep = false\n' }, child]);
    const second = await buildStudyEngineRules('child', '', [{ ini: '[parent:chess]\ndoubleStep = true\n' }, child]);
    expect(first.engineVariant).not.toBe(second.engineVariant);
    const parent = first.ini.match(/^\[([^:]+):chess\]/)![1];
    expect(first.ini).toContain(`[${first.engineVariant}:${parent}]`);
    expect(first.ini).not.toContain(':parent]');
    expect(externalRulesIni(first.ini, first.engineVariant)).toBe(first.ini);
});

test('snapshot definitions override the live section while unrelated rules are excluded', async () => {
    const result = await buildStudyEngineRules('saved', '[saved:chess]\ndoubleStep = true\n[other:fogofwar]\n', [
        { ini: '[saved:chess]\ndoubleStep = false\n' },
    ]);
    expect(result.ini).toContain('doubleStep = false');
    expect(result.ini).not.toContain('doubleStep = true');
    expect(result.ini).not.toContain('fogofwar');
    await expect(buildStudyEngineRules('a', '[a:b]\n[b:a]\n', [])).rejects.toThrow('rules_mismatch');
});
