import type { AnalysisSearch, AnalysisSearchBackend, SearchBackendEvents, SearchBackendStatus } from './searchBackend';

export interface ExternalCapabilities {
    name: string;
    variants: string[];
    chess960: boolean;
    customRules: boolean;
    maxThreads: number;
    maxHash: number;
    maxMultiPv: number;
    variantRestrictions?: Record<string, { chess960: boolean; customRules: boolean }>;
}

export interface ExternalSearchSession {
    sessionId?: string;
    lastAbort?: { address: string; until: number };
}
const tabSession: ExternalSearchSession = {};

export class ExternalEngineError extends Error {
    constructor(readonly code: string) {
        super(code);
    }
}

type Fetch = typeof fetch;
type LoopbackRequest = RequestInit & { targetAddressSpace: 'loopback' };
const MAX_LINE = 128 * 1024;
const MAX_SEARCH_MILLIS = 15 * 60 * 1000;
const SEARCH_TIMEOUT_GRACE_MILLIS = 30000;
const record = (value: unknown): value is Record<string, unknown> =>
    value !== null && typeof value === 'object' && !Array.isArray(value);
const integer = (value: unknown, minimum: number, maximum: number): value is number =>
    typeof value === 'number' && Number.isSafeInteger(value) && value >= minimum && value <= maximum;

export function externalAddress(value: string): string {
    let url: URL;
    try {
        url = new URL(value);
    } catch {
        throw new ExternalEngineError('invalid_address');
    }
    if (
        url.protocol !== 'http:' ||
        url.hostname !== '127.0.0.1' ||
        Number(url.port || 80) < 1 ||
        url.username ||
        url.password ||
        url.search ||
        url.hash ||
        url.pathname !== '/'
    )
        throw new ExternalEngineError('invalid_address');
    return url.origin;
}

export function parseCapabilities(value: unknown): ExternalCapabilities {
    if (!record(value) || value.protocolVersion !== 1 || value.prototype || value.scorePov !== 'sideToMove')
        throw new ExternalEngineError('invalid_protocol');
    const engine = value.engine;
    if (
        !record(engine) ||
        typeof engine.name !== 'string' ||
        engine.name.length > 200 ||
        !Array.isArray(engine.variants) ||
        engine.variants.length > 512 ||
        !engine.variants.every(v => typeof v === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(v)) ||
        typeof engine.chess960 !== 'boolean' ||
        typeof engine.customRules !== 'boolean' ||
        !integer(engine.maxThreads, 1, 1024) ||
        !integer(engine.maxHash, 0, 1048576) ||
        !integer(engine.maxMultiPv, 1, 20)
    )
        throw new ExternalEngineError('invalid_protocol');
    if (engine.adapters !== undefined) throw new ExternalEngineError('invalid_protocol');
    const variants = engine.variants;
    if (engine.variantRestrictions !== undefined) {
        if (!record(engine.variantRestrictions) || Object.entries(engine.variantRestrictions).some(([variant, flags]) =>
            !variants.includes(variant) || !record(flags) ||
            Object.keys(flags).length !== 2 || typeof flags.chess960 !== 'boolean' ||
            typeof flags.customRules !== 'boolean' ||
            (flags.chess960 && !engine.chess960) || (flags.customRules && !engine.customRules)))
            throw new ExternalEngineError('invalid_protocol');
    }
    return engine as unknown as ExternalCapabilities;
}

export function externalEngineSupports(
    engine: ExternalCapabilities | undefined,
    search: Pick<AnalysisSearch, 'engineVariant' | 'chess960' | 'rules'>,
): boolean {
    if (!engine) return false;
    const restrictions = engine.variantRestrictions?.[search.engineVariant];
    return (!search.chess960 || (engine.chess960 && restrictions?.chess960 !== false)) &&
        (search.rules
            ? engine.customRules && restrictions?.customRules !== false
            : engine.variants.includes(search.engineVariant));
}

async function checkResponse(response: Response): Promise<void> {
    if (response.ok) return;
    let code = response.status === 401 ? 'pairing_required' : 'connection_failed';
    try {
        const body: unknown = await response.json();
        if (
            record(body) &&
            record(body.error) &&
            typeof body.error.code === 'string' &&
            /^[a-z_]{1,64}$/.test(body.error.code)
        )
            code = body.error.code;
    } catch {
        /* Keep the bounded local error code. */
    }
    throw new ExternalEngineError(code);
}

/** Every response is owned by an epoch and search ID, including asynchronous pairing. */
export class ExternalSearchBackend implements AnalysisSearchBackend {
    readonly id = 'external';
    private epoch = 0;
    private abort?: AbortController;
    private address = '';
    private token = '';
    private destroyed = false;
    private recentlyAborted = false;
    private readonly sessionId: string;
    private engine?: ExternalCapabilities;
    status: SearchBackendStatus = 'disconnected';
    errorCode?: string;

