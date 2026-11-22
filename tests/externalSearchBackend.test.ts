import { expect, jest, test, beforeAll } from '@jest/globals';
import { TextEncoder, TextDecoder } from 'node:util';
import { ReadableStream } from 'node:stream/web';
import { createHash, webcrypto } from 'node:crypto';
import {
    ExternalSearchBackend,
    externalAddress,
    type ExternalSearchSession,
} from '../client/analysis/externalSearchBackend';
import { externalRulesIni, hashExternalRules } from '../client/analysis/externalRules';
import type { AnalysisSearch, SearchBackendEvents } from '../client/analysis/searchBackend';

beforeAll(() => {
    Object.assign(globalThis, { TextEncoder, TextDecoder });
    Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true });
});

function testBackend(events: SearchBackendEvents, fetcher: typeof fetch, session: ExternalSearchSession = {}) {
    return new ExternalSearchBackend(events, fetcher, session);
}

const TOKEN = 'test-pairing-token-' + 'x'.repeat(32);
const ADDRESS = 'http://127.0.0.1:9670';
const capabilities = {
    protocolVersion: 1,
    scorePov: 'sideToMove',
    engine: {
        name: 'Test engine',
        variants: ['shogi'],
        chess960: true,
        customRules: true,
        maxThreads: 2,
        maxHash: 64,
        maxMultiPv: 2,
    },
};
const search: AnalysisSearch = {
    variant: 'shogi',
    engineVariant: 'shogi',
    chess960: false,
    initialFen: 'root',
    currentFen: 'selected',
    moves: ['e7e8+'],
    threads: 8,
    hash: 128,
    multiPv: 5,
    maxDepth: 18,
};

function jsonResponse(data: unknown, status = 200): Response {
    return { ok: status === 200, status, json: async () => data } as Response;
}

function streamResponse() {
    let controller: ReadableStreamDefaultController<Uint8Array>;
    const stream = new ReadableStream<Uint8Array>({
        start: c => {
            controller = c as unknown as typeof controller;
        },
    });
    return {
        response: {
            ok: true,
            status: 200,
            headers: { get: () => 'application/x-ndjson' },
            body: stream,
        } as unknown as Response,
        write: (text: string) => controller.enqueue(new TextEncoder().encode(text)),
        close: () => controller.close(),
        fail: (error: Error) => controller.error(error),
        locked: () => stream.locked,
    };
}

async function eventually(predicate: () => boolean) {
    for (let i = 0; i < 100; i++) {
        if (predicate()) return;
        await new Promise(resolve => setTimeout(resolve, 5));
    }
    throw new Error('Expected asynchronous backend state');
}

test.each([18, 99])('quiet native searches survive 30 seconds and remain bounded (depth %s)', async maxDepth => {
    jest.useFakeTimers();
    const stream = streamResponse();
    let signal: AbortSignal | undefined;
    let searchId: string | undefined;
    const backend = testBackend({ canSearch: () => true, onEvaluation: jest.fn() }, async (_url, init) => {
        if (!init?.body) return jsonResponse(capabilities);
        signal = init.signal!;
        searchId = JSON.parse(init.body as string).searchId;
        signal.addEventListener('abort', () => stream.fail(new DOMException('Aborted', 'AbortError')), { once: true });
        return stream.response;
    });
    try {
        await backend.connect(ADDRESS, TOKEN);
        backend.start({ ...search, maxDepth });
        await jest.advanceTimersByTimeAsync(0);
        stream.write(JSON.stringify({ protocolVersion: 1, type: 'started', searchId }) + '\n');
        await jest.advanceTimersByTimeAsync(31000);
        expect(signal?.aborted).toBe(false);
        expect(backend.status).toBe('searching');
        const deadline = (maxDepth >= 99 ? 15 * 60 * 1000 : 90000) + 30000;
        await jest.advanceTimersByTimeAsync(deadline - 31000 - 1);
        expect(signal?.aborted).toBe(false);
        await jest.advanceTimersByTimeAsync(1);
        expect(signal?.aborted).toBe(true);
        expect(backend.status).toBe('error');
        expect(jest.getTimerCount()).toBe(0);
    } finally {
        backend.destroy();
        jest.useRealTimers();
    }
});

