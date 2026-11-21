import { expect, jest, test } from '@jest/globals';
import { BrowserSearchBackend } from '../client/analysis/browserSearchBackend';
import type { AnalysisSearch } from '../client/analysis/searchBackend';

const request: AnalysisSearch = {
    variant: 'shogi',
    engineVariant: 'shogi',
    chess960: false,
    initialFen: 'root',
    currentFen: 'current',
    moves: ['e7e8+'],
    threads: 2,
    hash: 64,
    multiPv: 2,
    maxDepth: 18,
    nnue: { file: 'local.nnue', enabled: true },
};

function fixture() {
    const commands: string[] = [];
    let allowed = true;
    const onEvaluation = jest.fn();
    const backend = new BrowserSearchBackend({
        postMessage: command => commands.push(command),
        capabilities: () => ({ available: true, supportsVariant: true }),
        canSearch: () => allowed,
        onEvaluation,
    });
    return {
        backend,
        commands,
        onEvaluation,
        block: () => {
            allowed = false;
        },
    };
}

test('navigation waits for readiness and starts only the latest position with its history', () => {
    const { backend, commands } = fixture();
    backend.start(request);
    expect(commands).toContain('position fen root moves e7e8+');
    expect(commands).toContain('setoption name EvalFile value local.nnue');
    backend.stop();
    const stoppedAt = commands.length;
    backend.start({ ...request, currentFen: 'discarded', moves: [] });
    backend.start({ ...request, currentFen: 'latest', moves: [], nnue: undefined });
    expect(commands).toHaveLength(stoppedAt);
    expect(backend.idle).toBe(false);
    backend.onReady();
    expect(commands.slice(stoppedAt)).toContain('position fen latest');
    expect(commands.slice(stoppedAt)).not.toContain('position fen discarded');
    expect(commands.slice(stoppedAt)).toContain('setoption name Use NNUE value false');
    expect(backend.status).toBe('searching');
});

test('stop blocks trailing evaluations and permission changes prevent a queued restart', () => {
    const { backend, onEvaluation, commands, block } = fixture();
    backend.start(request);
    const evaluation = { d: 5, p: 'e7e8+', s: { cp: 10 } };
    backend.deliver(evaluation);
    expect(onEvaluation).toHaveBeenCalledTimes(1);
    backend.stop();
    backend.deliver(evaluation);
    backend.start(request);
    block();
    const stoppedAt = commands.length;
    backend.onReady();
    backend.deliver(evaluation);
    expect(commands).toHaveLength(stoppedAt);
    expect(onEvaluation).toHaveBeenCalledTimes(1);
    expect(backend.idle).toBe(true);
});

test('destruction prevents deferred searches and evaluation delivery', () => {
    const { backend, commands, onEvaluation } = fixture();
    backend.stop();
    backend.start(request);
    backend.destroy();
    const end = commands.length;
    backend.onReady();
    backend.start(request);
    backend.deliver({ d: 5, p: 'e7e8+', s: { cp: 10 } });
    expect(commands).toHaveLength(end);
    expect(onEvaluation).not.toHaveBeenCalled();
    expect(backend.status).toBe('disconnected');
});


test('terminated WASM engine cannot restart or deliver stale results', () => {
    const { backend, commands, onEvaluation } = fixture();
    backend.start(request);
    backend.stop();
    backend.start({ ...request, currentFen: 'queued', moves: [] });
    backend.onFailure('worker exited');
    expect(backend.status).toBe('error');
    expect(backend.canDeliverEvaluation).toBe(false);
    const atFailure = commands.length;
    backend.onReady();
    backend.start(request);
    backend.stop();
    backend.deliver({ d: 1, p: 'e7e8+', s: { cp: 10 } });
    expect(commands).toHaveLength(atFailure);
    expect(onEvaluation).not.toHaveBeenCalled();
});