    constructor(
        private readonly events: SearchBackendEvents,
        private readonly fetcher: Fetch = fetch,
        private readonly session: ExternalSearchSession = tabSession,
    ) {
        this.sessionId = session.sessionId ??= crypto.randomUUID();
    }

    get engineCapabilities(): ExternalCapabilities | undefined {
        return this.engine;
    }

    get capabilities() {
        return { available: !!this.engine && !this.destroyed, supportsVariant: !!this.engine };
    }

    supports(search: Pick<AnalysisSearch, 'engineVariant' | 'chess960' | 'rules'>): boolean {
        return externalEngineSupports(this.engine, search);
    }

    private updateStatus(status: SearchBackendStatus, code?: string): void {
        this.status = status;
        this.errorCode = code;
        this.events.onStatusChanged?.(status, code);
    }

    private request(path: string, init: RequestInit): Promise<Response> {
        const options: LoopbackRequest = {
            ...init,
            credentials: 'omit',
            cache: 'no-store',
            targetAddressSpace: 'loopback',
            headers: { Authorization: 'Bearer ' + this.token, ...init.headers },
        };
        return this.fetcher.call(globalThis, this.address + path, options);
    }

    async connect(address: string, token: string): Promise<void> {
        if (this.destroyed) return;
        this.stop();
        this.engine = undefined;
        this.address = externalAddress(address);
        if (!/^[\x21-\x7e]{32,256}$/.test(token)) throw new ExternalEngineError('invalid_pairing');
        this.token = token;
        const epoch = this.epoch;
        const abort = new AbortController();
        this.abort = abort;
        this.updateStatus('loading');
        const timer = setTimeout(() => abort.abort(), 10000);
        try {
            const response = await this.request('/v1/capabilities', { signal: abort.signal });
            await checkResponse(response);
            const engine = parseCapabilities(await response.json());
            if (this.epoch !== epoch) return;
            if (abort.signal.aborted) throw new ExternalEngineError('connection_failed');
            this.engine = engine;
            this.updateStatus('ready');
        } catch (error) {
            if (this.epoch !== epoch) return;
            this.updateStatus('error', error instanceof ExternalEngineError ? error.code : 'connection_failed');
            throw new ExternalEngineError(this.errorCode!);
        } finally {
            clearTimeout(timer);
            if (this.abort === abort) this.abort = undefined;
        }
    }

    start(search: AnalysisSearch): void {
        const retryCleanup =
            this.recentlyAborted ||
            !!this.abort ||
            (this.session.lastAbort?.address === this.address && this.session.lastAbort.until > Date.now());
        this.stop();
        this.recentlyAborted = false;
        if (!this.engine || this.destroyed || !this.events.canSearch()) return;
        if (!this.supports(search)) {
            this.updateStatus('error', 'unsupported_variant');
            return;
        }
        const epoch = this.epoch;
        const abort = new AbortController();
        this.abort = abort;
        this.updateStatus('searching');
        void this.run(search, epoch, abort, retryCleanup);
    }

