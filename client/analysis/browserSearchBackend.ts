import type { Ceval } from '../messages';
import type {
    AnalysisSearch,
    AnalysisSearchBackend,
    SearchBackendCapabilities,
    SearchBackendEvents,
    SearchBackendStatus,
} from './searchBackend';

interface BrowserSearchHost extends SearchBackendEvents {
    postMessage(command: string): void;
    capabilities(): SearchBackendCapabilities;
}

/** Browser UCI commands retain their stop/readiness barrier and NNUE configuration. */
export class BrowserSearchBackend implements AnalysisSearchBackend {
    readonly id = 'browser';
    private awaitingReady = false;
    private pending?: AnalysisSearch;
    private searching = false;
    private destroyed = false;
    private failure?: string;

    constructor(private readonly host: BrowserSearchHost) {}

    get capabilities(): SearchBackendCapabilities {
        return this.host.capabilities();
    }

    get status(): SearchBackendStatus {
        if (this.destroyed) return 'disconnected';
        if (this.failure) return 'error';
        if (this.awaitingReady) return 'stopping';
        if (this.searching) return 'searching';
        return this.capabilities.available ? 'ready' : 'loading';
    }

    get idle(): boolean {
        return !this.awaitingReady && this.pending === undefined;
    }

    get canDeliverEvaluation(): boolean {
        return !this.destroyed && !this.failure && !this.awaitingReady && this.capabilities.available && this.host.canSearch();
    }

    deliver(ceval: Ceval): void {
        if (this.canDeliverEvaluation) this.host.onEvaluation(ceval);
    }

    onReady(): void {
        if (this.failure || this.destroyed) return;
        this.awaitingReady = false;
        const pending = this.pending;
        this.pending = undefined;
        if (pending && this.host.canSearch()) this.start(pending);
    }

    onCompleted(): void {
        this.searching = false;
    }

    start(search: AnalysisSearch): void {
        if (this.destroyed || this.failure || !this.capabilities.supportsVariant || !this.host.canSearch()) return;
        if (this.awaitingReady) {
            this.pending = search;
            return;
        }
        this.pending = undefined;
        const send = (command: string) => this.host.postMessage(command);
        send('setoption name UCI_Variant value ' + search.engineVariant);
        send('setoption name UCI_Chess960 value ' + search.chess960);
        if (search.nnue?.enabled && search.nnue.file) {
            send('setoption name Use NNUE value true');
            send('setoption name EvalFile value ' + search.nnue.file);
        } else {
            send('setoption name Use NNUE value false');
        }
        send('setoption name Hash value ' + search.hash);
        send('setoption name Threads value ' + search.threads);
        send('setoption name MultiPV value ' + search.multiPv);
        send(
            search.moves.length
                ? 'position fen ' + search.initialFen + ' moves ' + search.moves.join(' ')
                : 'position fen ' + search.currentFen,
        );
        send(search.maxDepth >= 99 ? 'go depth 99' : 'go movetime 90000 depth ' + search.maxDepth);
        this.searching = true;
    }

    stop(): void {
        if (this.destroyed || this.failure) return;
        this.awaitingReady = true;
        this.pending = undefined;
        this.searching = false;
        this.host.postMessage('stop');
        this.host.postMessage('isready');
    }

    /** A terminated WASM engine must never accept another search in this page. */
    onFailure(message: string): void {
        if (this.destroyed || this.failure) return;
        this.failure = message;
        this.awaitingReady = false;
        this.pending = undefined;
        this.searching = false;
        this.host.onStatusChanged?.('error', 'engine_terminated');
    }

    destroy(): void {
        this.stop();
        this.destroyed = true;
        this.pending = undefined;
    }
}