test('a quiet deep iteration can finish successfully and clears its deadline', async () => {
    jest.useFakeTimers();
    const stream = streamResponse();
    let searchId: string | undefined;
    const onEvaluation = jest.fn();
    const backend = testBackend({ canSearch: () => true, onEvaluation }, async (_url, init) => {
        if (!init?.body) return jsonResponse(capabilities);
        searchId = JSON.parse(init.body as string).searchId;
        return stream.response;
    });
    try {
        await backend.connect(ADDRESS, TOKEN);
        backend.start({ ...search, maxDepth: 99 });
        await jest.advanceTimersByTimeAsync(60000);
        stream.write(
            JSON.stringify({
                protocolVersion: 1,
                type: 'evaluation',
                searchId,
                nodes: 100000,
                millis: 60000,
                pvs: [{ depth: 30, multiPv: 1, cp: 32, moves: ['e7e8+'] }],
            }) + '\n',
        );
        stream.write(JSON.stringify({ protocolVersion: 1, type: 'completed', searchId }) + '\n');
        stream.close();
        await jest.advanceTimersByTimeAsync(0);
        expect(onEvaluation).toHaveBeenCalledTimes(1);
        expect(backend.status).toBe('ready');
        expect(jest.getTimerCount()).toBe(0);
    } finally {
        backend.destroy();
        jest.useRealTimers();
    }
});

test('connection addresses stay on IPv4 loopback and reject credentials or paths', () => {
    expect(externalAddress(ADDRESS + '/')).toBe(ADDRESS);
    for (const value of [
        'https://127.0.0.1:9670',
        'http://remote.example:9670',
        'http://localhost:9670',
        ADDRESS + '/path',
        ADDRESS + '?token=x',
        'http://user:pass@127.0.0.1:9670',
        'http://127.0.0.1:0',
    ])
        expect(() => externalAddress(value)).toThrow();
});

test('minimal rules preserve snapshot inheritance, skip unrelated rules and hash exact UTF-8', async () => {
    const ini =
        '# Árvíztűrő\n[unrelated:chess]\n[base:chess]\ndoubleStep = false\n[studysnap_saved:base]\n[hidden:fogofwar]\n';
    const exact = externalRulesIni(ini, 'studysnap_saved')!;
    expect(exact).toBe('[base:chess]\ndoubleStep = false\n[studysnap_saved:base]\n');
    expect(externalRulesIni(ini, 'shogi')).toBeUndefined();
    const hashed = await hashExternalRules(exact + '# Árvíztűrő\n');
    expect(hashed.sha256).toBe(createHash('sha256').update(hashed.ini).digest('hex'));
    expect(() => externalRulesIni('[a:b]\n[b:a]\n', 'a')).toThrow();
    expect(() => externalRulesIni('[a:chess]\n[a:chess]\n', 'a')).toThrow();
});

test('pairing requires production capabilities and stale pairing cannot replace a new connection', async () => {
    let resolveOld: (response: Response) => void = () => {};
    const first = new Promise<Response>(resolve => {
        resolveOld = resolve;
    });
    let calls = 0;
    const fetcher = jest.fn<typeof fetch>(async () => (++calls === 1 ? first : jsonResponse(capabilities)));
    const backend = testBackend({ canSearch: () => true, onEvaluation: jest.fn() }, fetcher);
    const old = backend.connect(ADDRESS, TOKEN);
    await backend.connect(ADDRESS, TOKEN);
    resolveOld(jsonResponse({ ...capabilities, prototype: true }));
    await old;
    expect(backend.status).toBe('ready');
    expect(backend.engineCapabilities?.name).toBe('Test engine');
    expect(
        backend.supports({ engineVariant: 'new-snapshot', chess960: false, rules: { ini: 'rules', sha256: 'hash' } }),
    ).toBe(true);
    expect(backend.supports({ engineVariant: 'chess', chess960: false })).toBe(false);
    backend.destroy();
    const fake = testBackend({ canSearch: () => true, onEvaluation: jest.fn() }, async () =>
        jsonResponse({ ...capabilities, prototype: true }),
    );
    await expect(fake.connect(ADDRESS, TOKEN)).rejects.toThrow('invalid_protocol');
    fake.destroy();
});

