import { expect, test } from '@jest/globals';

import {
    ensureCataloguedVariantsLoaded,
    unregisterCataloguedVariant,
    VARIANTS,
} from '../client/variants';

const name = 'on-demand-catalogue-test';

test('unknown variants can be loaded once when a shared widget needs them', async () => {
    const originalFetch = globalThis.fetch;
    let requests = 0;
    globalThis.fetch = (async () => {
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
        await Promise.all([ensureCataloguedVariantsLoaded(), ensureCataloguedVariantsLoaded()]);
        expect(requests).toBe(1);
        expect(VARIANTS[name]).toBeDefined();
    } finally {
        globalThis.fetch = originalFetch;
        unregisterCataloguedVariant(name);
    }
});
