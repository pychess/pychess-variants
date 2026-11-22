import { beforeEach, expect, jest, test } from '@jest/globals';
import { ExternalEngineSettings, registeredExternalEngines, rememberExternalConnection } from '../client/analysis/externalEngineSettings';
import type { AnalysisController } from '../client/analysis/analysisCtrl';
import { patch } from '../client/document';

beforeEach(() => localStorage.clear());

const engine = { id: 'engine01', address: 'http://127.0.0.1:9670', token: 'x'.repeat(43),
    engine: { name: 'My UCI engine', variants: ['chess'], chess960: true, customRules: false,
        maxThreads: 2, maxHash: 64, maxMultiPv: 2 } };

function mount(overrides: object = {}) {
    const ctrl = { externalEngines: [], engineSource: 'browser', externalEngineStatus: 'disconnected',
        canUseExternalEngine: () => true, externalEngineStatusText: () => 'Disconnected',
        isSelectedEngineReady: () => true,
        supportsExternalEngine: () => true, ...overrides };
    const settings = new ExternalEngineSettings(() => ctrl as AnalysisController);
    const host = document.createElement('div');
    document.body.appendChild(host);
    return { settings, element: patch(host, settings.view()).elm as HTMLElement };
}

test('settings contain only the engine selector when no external engine is registered', () => {
    const { element } = mount();
    expect(element.querySelector('input')).toBeNull();
    expect(element.querySelector('#external-engine-connect')).toBeNull();
    expect(element.querySelector('select')!.options.length).toBe(1);
    expect(element.querySelector<HTMLButtonElement>('#external-engine-forget')!.hidden).toBe(true);
    expect(element.querySelector<HTMLElement>('#external-engine-status')!.hidden).toBe(true);
    element.remove();
});

test('registered engines appear by name and policy disables their selection', () => {
    let allowed = false;
    const selectExternal = jest.fn();
    const remove = jest.fn();
    const { settings, element } = mount({ externalEngines: [engine], engineSource: 'external', externalEngineId: engine.id,
        externalEngineStatus: 'ready', canUseExternalEngine: () => allowed,
        selectExternalEngine: selectExternal, removeExternalEngine: remove });
    let option = element.querySelector<HTMLOptionElement>('option[value="engine01"]')!;
    expect(option.textContent).toBe('My UCI engine');
    expect(option.disabled).toBe(true);
    allowed = true;
    settings.refresh();
    option = element.querySelector<HTMLOptionElement>('option[value="engine01"]')!;
    expect(option.disabled).toBe(false);
    const select = element.querySelector('select')!;
    select.dispatchEvent(new Event('change'));
    expect(selectExternal).toHaveBeenCalledWith('engine01');
    const button = element.querySelector<HTMLButtonElement>('#external-engine-forget')!;
    expect(button.type).toBe('button');
    button.click();
    expect(remove).toHaveBeenCalledTimes(1);
    expect(element.querySelector<HTMLElement>('#external-engine-status')!.hidden).toBe(true);
    element.remove();
});

test('only connection errors show recovery controls', () => {
    const retry = jest.fn();
    const { element } = mount({ externalEngines: [engine], engineSource: 'external', externalEngineId: engine.id,
        externalEngineStatus: 'error', externalEngineStatusText: () => 'Unable to connect', selectExternalEngine: retry });
    expect(element.querySelector<HTMLElement>('#external-engine-status')!.hidden).toBe(false);
    const button = element.querySelector<HTMLButtonElement>('#external-engine-retry')!;
    expect(button.hidden).toBe(false);
    button.click();
    expect(retry).toHaveBeenCalledWith(engine.id);
    element.remove();
});

test('preferences store the registration ID, without connection or account credentials', () => {
    rememberExternalConnection(engine);
    expect(localStorage.getItem('analysisExternalEngineId')).toBe(engine.id);
    expect(localStorage.getItem('externalEngineConnection')).toBeNull();
    expect(JSON.stringify(localStorage)).not.toContain(engine.token);
});

test('account discovery uses same-origin authentication and validates loopback metadata', async () => {
    const fetcher = jest.fn<typeof fetch>(async () => ({ ok: true, status: 200, json: async () => [engine] }) as Response);
    expect(await registeredExternalEngines(fetcher)).toEqual([engine]);
    expect(fetcher.mock.calls[0]).toEqual(['/api/external-engine', { credentials: 'same-origin', cache: 'no-store' }]);
    const remote = async () => ({ ok: true, status: 200,
        json: async () => [{ ...engine, address: 'http://evil.example' }] }) as Response;
    await expect(registeredExternalEngines(remote)).rejects.toThrow('invalid_address');
});