test('fragmented events preserve scores and extended moves while dropping stale search IDs', async () => {
    const stream = streamResponse();
    let body: Record<string, unknown> = {};
    const onEvaluation = jest.fn();
    const fetcher = jest.fn<typeof fetch>(async (_url, init) => {
        if (!init?.body) return jsonResponse(capabilities);
        body = JSON.parse(init.body as string);
        return stream.response;
    });
    const backend = testBackend({ canSearch: () => true, onEvaluation }, fetcher);
    await backend.connect(ADDRESS, TOKEN);
    backend.start(search);
    await eventually(() => !!body.searchId);
    const event = {
        protocolVersion: 1,
        type: 'evaluation',
        searchId: body.searchId,
        nodes: 1000,
        millis: 50,
        pvs: [{ depth: 5, multiPv: 1, cp: -32, moves: ['e7e8+', 'P@a10'] }],
    };
    stream.write(JSON.stringify({ ...event, searchId: 'old-search' }) + '\n');
    const line = JSON.stringify(event) + '\n';
    stream.write(line.slice(0, 20));
    stream.write(line.slice(20));
    stream.write(JSON.stringify({ protocolVersion: 1, searchId: body.searchId, type: 'completed' }) + '\n');
    stream.close();
    await eventually(() => backend.status === 'ready');
    expect(onEvaluation).toHaveBeenCalledTimes(1);
    expect(onEvaluation).toHaveBeenCalledWith({ d: 5, multipv: 1, p: 'e7e8+ P@a10', s: { cp: -32 }, k: 20 });
    expect(body).toMatchObject({
        initialFen: 'root',
        currentFen: 'selected',
        moves: ['e7e8+'],
        threads: 2,
        hash: 64,
        multiPv: 2,
    });
    expect(fetcher.mock.calls[1][0]).toBe(ADDRESS + '/v1/analyse');
    expect(fetcher.mock.contexts[1]).toBe(globalThis);
    expect(fetcher.mock.calls[1][1]).toMatchObject({
        credentials: 'omit',
        targetAddressSpace: 'loopback',
        headers: { Authorization: 'Bearer ' + TOKEN },
    });
    backend.destroy();
});

test('an aborted response cannot deliver a late legal PV to its replacement', async () => {
    const streams = [streamResponse(), streamResponse()];
    const bodies: Record<string, unknown>[] = [];
    const onEvaluation = jest.fn();
    const backend = testBackend({ canSearch: () => true, onEvaluation }, async (_url, init) => {
        if (!init?.body) return jsonResponse(capabilities);
        const index = bodies.length;
        bodies.push(JSON.parse(init.body as string));
        return streams[index].response;
    });
    await backend.connect(ADDRESS, TOKEN);
    backend.start(search);
    await eventually(() => bodies.length === 1);
    await eventually(() => streams[0].locked());
    backend.stop();
    backend.start({ ...search, currentFen: 'replacement' });
    await eventually(() => bodies.length === 2);
    const event = (index: number) => ({
        protocolVersion: 1,
        type: 'evaluation',
        searchId: bodies[index].searchId,
        nodes: 10,
        millis: 5,
        pvs: [{ depth: 2, multiPv: 1, cp: index + 10, moves: ['e7e8+'] }],
    });
    streams[0].write(JSON.stringify(event(0)) + '\n');
    streams[1].write(JSON.stringify(event(1)) + '\n');
    await eventually(() => onEvaluation.mock.calls.length === 1);
    expect(onEvaluation.mock.calls[0][0]).toMatchObject({ s: { cp: 11 } });
    backend.destroy();
    streams[1].close();
});

