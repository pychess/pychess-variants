import { expect, jest, test, beforeEach } from '@jest/globals';
import { upsertActiveCevalRound } from '../client/antiCheat';
import { BrowserSearchBackend } from '../client/analysis/browserSearchBackend';
import { GameController } from '../client/gameCtrl';

jest.unstable_mockModule('chessgroundx', () => ({ Chessground: jest.fn() }));
const { AnalysisController } = await import('../client/analysis/analysisCtrl');
const fetcher = jest.fn<typeof fetch>();
const permission = jest.fn(async () => ({ state: 'granted' }));
const registration = {
    id: 'engine01',
    address: 'http://127.0.0.1:19670',
    token: 'x'.repeat(43),
    engine: {
        name: 'Native engine',
        variants: ['chess'],
        chess960: true,
        customRules: false,
        maxThreads: 2,
        maxHash: 64,
        maxMultiPv: 2,
    },
};

beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    fetcher.mockReset();
    permission.mockReset().mockResolvedValue({ state: 'granted' });
    Object.defineProperty(globalThis, 'fetch', { value: fetcher, configurable: true });
    Object.defineProperty(navigator, 'permissions', { value: { query: permission }, configurable: true });
});

function controller() {
    const ctrl = Object.create(AnalysisController.prototype) as any;
    ctrl.destroyed = false;
    ctrl.anon = false;
    ctrl.externalAllowed = true;
    ctrl.externalRulesInvalid = false;
    ctrl.engineSource = 'external';
    ctrl.engineVariant = 'chess';
    ctrl.chess960 = false;
    ctrl.analysisContext = { capabilities: { engineTools: true, localAnalysisAllowed: true } };
    ctrl.externalEngines = [];
    ctrl.externalEngineId = registration.id;
    ctrl.externalSearch = {
        supports: jest.fn(() => true),
        stop: jest.fn(),
        disconnect: jest.fn(),
        connect: jest.fn(async () => {}),
        status: 'ready',
    };
    ctrl.browserSearch = { stop: jest.fn() };
    ctrl.connectionGeneration = 0;
    ctrl.engineStop = jest.fn();
    ctrl.pvboxIni = jest.fn();
    ctrl.refreshEngineLabel = jest.fn();
    ctrl.refreshLocalAnalysisAvailabilityForAntiCheat = jest.fn();
    return ctrl;
}

test('external capability is independent of WASM readiness and variant support', () => {
    const ctrl = controller();
    ctrl.localEngine = false;
    ctrl.isEngineReady = false;
    ctrl.variantSupportedByFSF = false;
    expect(ctrl.isSelectedEngineReady()).toBe(true);
    ctrl.engineSource = 'browser';
    expect(ctrl.isSelectedEngineReady()).toBe(false);
});

test('registration selection applies variant restrictions alongside exact-rule validity', () => {
    const ctrl = controller();
    const connection = {
        engine: {
            name: 'One engine',
            variants: ['chess', 'alice'],
            chess960: true,
            customRules: true,
            maxThreads: 2,
            maxHash: 64,
            maxMultiPv: 2,
            variantRestrictions: { alice: { chess960: false, customRules: false } },
        },
    };
    expect(ctrl.supportsExternalEngine(connection)).toBe(true);
    ctrl.engineVariant = 'alice';
    expect(ctrl.supportsExternalEngine(connection)).toBe(true);
    ctrl.chess960 = true;
    expect(ctrl.supportsExternalEngine(connection)).toBe(false);
    ctrl.chess960 = false;
    ctrl.externalRulesText = '[alice:chess]';
    expect(ctrl.supportsExternalEngine(connection)).toBe(false);
    ctrl.engineVariant = 'new-snapshot';
    expect(ctrl.supportsExternalEngine(connection)).toBe(true);
    ctrl.externalRulesInvalid = true;
    expect(ctrl.supportsExternalEngine(connection)).toBe(false);
});

test('ongoing games, Practice/unsupported adapters, concealed lessons and anti-cheat block external use', () => {
    const ctrl = controller();
    expect(ctrl.canUseExternalEngine()).toBe(true);
    ctrl.analysisContext.capabilities.localAnalysisAllowed = false;
    expect(ctrl.canUseExternalEngine()).toBe(false);
    ctrl.analysisContext.capabilities.localAnalysisAllowed = true;
    ctrl.externalAllowed = false;
    expect(ctrl.canUseExternalEngine()).toBe(false);
    ctrl.externalAllowed = true;
    Object.defineProperty(ctrl, 'analysisExtension', {
        value: { allowComputerSearch: () => false },
        configurable: true,
    });
    expect(ctrl.canUseExternalEngine()).toBe(false);
    Object.defineProperty(ctrl, 'analysisExtension', { value: undefined, configurable: true });
    upsertActiveCevalRound('active-game', Date.now());
    expect(ctrl.canUseExternalEngine()).toBe(false);
    expect(ctrl.isSelectedEngineReady()).toBe(false);
});

test('switching source during pairing does not persist or activate a stale connection', async () => {
    const ctrl = controller();
    let resolvePairing: () => void = () => {};
    ctrl.externalSearch.connect = jest.fn(
        () =>
            new Promise<void>(resolve => {
                resolvePairing = resolve;
            }),
    );
    const pairing = ctrl.connectExternalEngine('http://127.0.0.1:9670', 'x'.repeat(43));
    ctrl.selectEngineSource('browser');
    resolvePairing();
    await pairing;
    expect(ctrl.engineSource).toBe('browser');
    expect(localStorage.getItem('externalEngineConnection')).toBeNull();
    expect(localStorage.getItem('analysisEngineSource')).toBe('browser');
    expect(ctrl.pvboxIni).toHaveBeenCalledTimes(1);
});

