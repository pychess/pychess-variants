import type { Ceval } from '../messages';

export type SearchBackendStatus = 'loading' | 'ready' | 'searching' | 'stopping' | 'disconnected' | 'error';

export interface SearchBackendCapabilities {
    available: boolean;
    supportsVariant: boolean;
}

export interface AnalysisSearch {
    variant: string;
    engineVariant: string;
    chess960: boolean;
    initialFen: string;
    currentFen: string;
    moves: string[];
    threads: number;
    hash: number;
    multiPv: number;
    maxDepth: number;
    nnue?: { file: string; enabled: boolean };
    rules?: { ini: string; sha256: string };
}

export interface AnalysisSearchBackend {
    readonly id: 'browser' | 'external';
    readonly capabilities: SearchBackendCapabilities;
    readonly status: SearchBackendStatus;
    start(search: AnalysisSearch): void;
    stop(): void;
    destroy(): void;
}

export interface SearchBackendEvents {
    canSearch(): boolean;
    onEvaluation(ceval: Ceval): void;
    onStatusChanged?(status: SearchBackendStatus, errorCode?: string): void;
}