test('initial busy ownership is surfaced without retries and invalid mixed scores are rejected', async () => {
    const onEvaluation = jest.fn();
    const busyFetch = jest.fn<typeof fetch>(async (_url, init) =>
        init?.body ? jsonResponse({ error: { code: 'engine_busy' } }, 409) : jsonResponse(capabilities),
    );
    const busy = testBackend({ canSearch: () => true, onEvaluation }, busyFetch);
    await busy.connect(ADDRESS, TOKEN);
    busy.start(search);
    await eventually(() => busy.status === 'error');
    expect(busy.errorCode).toBe('engine_busy');
    expect(busyFetch).toHaveBeenCalledTimes(2);
    busy.destroy();

    const stream = streamResponse();
    let identity: unknown;
    const invalid = testBackend({ canSearch: () => true, onEvaluation }, async (_url, init) => {
        if (!init?.body) return jsonResponse(capabilities);
        identity = JSON.parse(init.body as string).searchId;
        return stream.response;
    });
    await invalid.connect(ADDRESS, TOKEN);
    invalid.start(search);
    await eventually(() => !!identity);
    stream.write(
        JSON.stringify({
            protocolVersion: 1,
            type: 'evaluation',
            searchId: identity,
            nodes: 10,
            millis: 5,
            pvs: [{ depth: 2, multiPv: 1, cp: 'invalid', mate: 3, moves: ['e7e8+'] }],
        }) + '\n',
    );
    await eventually(() => invalid.status === 'error');
    expect(invalid.errorCode).toBe('invalid_protocol');
    expect(onEvaluation).not.toHaveBeenCalled();
    invalid.destroy();
});

test('only a replacement retries its own bounded cleanup window', async () => {
    const first = streamResponse();
    const replacement = streamResponse();
    let searches = 0;
    let replacementId: unknown;
    const backend = testBackend({ canSearch: () => true, onEvaluation: jest.fn() }, async (_url, init) => {
        if (!init?.body) return jsonResponse(capabilities);
        searches++;
        if (searches === 1) return first.response;
        if (searches === 2) return jsonResponse({ error: { code: 'engine_busy' } }, 409);
        replacementId = JSON.parse(init.body as string).searchId;
        return replacement.response;
    });
    await backend.connect(ADDRESS, TOKEN);
    backend.start(search);
    await eventually(() => first.locked());
    backend.stop();
    first.close();
    backend.start(search);
    await eventually(() => searches === 3);
    replacement.write(JSON.stringify({ protocolVersion: 1, type: 'completed', searchId: replacementId }) + '\n');
    replacement.close();
    await eventually(() => backend.status === 'ready');
    backend.destroy();
});

test('permission failure is surfaced once and analysis policy blocks search requests', async () => {
    const deniedFetch = jest.fn<typeof fetch>(async () => {
        throw new TypeError('Permission denied');
    });
    const denied = testBackend({ canSearch: () => true, onEvaluation: jest.fn() }, deniedFetch);
    await expect(denied.connect(ADDRESS, TOKEN)).rejects.toThrow('connection_failed');
    expect(deniedFetch).toHaveBeenCalledTimes(1);
    denied.destroy();
    const fetcher = jest.fn<typeof fetch>(async () => jsonResponse(capabilities));
    const blocked = testBackend({ canSearch: () => false, onEvaluation: jest.fn() }, fetcher);
    await blocked.connect(ADDRESS, TOKEN);
    blocked.start(search);
    expect(fetcher).toHaveBeenCalledTimes(1);
    blocked.destroy();
});

