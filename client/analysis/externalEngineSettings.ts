import { h, type VNode } from 'snabbdom';
import { _ } from '../i18n';
import type { AnalysisController } from './analysisCtrl';
import { ExternalEngineError, externalAddress, parseCapabilities, type ExternalCapabilities } from './externalSearchBackend';

const SOURCE_KEY = 'analysisEngineSource';
const ENGINE_KEY = 'analysisExternalEngineId';
const connectedThisPage = new Set<string>();

// Remove the alpha's browser-stored connection credential. Registrations now
// belong to the signed-in account and credentials remain only in page memory.
localStorage.removeItem('externalEngineConnection');

export interface ExternalConnection {
    id: string;
    address: string;
    token: string;
    engine: ExternalCapabilities;
}

export async function registeredExternalEngines(fetcher: typeof fetch = fetch): Promise<ExternalConnection[]> {
    const response = await fetcher.call(globalThis, '/api/external-engine', { credentials: 'same-origin', cache: 'no-store' });
    if (response.status === 401) return [];
    if (!response.ok) throw new ExternalEngineError('registration_unavailable');
    const data: unknown = await response.json();
    if (!Array.isArray(data) || data.length > 100) throw new ExternalEngineError('invalid_protocol');
    return data.map(value => {
        if (!value || typeof value !== 'object' || typeof value.id !== 'string' || !/^\w{8}$/.test(value.id) ||
            typeof value.address !== 'string' || typeof value.token !== 'string' || !/^[\x21-\x7e]{32,256}$/.test(value.token))
            throw new ExternalEngineError('invalid_protocol');
        return { id: value.id, address: externalAddress(value.address), token: value.token,
            engine: parseCapabilities({ protocolVersion: 1, scorePov: 'sideToMove', engine: value.engine }) };
    });
}

export function preferredEngineSource(): 'browser' | 'external' {
    return localStorage.getItem(SOURCE_KEY) === 'external' ? 'external' : 'browser';
}

export function preferredExternalEngineId(): string | undefined {
    return localStorage.getItem(ENGINE_KEY) ?? undefined;
}

export function saveEngineSource(source: 'browser' | 'external'): void {
    localStorage.setItem(SOURCE_KEY, source);
}

export function rememberExternalConnection(connection: ExternalConnection): void {
    localStorage.setItem(ENGINE_KEY, connection.id);
    connectedThisPage.add(connection.address);
}

export function forgetExternalConnection(): void {
    localStorage.removeItem(ENGINE_KEY);
}

export async function mayRestoreExternalConnection(address: string): Promise<boolean> {
    if (connectedThisPage.has(address)) return true;
    try {
        const permission = await navigator.permissions.query({ name: 'loopback-network' as PermissionName });
        return permission.state === 'granted';
    } catch {
        return false;
    }
}

export class ExternalEngineSettings {
    private root?: HTMLElement;

    constructor(private readonly controller: () => AnalysisController | undefined) {}

    view(): VNode {
        return h('div.analysis-settings-group.external-engine-settings', {
            hook: { insert: vnode => { this.root = vnode.elm as HTMLElement; this.refresh(); } },
        }, [
            h('div.external-engine-field', [
                h('label', { attrs: { for: 'analysis-engine-source' } }, _('Engine')),
                h('div.external-engine-choice', [
                    h('select#analysis-engine-source', {
                        on: { change: event => {
                            const value = (event.target as HTMLSelectElement).value;
                            if (value === 'browser') this.controller()?.selectEngineSource('browser');
                            else void this.controller()?.selectExternalEngine(value);
                        } },
                    }, [h('option', { props: { value: 'browser' } }, 'Fairy-Stockfish 14+')]),
                    h('button#external-engine-forget.button', {
                        props: { type: 'button', hidden: true },
                        attrs: { title: _('Remove external engine'), 'aria-label': _('Remove external engine') },
                        on: { click: () => void this.controller()?.removeExternalEngine() },
                    }, [h('i.icon.icon-trash-o', { attrs: { 'aria-hidden': 'true' } })]),
                ]),
            ]),
            h('p#external-engine-status', { attrs: { role: 'status', 'aria-live': 'polite' }, props: { hidden: true } }),
            h('button#external-engine-retry.button', { props: { type: 'button', hidden: true },
                on: { click: () => { const ctrl = this.controller();
                    if (ctrl?.externalEngineId) void ctrl.selectExternalEngine(ctrl.externalEngineId);
                } } }, _('Retry')),
        ]);
    }

    refresh(): void {
        const ctrl = this.controller();
        const root = this.root;
        if (!ctrl || !root) return;
        const select = root.querySelector<HTMLSelectElement>('#analysis-engine-source');
        const remove = root.querySelector<HTMLButtonElement>('#external-engine-forget');
        const retry = root.querySelector<HTMLButtonElement>('#external-engine-retry');
        const status = root.querySelector<HTMLElement>('#external-engine-status');
        const allowed = ctrl.canUseExternalEngine();
        if (select) {
            // Engine discovery and chapter changes refresh this mounted control.
            select.querySelectorAll('option:not([value="browser"])').forEach(option => option.remove());
            for (const engine of ctrl.externalEngines) {
                const option = document.createElement('option');
                option.value = engine.id;
                option.textContent = engine.engine.name;
                option.disabled = !allowed || !ctrl.supportsExternalEngine(engine);
                select.appendChild(option);
            }
            select.value = ctrl.engineSource === 'external' ? ctrl.externalEngineId ?? 'browser' : 'browser';
        }
        if (remove) remove.hidden = ctrl.engineSource !== 'external' || !ctrl.externalEngineId;
        const error = ctrl.engineSource === 'external' && ctrl.externalEngineStatus === 'error';
        if (status) {
            status.textContent = ctrl.externalEngineStatusText();
            status.hidden = ctrl.engineSource !== 'external' ||
                (ctrl.externalEngineStatus !== 'loading' && !error && ctrl.isSelectedEngineReady());
        }
        if (retry) retry.hidden = !allowed || !error || !ctrl.externalEngineId;
        root.closest<HTMLElement>('.analysis-engine-preferences')?.setAttribute('data-engine-source', ctrl.engineSource);
    }
}