test('controller destruction sends WASM stop commands through the real guarded message path', () => {
    const ctrl = controller();
    const postMessage = jest.fn();
    Object.defineProperty(window, 'fsf', { value: { postMessage }, configurable: true });
    const baseDestroy = jest.spyOn(GameController.prototype, 'destroy').mockImplementation(() => {});
    ctrl.cancelAnalysisSession = jest.fn();
    ctrl.restoreFsfPrompt = jest.fn();
    ctrl.pvHoverPreview = { destroy: jest.fn() };
    ctrl.tree = { destroy: jest.fn() };
    ctrl.externalSearch.destroy = jest.fn();
    ctrl.browserSearch = new BrowserSearchBackend({
        postMessage: command => ctrl.fsfPostMessage(command),
        capabilities: () => ({ available: true, supportsVariant: true }),
        canSearch: () => !ctrl.destroyed,
        onEvaluation: jest.fn(),
    });
    try {
        ctrl.destroy();
        expect(postMessage.mock.calls).toEqual([['stop'], ['isready']]);
        expect(ctrl.browserSearch.status).toBe('disconnected');
        ctrl.fsfPostMessage('go depth 99');
        expect(postMessage).toHaveBeenCalledTimes(2);
    } finally {
        baseDestroy.mockRestore();
        Reflect.deleteProperty(window, 'fsf');
    }
});

test('anonymous analysis cannot select or restore account engines', async () => {
    localStorage.setItem('analysisEngineSource', 'external');
    const ctrl = controller();
    ctrl.engineSource = 'browser';
    ctrl.anon = true;
    expect(ctrl.canUseExternalEngine()).toBe(false);
    await ctrl.restoreExternalEngine();
    await ctrl.selectExternalEngine(registration.id);
    expect(fetcher).not.toHaveBeenCalled();
    expect(ctrl.engineSource).toBe('browser');
});

test('a saved native preference restores an eligible engine after account discovery', async () => {
    localStorage.setItem('analysisEngineSource', 'external');
    const ctrl = controller();
    ctrl.engineSource = 'browser';
    fetcher.mockResolvedValue({ ok: true, json: async () => [registration] } as Response);
    await ctrl.restoreExternalEngine();
    expect(ctrl.externalSearch.connect).toHaveBeenCalledWith(registration.address, registration.token);
    expect(ctrl.engineSource).toBe('external');
    expect(ctrl.externalEngines).toHaveLength(1);
});

test.each(['discovery-failed', 'missing', 'unsupported', 'permission', 'browser-preference', 'page-policy'])(
    'automatic restoration keeps WASM available: %s',
    async reason => {
        localStorage.setItem('analysisEngineSource', reason === 'browser-preference' ? 'browser' : 'external');
        const ctrl = controller();
        ctrl.engineSource = 'browser';
        ctrl.localEngine = ctrl.isEngineReady = ctrl.variantSupportedByFSF = true;
        if (reason === 'discovery-failed') fetcher.mockRejectedValue(new Error('Unavailable'));
        else
            fetcher.mockResolvedValue({
                ok: true,
                json: async () =>
                    reason === 'missing' ? [] : [{ ...registration, address: 'http://127.0.0.1:19671' }],
            } as Response);
        if (reason === 'unsupported') ctrl.engineVariant = 'shogi';
        if (reason === 'permission') permission.mockResolvedValue({ state: 'prompt' });
        if (reason === 'page-policy') ctrl.analysisContext.capabilities.engineTools = false;
        await ctrl.restoreExternalEngine();
        expect(ctrl.externalSearch.connect).not.toHaveBeenCalled();
        expect(ctrl.engineSource).toBe('browser');
        expect(ctrl.isSelectedEngineReady()).toBe(true);
    },
);

test('failed automatic pairing returns to browser analysis while explicit pairing keeps its error', async () => {
    localStorage.setItem('analysisEngineSource', 'external');
    const ctrl = controller();
    ctrl.engineSource = 'browser';
    fetcher.mockResolvedValue({ ok: true, json: async () => [registration] } as Response);
    ctrl.externalSearch.connect.mockRejectedValue(new Error('Connection refused'));
    await ctrl.restoreExternalEngine();
    expect(ctrl.engineSource).toBe('browser');
    await ctrl.selectExternalEngine(registration.id);
    expect(ctrl.engineSource).toBe('external');
    expect(ctrl.externalEngineStatus).toBe('error');
});

test('a manual source selection supersedes pending account discovery', async () => {
    localStorage.setItem('analysisEngineSource', 'external');
    const ctrl = controller();
    ctrl.engineSource = 'browser';
    let resolveDiscovery: (value: Response) => void = () => {};
    fetcher.mockReturnValue(
        new Promise<Response>(resolve => {
            resolveDiscovery = resolve;
        }),
    );
    const restoring = ctrl.restoreExternalEngine();
    ctrl.selectEngineSource('browser');
    resolveDiscovery({ ok: true, json: async () => [registration] } as Response);
    await restoring;
    expect(ctrl.externalSearch.connect).not.toHaveBeenCalled();
    expect(ctrl.externalEngines).toEqual([]);
    expect(ctrl.engineSource).toBe('browser');
});