test('chapter controller replacement retains tab identity and waits for its own old search cleanup', async () => {
    const session: ExternalSearchSession = {};
    const first = streamResponse();
    const second = streamResponse();
    const requests: Record<string, unknown>[] = [];
    const fetcher = jest.fn<typeof fetch>(async (_url, init) => {
        if (!init?.body) return jsonResponse(capabilities);
        requests.push(JSON.parse(init.body as string));
        if (requests.length === 1) return first.response;
        if (requests.length === 2) return jsonResponse({ error: { code: 'engine_busy' } }, 409);
        return second.response;
    });
    const events = { canSearch: () => true, onEvaluation: jest.fn() };
    const old = testBackend(events, fetcher, session);
    await old.connect(ADDRESS, TOKEN);
    old.start(search);
    await eventually(() => first.locked());
    old.destroy();
    first.close();
    const replacement = testBackend(events, fetcher, session);
    await replacement.connect(ADDRESS, TOKEN);
    replacement.start(search);
    await eventually(() => requests.length === 3);
    expect(requests[2].sessionId).toBe(requests[0].sessionId);
    expect(requests[2].searchId).not.toBe(requests[0].searchId);
    second.write(JSON.stringify({ protocolVersion: 1, type: 'completed', searchId: requests[2].searchId }) + '\n');
    second.close();
    await eventually(() => replacement.status === 'ready');
    replacement.destroy();
});


test('standalone Alice capabilities enable fixed-rule analysis and use their search limits', async () => {
    const alice = { ...capabilities.engine, name: 'Standalone Alice engine', variants: ['alice'],
        chess960: false, customRules: false, maxThreads: 1, maxHash: 32, maxMultiPv: 1 };
    const stream = streamResponse();
    let body: Record<string, unknown> = {};
    const onEvaluation = jest.fn();
    const backend = testBackend({ canSearch: () => true, onEvaluation }, async (_url, init) => {
        if (!init?.body) return jsonResponse({ ...capabilities, engine: alice });
        body = JSON.parse(init.body as string);
        return stream.response;
    });
    await backend.connect(ADDRESS, TOKEN);
    expect(backend.status).toBe('ready');
    expect(backend.engineCapabilities).toEqual(alice);
    expect(backend.supports({ engineVariant: 'alice', chess960: false })).toBe(true);
    expect(backend.supports({ engineVariant: 'alice', chess960: true })).toBe(false);
    expect(backend.supports({ engineVariant: 'alice', chess960: false,
        rules: { ini: '[alice:chess]', sha256: 'x' } })).toBe(false);
    expect(backend.supports({ engineVariant: 'shogi', chess960: false })).toBe(false);
    backend.start({ ...search, variant: 'alice', engineVariant: 'alice', moves: ['e2e4'] });
    await eventually(() => !!body.searchId);
    expect(body).toMatchObject({ variant: 'alice', engineVariant: 'alice',
        threads: 1, hash: 32, multiPv: 1 });
    stream.write(JSON.stringify({
        protocolVersion: 1, type: 'evaluation', searchId: body.searchId,
        nodes: 1000, millis: 50,
        pvs: [{ depth: 5, multiPv: 1, cp: 32, moves: ['e7e5'] }],
    }) + '\n');
    stream.write(JSON.stringify({ protocolVersion: 1, searchId: body.searchId, type: 'completed' }) + '\n');
    stream.close();
    await eventually(() => backend.status === 'ready');
    expect(onEvaluation).toHaveBeenCalledWith({ d: 5, multipv: 1, p: 'e7e5', s: { cp: 32 }, k: 20 });
    backend.destroy();
});