    private async run(
        search: AnalysisSearch,
        epoch: number,
        abort: AbortController,
        retryCleanup: boolean,
    ): Promise<void> {
        const engine = this.engine!;
        const searchId = crypto.randomUUID();
        const body = {
            protocolVersion: 1,
            sessionId: this.sessionId,
            searchId,
            variant: search.variant,
            engineVariant: search.engineVariant,
            chess960: search.chess960,
            initialFen: search.initialFen,
            currentFen: search.currentFen,
            moves: search.moves,
            threads: Math.min(search.threads, engine.maxThreads),
            hash: Math.min(search.hash, engine.maxHash || search.hash),
            multiPv: Math.min(Math.max(search.multiPv, 1), engine.maxMultiPv),
            search: search.maxDepth >= 99 ? { depth: 128 } : { depth: search.maxDepth, movetime: 90000 },
            ...(search.rules ? { rules: search.rules } : {}),
        };
        const current = () => this.epoch === epoch && !abort.signal.aborted && !this.destroyed;
        let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
        let timer = setTimeout(() => abort.abort(), 30000);
        try {
            const retryUntil = Date.now() + (retryCleanup ? 2000 : 0);
            let response: Response;
            while (true) {
                response = await this.request('/v1/analyse', {
                    method: 'POST',
                    signal: abort.signal,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                if (response.status !== 409 || Date.now() >= retryUntil) break;
                await response.body?.cancel();
                await new Promise(resolve => setTimeout(resolve, 100));
                if (!current()) return;
            }
            await checkResponse(response);
            clearTimeout(timer);
            // A deep iteration can legitimately emit no PV for over 30 seconds.
            // Bound the entire search instead of treating silence as a failure.
            timer = setTimeout(
                () => abort.abort(),
                (body.search.movetime ?? MAX_SEARCH_MILLIS) + SEARCH_TIMEOUT_GRACE_MILLIS,
            );
            if (!response.body || !response.headers.get('Content-Type')?.startsWith('application/x-ndjson'))
                throw new ExternalEngineError('invalid_protocol');
            reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let completed = false;
            while (current()) {
                const chunk = await reader.read();
                if (chunk.done) break;
                buffer += decoder.decode(chunk.value, { stream: true });
                let newline: number;
                while ((newline = buffer.indexOf('\n')) >= 0) {
                    if (newline > MAX_LINE) throw new ExternalEngineError('invalid_protocol');
                    const line = buffer.slice(0, newline);
                    buffer = buffer.slice(newline + 1);
                    if (!line.trim()) continue;
                    const event: unknown = JSON.parse(line);
                    if (!record(event) || event.protocolVersion !== 1 || event.prototype)
                        throw new ExternalEngineError('invalid_protocol');
                    if (!current() || event.searchId !== searchId) continue;
                    if (completed) throw new ExternalEngineError('invalid_protocol');
                    if (event.type === 'evaluation') this.deliver(event, current);
                    else if (event.type === 'error') {
                        const code =
                            record(event.error) &&
                            typeof event.error.code === 'string' &&
                            /^[a-z_]{1,64}$/.test(event.error.code)
                                ? event.error.code
                                : 'engine_error';
                        throw new ExternalEngineError(code);
                    } else if (event.type === 'completed') completed = true;
                    else if (event.type !== 'started') throw new ExternalEngineError('invalid_protocol');
                }
                if (buffer.length > MAX_LINE) throw new ExternalEngineError('invalid_protocol');
            }
            if (current()) {
                if (!completed || buffer.trim()) throw new ExternalEngineError('stream_ended');
                this.updateStatus('ready');
            }
        } catch (error) {
            if (this.epoch === epoch && !this.destroyed)
                this.updateStatus('error', error instanceof ExternalEngineError ? error.code : 'connection_failed');
        } finally {
            clearTimeout(timer);
            await reader?.cancel().catch(() => {});
            if (this.abort === abort) this.abort = undefined;
        }
    }

    private deliver(event: Record<string, unknown>, current: () => boolean): void {
        if (
            !Array.isArray(event.pvs) ||
            event.pvs.length > 20 ||
            !integer(event.nodes, 0, Number.MAX_SAFE_INTEGER) ||
            !integer(event.millis, 1, Number.MAX_SAFE_INTEGER)
        )
            throw new ExternalEngineError('invalid_protocol');
        for (const pv of event.pvs) {
            if (
                !record(pv) ||
                !integer(pv.multiPv, 1, 20) ||
                !integer(pv.depth, 0, 128) ||
                !Array.isArray(pv.moves) ||
                pv.moves.length < 1 ||
                pv.moves.length > 64 ||
                !pv.moves.every(m => typeof m === 'string' && /^[\x21-\x7e]{1,64}$/.test(m)) ||
                integer(pv.cp, -2147483647, 2147483647) === integer(pv.mate, -2147483647, 2147483647) ||
                (pv.cp !== undefined && !integer(pv.cp, -2147483647, 2147483647)) ||
                (pv.mate !== undefined && !integer(pv.mate, -2147483647, 2147483647))
            )
                throw new ExternalEngineError('invalid_protocol');
            if (!current() || !this.events.canSearch()) return;
            if (pv.mate === 0 || (pv.multiPv === 1 && (pv.upperbound || pv.lowerbound))) continue;
            this.events.onEvaluation({
                d: pv.depth,
                multipv: pv.multiPv,
                p: pv.moves.join(' '),
                s: pv.cp !== undefined ? { cp: pv.cp as number } : { mate: pv.mate as number },
                k: event.nodes / event.millis,
            });
        }
    }

    stop(): void {
        this.epoch++;
        if (this.abort) {
            this.recentlyAborted = this.status === 'searching';
            if (this.recentlyAborted) this.session.lastAbort = { address: this.address, until: Date.now() + 2000 };
        }
        this.abort?.abort();
        this.abort = undefined;
        if (this.engine && !this.destroyed) this.updateStatus('ready');
    }

    destroy(): void {
        this.disconnect();
        this.destroyed = true;
    }

    disconnect(): void {
        this.stop();
        this.engine = undefined;
        this.token = '';
        this.updateStatus('disconnected');
    }
}
