import { expect, test } from '@jest/globals';

import {
    ensureCataloguedVariantsLoaded,
    ensureCataloguedVariantKeysLoaded,
    splitVariantKey,
    unregisterCataloguedVariant,
    VARIANTS,
} from '../client/variants';

const name = 'on-demand-catalogue-test';

test('unknown variants can be loaded once when a shared widget needs them', async () => {
    const originalFetch = globalThis.fetch;
    let requests = 0;
    globalThis.fetch = (async (url: RequestInfo | URL) => {
        expect(String(url)).toBe(`/api/catalogued-variants?name=${name}`);
        requests += 1;
        return {
            ok: true,
            json: async () => ({
                variants: [{
                    name,
                    displayName: 'On-demand variant',
                    ini: `[${name}:chess]`,
                    baseVariant: 'chess',
                    startFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
                    width: 8,
                    height: 8,
                    pieces: ['p', 'n', 'b', 'r', 'q', 'k'],
                }],
            }),
        } as Response;
    }) as typeof fetch;
    try {
        await Promise.all([
            ensureCataloguedVariantsLoaded([name]),
            ensureCataloguedVariantsLoaded([name]),
        ]);
        expect(requests).toBe(1);
        expect(VARIANTS[name]).toBeDefined();
    } finally {
        globalThis.fetch = originalFetch;
        unregisterCataloguedVariant(name);
    }
});

test('literal catalogue names ending in 960 are resolved before shuffle suffixes', async () => {
    const originalFetch = globalThis.fetch;
    const literal = 'literal-catalogue960';
    const requests: string[] = [];
    globalThis.fetch = (async (url: RequestInfo | URL) => {
        requests.push(String(url));
        return {
            ok: true,
            json: async () => ({ variants: [{
                name: literal, baseVariant: 'chess', ini: `[${literal}:chess]`,
                startFen: '4k3/8/8/8/8/8/8/4K3 w - - 0 1', width: 8, height: 8, pieces: ['k'],
            }] }),
        } as Response;
    }) as typeof fetch;
    try {
        await ensureCataloguedVariantKeysLoaded([literal]);
        expect(requests).toEqual([`/api/catalogued-variants?name=${literal}`]);
        expect(splitVariantKey(literal).base).toBe(literal);
    } finally {
        globalThis.fetch = originalFetch;
        unregisterCataloguedVariant(literal);
    }
});