test('variant restrictions narrow support while identity and resource limits belong to one engine', async () => {
    const events = { canSearch: () => true, onEvaluation: jest.fn() };
    const plain = testBackend(events, async () => jsonResponse(capabilities));
    await plain.connect(ADDRESS, TOKEN);
    expect(plain.supports({ engineVariant: 'alice', chess960: false })).toBe(false);
    plain.destroy();
    const engine = { ...capabilities.engine, variants: ['shogi', 'alice'],
        variantRestrictions: { alice: { chess960: false, customRules: false } } };
    const stream = streamResponse();
    let body: Record<string, unknown> = {};
    const backend = testBackend(events, async (_url, init) => {
        if (!init?.body) return jsonResponse({ ...capabilities, engine });
        body = JSON.parse(init.body as string);
        return stream.response;
    });
    await backend.connect(ADDRESS, TOKEN);
    expect(backend.supports({ engineVariant: 'alice', chess960: false })).toBe(true);
    expect(backend.engineCapabilities?.name).toBe('Test engine');
    expect(backend.supports({ engineVariant: 'alice', chess960: true })).toBe(false);
    expect(backend.supports({ engineVariant: 'alice', chess960: false,
        rules: { ini: '[alice:chess]', sha256: 'x' } })).toBe(false);
    expect(backend.supports({ engineVariant: 'shogi', chess960: true })).toBe(true);
    expect(backend.supports({ engineVariant: 'shogi', chess960: false,
        rules: { ini: '[shogi:chess]', sha256: 'x' } })).toBe(true);
    expect(backend.supports({ engineVariant: 'new-snapshot', chess960: false,
        rules: { ini: '[new-snapshot:chess]', sha256: 'x' } })).toBe(true);
    backend.start({ ...search, variant: 'alice', engineVariant: 'alice' });
    await eventually(() => !!body.searchId);
    expect(body).toMatchObject({ variant: 'alice', threads: 2, hash: 64, multiPv: 2 });
    stream.write(JSON.stringify({ protocolVersion: 1, searchId: body.searchId, type: 'completed' }) + '\n');
    stream.close();
    await eventually(() => backend.status === 'ready');
    backend.destroy();
});

test('restrictions apply to arbitrary advertised variants rather than special engine names', async () => {
    const backend = testBackend({ canSearch: () => true, onEvaluation: jest.fn() }, async () =>
        jsonResponse({ ...capabilities, engine: { ...capabilities.engine,
            variantRestrictions: { shogi: { chess960: false, customRules: false } } } }));
    await backend.connect(ADDRESS, TOKEN);
    expect(backend.supports({ engineVariant: 'shogi', chess960: false })).toBe(true);
    expect(backend.supports({ engineVariant: 'shogi', chess960: true })).toBe(false);
    expect(backend.supports({ engineVariant: 'shogi', chess960: false,
        rules: { ini: '[shogi:chess]', sha256: 'x' } })).toBe(false);
    backend.destroy();
});

test('invalid restrictions and nested engine profiles are rejected during pairing', async () => {
    for (const changes of [
        { variantRestrictions: null },
        { variantRestrictions: [] },
        { variantRestrictions: { missing: { chess960: false, customRules: false } } },
        { variantRestrictions: { shogi: { chess960: 'false', customRules: false } } },
        { variantRestrictions: { shogi: { chess960: false } } },
        { variantRestrictions: { shogi: { chess960: false, customRules: false, name: 'Other engine' } } },
        { variantRestrictions: { shogi: { chess960: false, customRules: false, maxThreads: 1 } } },
        { customRules: false, variantRestrictions: { shogi: { chess960: false, customRules: true } } },
        { chess960: false, variantRestrictions: { shogi: { chess960: true, customRules: false } } },
        { adapters: { alice: capabilities.engine } },
    ]) {
        const invalid = testBackend({ canSearch: () => true, onEvaluation: jest.fn() }, async () =>
            jsonResponse({ ...capabilities, engine: { ...capabilities.engine, ...changes } }));
        await expect(invalid.connect(ADDRESS, TOKEN)).rejects.toThrow('invalid_protocol');
        invalid.destroy();
    }
});
