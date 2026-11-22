import { h, VNode } from 'snabbdom';

import { _ } from '../i18n';
import { alertDialog } from '../alertDialog';
import { confirmDialog } from '../confirmDialog';
import { Settings, BooleanSettings, NumberSettings, StringSettings } from '../settings';
import { nnueFile, slider, sliderFromList, toggleSwitch } from '../view';
import { downloadOfficialNnue, formatNnueSize, requiresLargeNnueConfirmation } from '../nnueDownload';
import {
    nnueLookupContextForVariant,
    officialNnueNetwork,
    type OfficialNnueLookupContext,
    type OfficialNnueNetwork,
} from '../nnueManifest';
import {
    hasNnueFile,
    removeNnueFile,
    removeObsoleteOfficialNnue,
    storedNnueMetadata,
    storedNnueSize,
    type NnueFileMetadata,
} from '../nnueStorage';
import { AnalysisController } from './analysisCtrl';
import { patch } from '../document';
import { updateMovelist } from '../movelist';
import { ExternalEngineSettings } from './externalEngineSettings';

function installEnginePreferencesDismissal(vnode: VNode): void {
    const panel = vnode.elm as HTMLElement;
    const gear = document.getElementById('analysis-engine-gear');
    const close = () => { panel.hidden = true; gear?.setAttribute('aria-expanded', 'false'); };
    const onPointerDown = (event: PointerEvent) => {
        if (!panel.contains(event.target as Node) && !gear?.contains(event.target as Node)) close();
    };
    const onKeyDown = (event: KeyboardEvent) => {
        if (event.key === 'Escape' && !panel.hidden) { close(); (gear as HTMLElement | null)?.focus(); }
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    (panel as HTMLElement & { removeEngineDismissal?: () => void }).removeEngineDismissal = () => {
        document.removeEventListener('pointerdown', onPointerDown);
        document.removeEventListener('keydown', onKeyDown);
    };
}


class AnalysisSettings {
    ctrl: AnalysisController;
    settings: { [key: string]: Settings<number | boolean | string> };
    assetURL: string;
    readonly externalEngine = new ExternalEngineSettings(() => this.ctrl);

    constructor() {
        this.settings = {};
        this.settings['showServerAnalysis'] = new ServerAnalysisSettings(this);
        this.settings['showGauge'] = new GaugeSettings();
        this.settings['arrow'] = new ArrowSettings(this);
        this.settings['variationArrows'] = new VariationArrowSettings(this);
        this.settings['maneuverArrows'] = new ManeuverArrowSettings(this);
        this.settings['showMoveAnnotationsOnBoard'] = new MoveAnnotationsSettings(this);
        this.settings['inlineNotation'] = new InlineNotationSettings(this);
        this.settings['disclosureMode'] = new DisclosureModeSettings(this);
        this.settings['infiniteAnalysis'] = new InfiniteAnalysisSettings(this);
        this.settings['multipv'] = new MultiPVSettings(this);
        this.settings['threads'] = new ThreadsSettings(this);
        this.settings['hash'] = new HashSettings(this);
        this.settings['nnue'] = new NnueSettings(this);
        this.settings['fsfDebug'] = new FsfDebugSettings(this);
    }

    getSettings(family: string): NnueFileSettings {
        const fullName = family + 'Nnue';
        if (!this.settings[fullName]) {
            this.settings[fullName] = new NnueFileSettings(this, family);
        }
        return this.settings[fullName] as NnueFileSettings;
    }

    engineView(variant: {
        readonly name: string;
        readonly cataloguedSource?: 'user' | 'fairy-stockfish-builtin';
        readonly nnueFingerprint?: string;
    }): VNode {
        const nnueFileSettings = this.getSettings(variant.name);
        nnueFileSettings.setLookupContext(nnueLookupContextForVariant(variant));
        return h('div.analysis-engine-preferences', {
            attrs: { hidden: true, id: 'analysis-engine-preferences' },
            hook: {
                insert: installEnginePreferencesDismissal,
                destroy: vnode => (vnode.elm as HTMLElement & { removeEngineDismissal?: () => void }).removeEngineDismissal?.(),
            },
        }, [
            this.externalEngine.view(),
            h('div.analysis-settings-group', [
                this.settings['multipv'].view(),
                this.settings['threads'].view(),
                this.settings['hash'].view(),
                this.settings['infiniteAnalysis'].view(),
            ]),
            h('div.analysis-settings-group.browser-engine-settings', [
                this.settings['nnue'].view(),
                nnueFileSettings.view(),
            ]),
            h('div.analysis-settings-group.browser-engine-settings', [this.settings['fsfDebug'].view()]),
        ]);
    }

    view(variant: {
        readonly name: string;
        readonly cataloguedSource?: 'user' | 'fairy-stockfish-builtin';
        readonly nnueFingerprint?: string;
    }) {
        if (!variant.name) return h('div.analysis-settings');

        return h('div.analysis-settings', [
            h('fieldset.analysis-general-settings-group', [
                h('legend', _('Move list')),
                this.settings['inlineNotation'].view(),
                this.settings['disclosureMode'].view(),
            ]),
            h('fieldset.analysis-general-settings-group', [
                h('legend', _('Board')),
                this.settings['arrow'].view(),
                this.settings['variationArrows'].view(),
                this.settings['maneuverArrows'].view(),
                this.settings['showMoveAnnotationsOnBoard'].view(),
            ]),
            h('fieldset.analysis-general-settings-group', [
                h('legend', _('General')),
                this.settings['showServerAnalysis'].view(),
                this.settings['showGauge'].view(),
            ]),
        ]);
    }
}

class ServerAnalysisSettings extends BooleanSettings {
    constructor(private readonly analysisSettings: AnalysisSettings) {
        super('showServerAnalysis', true);
    }

    update(): void {
        this.analysisSettings.ctrl.setServerAnalysisVisibility(this.value);
    }

    view(): VNode {
        return h(
            'div.serverAnalysis-toggle',
            toggleSwitch(this, 'serverAnalysis-enabled', _('Show server analysis'), false),
        );
    }
}

class GaugeSettings extends BooleanSettings {
    constructor() {
        super('showGauge', true);
    }

    update(): void {
        document.querySelector('.analysis-app')?.classList.toggle('gauge-off', !this.value);
        window.dispatchEvent(new Event('resize'));
    }

    view(): VNode {
        return h('div.gauge-toggle', toggleSwitch(this, 'gauge-enabled', _('Show evaluation gauge'), false));
    }
}

class InlineNotationSettings extends BooleanSettings {
    readonly analysisSettings: AnalysisSettings;

    constructor(analysisSettings: AnalysisSettings) {
        super('inlineNotation', false);
        this.analysisSettings = analysisSettings;
    }

    update(): void {
        const ctrl = this.analysisSettings.ctrl;
        ctrl.inlineNotation = this.value;
        updateMovelist(ctrl, true, false);
    }

    view(): VNode {
        return h(
            'div.inlineNotation-toggle',
            toggleSwitch(this, 'inlineNotation-enabled', _('Inline notation'), false),
        );
    }
}

class DisclosureModeSettings extends BooleanSettings {
    readonly analysisSettings: AnalysisSettings;

    constructor(analysisSettings: AnalysisSettings) {
        super('disclosureMode', false);
        this.analysisSettings = analysisSettings;
    }

    update(): void {
        const ctrl = this.analysisSettings.ctrl;
        ctrl.disclosureMode = this.value;
        updateMovelist(ctrl, true, false);
    }

    view(): VNode {
        return h(
            'div.disclosureMode-toggle',
            toggleSwitch(this, 'disclosureMode-enabled', _('Disclosure buttons'), false),
        );
    }
}

class ArrowSettings extends BooleanSettings {
    readonly analysisSettings: AnalysisSettings;

    constructor(analysisSettings: AnalysisSettings) {
        super('arrow', true);
        this.analysisSettings = analysisSettings;
    }

    update(): void {
        const ctrl = this.analysisSettings.ctrl;
        if ('arrow' in ctrl) ctrl.arrow = this.value;
    }

    view(): VNode {
        return h('div.arrow-toggle', toggleSwitch(this, 'arrow-enabled', _('Best move arrow'), false));
    }
}

class VariationArrowSettings extends BooleanSettings {
    constructor(private readonly analysisSettings: AnalysisSettings) {
        super('variationArrows', true);
    }

    update(): void {
        const ctrl = this.analysisSettings.ctrl;
        ctrl.variationArrows = this.value;
        ctrl.setAutoShapes();
    }

    view(): VNode {
        return h(
            'div.variation-arrows-toggle',
            toggleSwitch(this, 'variation-arrows-enabled', _('Show variation arrows'), false),
        );
    }
}

class ManeuverArrowSettings extends BooleanSettings {
    constructor(private readonly analysisSettings: AnalysisSettings) {
        super('maneuverArrows', true);
    }

    update(): void {
        const ctrl = this.analysisSettings.ctrl;
        ctrl.maneuverArrowsEnabled = this.value;
        ctrl.setAutoShapes();
    }

    view(): VNode {
        return h(
            'div.maneuver-arrows-toggle',
            toggleSwitch(this, 'maneuver-arrows-enabled', _('Show maneuver arrows'), false),
        );
    }
}

class MoveAnnotationsSettings extends BooleanSettings {
    constructor(private readonly analysisSettings: AnalysisSettings) {
        super('showMoveAnnotationsOnBoard', true);
    }

    update(): void {
        const ctrl = this.analysisSettings.ctrl;
        ctrl.showMoveAnnotationsOnBoard = this.value;
        ctrl.setAutoShapes();
    }

    view(): VNode {
        return h(
            'div.move-annotations-toggle',
            toggleSwitch(this, 'move-annotations-enabled', _('Show move annotations'), false),
        );
    }
}

class InfiniteAnalysisSettings extends BooleanSettings {
    readonly analysisSettings: AnalysisSettings;

    constructor(analysisSettings: AnalysisSettings) {
        super('infiniteAnalysis', false);
        this.analysisSettings = analysisSettings;
    }

    update(): void {
        const ctrl = this.analysisSettings.ctrl;
        if ('maxDepth' in ctrl) {
            ctrl.maxDepth = this.value ? 99 : 18;
            ctrl.pvboxIni();
        }
    }

    view(): VNode {
        return h(
            'div.infiniteAnalysis-toggle',
            toggleSwitch(this, 'infiniteAnalysis-enabled', _('Infinite analysis'), false),
        );
    }
}

class MultiPVSettings extends NumberSettings {
    readonly analysisSettings: AnalysisSettings;

    constructor(analysisSettings: AnalysisSettings) {
        super('multipv', 1);
        this.analysisSettings = analysisSettings;
    }

    update(): void {
        const ctrl = this.analysisSettings.ctrl;
        if ('multipv' in ctrl) {
            ctrl.multipv = this.value;
            ctrl.pvboxIni();
            ctrl.autoShapes = Array.from({ length: ctrl.multipv }, () => []);
            ctrl.chessground.setAutoShapes([]);
            const settingsEl = document.querySelector('div.multipv_range_value') as HTMLElement;
            patch(settingsEl, h('div.multipv_range_value', `${this.value} / 5`));
        }
    }

    view(): VNode {
        const els = slider(this, 'multipv', 0, 5, 1, _('Multiple lines'));
        els.push(h('div.multipv_range_value', `${this.value} / 5`));
        return h('div.labelled', els);
    }
}

class ThreadsSettings extends NumberSettings {
    readonly analysisSettings: AnalysisSettings;
    readonly maxThreads: number;

    constructor(analysisSettings: AnalysisSettings) {
        super('threads', 1);
        this.analysisSettings = analysisSettings;
        this.maxThreads = Math.min(Math.max((navigator.hardwareConcurrency || 1) - 1, 1), 32);
    }

    update(): void {
        const ctrl = this.analysisSettings.ctrl;
        if ('threads' in ctrl) {
            ctrl.threads = this.value;
            ctrl.pvboxIni();
            const settingsEl = document.querySelector('div.threads_range_value') as HTMLElement;
            patch(settingsEl, h('div.threads_range_value', `${this.value} / ${this.maxThreads}`));
        }
    }

    view(): VNode {
        const els = slider(this, 'threads', 1, this.maxThreads, 1, _('CPUs'));
        els.push(h('div.threads_range_value', `${this.value} / ${this.maxThreads}`));
        return h('div.labelled', els);
    }
}

// Some utility functions are borrowed from lila ui code
const isAndroid = (): boolean => /Android/.test(navigator.userAgent);

const isIOS = (): boolean => /iPhone|iPod/.test(navigator.userAgent) || isIPad();

// some newer iPads pretend to be Macs, hence checking for "Macintosh"
const isIPad = (): boolean => navigator?.maxTouchPoints > 2 && /iPad|Macintosh/.test(navigator.userAgent);

// the numbers returned by maxHashMB seem small, but who knows if wasm stockfish performance even
// scales like native stockfish with increasing hash. prefer smaller, non-crashing values
// steer the high performance crowd towards external engine as it gets better
const maxHashMB = (): number => {
    let maxHash = 512; // allocating 1024 often fails and offers little benefit over 512, or 16 for that matter
    if (isAndroid()) maxHash = 64; // budget androids are easy to crash @ 128
    else if (isIPad()) maxHash = 64; // iPadOS safari pretends to be desktop but acts more like iphone
    else if (isIOS()) maxHash = 32;
    return maxHash;
};

class HashSettings extends NumberSettings {
    readonly analysisSettings: AnalysisSettings;
    readonly maxHash: number;

    constructor(analysisSettings: AnalysisSettings) {
        super('hash', 16);
        this.analysisSettings = analysisSettings;
        this.maxHash = maxHashMB();
    }

    update(): void {
        const ctrl = this.analysisSettings.ctrl;
        if ('threads' in ctrl) {
            ctrl.hash = this.value;
            ctrl.pvboxIni();
            const settingsEl = document.querySelector('div.hash_range_value') as HTMLElement;
            patch(settingsEl, h('div.hash_range_value', `${this.value}MB`));
        }
    }

    view(): VNode {
        const hashList = [...Array(10).keys()].map(i => 2 ** i).filter(n => n >= 16 && n <= this.maxHash);
        const els = sliderFromList(this, 'hash', _('Memory'), 'hashList', hashList);
        els.push(h('div.hash_range_value', `${this.value}MB`));
        return h('div.labelled', els);
    }
}

class NnueSettings extends BooleanSettings {
    readonly analysisSettings: AnalysisSettings;

    constructor(analysisSettings: AnalysisSettings) {
        super('nnue', true);
        this.analysisSettings = analysisSettings;
    }

    update(): void {
        const ctrl = this.analysisSettings.ctrl;
        if ('nnue' in ctrl) {
            ctrl.nnue = this.value;
            ctrl.refreshNnueIndicator();
            ctrl.pvboxIni();
        }
    }

    view(): VNode {
        return h('div.nnue-toggle', toggleSwitch(this, 'nnue-enabled', _('Use NNUE'), false));
    }
}

class NnueFileSettings extends StringSettings {
    readonly analysisSettings: AnalysisSettings;
    readonly variant: string;
    private root?: HTMLElement;
    private stateGeneration = 0;
    // Rendering happens before AnalysisController is constructed. Default to
    // the restrictive UDV context until AnalysisSettings.view supplies the
    // actual variant identity.
    private lookupContext: OfficialNnueLookupContext = { userDefined: true };

    constructor(analysisSettings: AnalysisSettings, variant: string) {
        super(variant + '-nnue', '');
        this.analysisSettings = analysisSettings;
        this.variant = variant;
    }

    setLookupContext(context: OfficialNnueLookupContext): void {
        this.lookupContext = context;
    }

    update(): void {
        const ctrl = this.analysisSettings.ctrl;
        if ('evalFile' in ctrl) {
            ctrl.evalFile = this.value;
            if (this.value) ctrl.nnueIni();
            else ctrl.nnueClear();
        }
    }

    view(): VNode {
        const network = officialNnueNetwork(this.variant, this.lookupContext);
        const actions: VNode[] = [];
        if (network) actions.push(this.officialDownloadButton(network));
        actions.push(
            h(
                'button.button.nnue-remove-button',
                {
                    props: { type: 'button', hidden: true },
                    on: { click: () => void this.removeInstalled() },
                },
                _('Remove NNUE'),
            ),
        );

        const children: VNode[] = [
            h('div.nnue-network-status', [
                h('strong.nnue-network-state', _('Checking NNUE storage…')),
                h('span.nnue-network-detail', network ? this.officialNetworkDetail(network) : ''),
            ]),
            h('div.nnue-network-actions', actions),
        ];

        if (network) {
            children.push(
                h('div.nnue-download-feedback', [
                    h('progress.nnue-download-progress', {
                        props: { max: network.bytes, value: 0, hidden: true },
                    }),
                    h('span.nnue-download-status'),
                ]),
            );
        }

        children.push(
            h(
                'div.labelled.nnue-manual-file',
                nnueFile(this, 'evalFile', _('Manual NNUE file'), this.variant, () => {
                    void this.refreshStorageState(_('Manual NNUE ready'));
                }),
            ),
        );

        return h(
            'div.nnue-file-settings',
            {
                hook: {
                    insert: vnode => {
                        this.root = vnode.elm as HTMLElement;
                        void this.refreshStorageState();
                    },
                },
            },
            children,
        );
    }

    private officialDownloadButton(network: OfficialNnueNetwork): VNode {
        return h(
            'button.button.nnue-download-button',
            {
                props: { type: 'button' },
                on: { click: event => void this.downloadOfficial(event, network) },
            },
            _('Download official NNUE (%1)', formatNnueSize(network.bytes)),
        );
    }

    private async refreshStorageState(message = ''): Promise<void> {
        const root = this.root;
        if (!root) return;

        const generation = ++this.stateGeneration;
        const network = officialNnueNetwork(this.variant, this.lookupContext);
        let statusMessage = message;
        let selected = this.value;
        let available = false;
        let metadata: NnueFileMetadata | undefined;
        try {
            const obsolete = await removeObsoleteOfficialNnue(this.variant, network);
            if (obsolete && selected === obsolete) {
                this.value = '';
                selected = '';
                statusMessage ||=
                    network === undefined
                        ? _('Official NNUE removed because this variant definition no longer matches it')
                        : _('Previous official NNUE removed; updated network available');
            }

            if (selected) {
                metadata = await storedNnueMetadata(this.variant);
                available = await hasNnueFile(this.variant, selected);

                if (!available && network?.file === selected && metadata?.source !== 'manual') {
                    this.value = '';
                    selected = '';
                    metadata = undefined;
                    statusMessage ||= _('Official NNUE cache is missing; download it again.');
                } else if (available && network?.file === selected && metadata?.source !== 'manual') {
                    const storedBytes = await storedNnueSize(this.variant, selected);
                    if (storedBytes !== network.bytes) {
                        await removeNnueFile(this.variant, selected);
                        this.value = '';
                        selected = '';
                        available = false;
                        metadata = undefined;
                        statusMessage = _('Corrupt or incomplete official NNUE removed; download it again.');
                    }
                }
            }
        } catch (error) {
            if (generation !== this.stateGeneration || root !== this.root) return;
            const state = root.querySelector('.nnue-network-state');
            const detail = root.querySelector('.nnue-network-detail');
            const downloadButton = root.querySelector('.nnue-download-button') as HTMLButtonElement | null;
            const removeButton = root.querySelector('.nnue-remove-button') as HTMLButtonElement | null;
            if (state) state.textContent = _('Unable to inspect NNUE storage');
            if (detail) detail.textContent = error instanceof Error ? error.message : String(error);
            if (downloadButton) downloadButton.disabled = false;
            if (removeButton) {
                removeButton.hidden = !selected;
                removeButton.disabled = false;
            }
            this.setManualInputDisabled(root, false);
            this.hideDownloadProgress(root);
            this.updateDownloadStatus(root, statusMessage);
            return;
        }
        if (generation !== this.stateGeneration || root !== this.root) return;

        const state = root.querySelector('.nnue-network-state');
        const detail = root.querySelector('.nnue-network-detail');
        const downloadButton = root.querySelector('.nnue-download-button') as HTMLButtonElement | null;
        const removeButton = root.querySelector('.nnue-remove-button') as HTMLButtonElement | null;
        const officialInstalled =
            network !== undefined && available && selected === network.file && metadata?.source !== 'manual';

        if (state && detail) {
            if (officialInstalled && network) {
                state.textContent = _('Official NNUE cached');
                detail.textContent = this.officialNetworkDetail(network);
            } else if (selected && available) {
                state.textContent = _('Manual NNUE supplied');
                detail.textContent = selected;
            } else if (selected) {
                state.textContent = _('Selected NNUE file is missing');
                detail.textContent = selected;
            } else if (network) {
                state.textContent = _('Official NNUE not installed');
                detail.textContent = this.officialNetworkDetail(network);
            } else {
                state.textContent = _('No NNUE network installed');
                detail.textContent = _('Choose a manual .nnue file below.');
            }
        }

        if (downloadButton && network) {
            downloadButton.disabled = officialInstalled;
            downloadButton.textContent = officialInstalled
                ? _('Official NNUE cached')
                : _('Download official NNUE (%1)', formatNnueSize(network.bytes));
        }
        if (removeButton) {
            removeButton.hidden = !selected;
            removeButton.disabled = false;
        }
        this.setManualInputDisabled(root, false);
        this.hideDownloadProgress(root);
        this.updateDownloadStatus(root, statusMessage);
    }

    private async downloadOfficial(event: Event, network: OfficialNnueNetwork): Promise<void> {
        const ctrl = this.analysisSettings.ctrl;
        const button = event.currentTarget as HTMLButtonElement;
        const root = this.root;
        if (!root) return;

        if (!ctrl.nnueDownloadRoot) {
            await alertDialog({ text: _('Official NNUE downloads are not configured on this server.') });
            return;
        }

        if (requiresLargeNnueConfirmation(network)) {
            const size = `${formatNnueSize(network.bytes)} (${_('%1 bytes', network.bytes.toLocaleString())})`;
            const confirmed = await confirmDialog({
                text: _('This NNUE network is %1. Download it now?', size),
                confirmText: _('Download'),
                cancelText: _('Cancel'),
            });
            if (!confirmed) return;
        }

        button.disabled = true;
        const removeButton = root.querySelector('.nnue-remove-button') as HTMLButtonElement | null;
        if (removeButton) removeButton.disabled = true;
        this.setManualInputDisabled(root, true);
        this.updateDownloadProgress(root, 0, network.bytes);

        try {
            const data = await downloadOfficialNnue(this.variant, network, ctrl.nnueDownloadRoot, progress => {
                this.updateDownloadProgress(root, progress.loaded, progress.total);
            });

            localStorage[this.name] = network.file;
            this._value = network.file;
            ctrl.evalFile = network.file;
            ctrl.nnueIni(data);

            await this.refreshStorageState(_('NNUE ready'));
        } catch (error) {
            await this.refreshStorageState();
            const message = error instanceof Error ? error.message : String(error);
            const retryButton = root.querySelector('.nnue-download-button') as HTMLButtonElement | null;
            if (retryButton) {
                retryButton.disabled = false;
                retryButton.textContent = _('Retry official NNUE (%1)', formatNnueSize(network.bytes));
            }
            this.updateDownloadStatus(root, _('Download failed — retry is available'));
            await alertDialog({ text: _('NNUE download failed: %1', message) });
        }
    }

    private async removeInstalled(): Promise<void> {
        const selected = this.value;
        if (!selected) return;

        const confirmed = await confirmDialog({
            text: _('Remove the installed NNUE network from this browser?'),
            confirmText: _('Remove'),
            cancelText: _('Cancel'),
        });
        if (!confirmed) return;

        const root = this.root;
        const removeButton = root?.querySelector('.nnue-remove-button') as HTMLButtonElement | null;
        if (removeButton) removeButton.disabled = true;
        if (root) this.setManualInputDisabled(root, true);

        try {
            await removeNnueFile(this.variant, selected);
            this.value = '';
            await this.refreshStorageState(_('NNUE removed'));
        } catch (error) {
            if (removeButton) removeButton.disabled = false;
            if (root) this.setManualInputDisabled(root, false);
            const message = error instanceof Error ? error.message : String(error);
            await alertDialog({ text: _('Unable to remove NNUE: %1', message) });
        }
    }

    private setManualInputDisabled(root: HTMLElement, disabled: boolean): void {
        const input = root.querySelector('#evalFile') as HTMLInputElement | null;
        if (input) input.disabled = disabled;
    }

    private updateDownloadProgress(root: HTMLElement, loaded: number, total: number): void {
        const progress = root.querySelector('progress') as HTMLProgressElement | null;
        if (progress) {
            progress.hidden = false;
            progress.max = total;
            progress.value = Math.min(loaded, total);
        }
        const percent = total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : 0;
        this.updateDownloadStatus(
            root,
            _('Downloading NNUE… %1', `${formatNnueSize(loaded)} / ${formatNnueSize(total)} (${percent}%)`),
        );

        const state = root.querySelector('.nnue-network-state');
        if (state) state.textContent = _('Downloading official NNUE');
    }

    private hideDownloadProgress(root: HTMLElement): void {
        const progress = root.querySelector('progress') as HTMLProgressElement | null;
        if (progress) progress.hidden = true;
    }

    private updateDownloadStatus(root: HTMLElement, text: string): void {
        const status = root.querySelector('.nnue-download-status');
        if (status) status.textContent = text;
    }

    private officialNetworkDetail(network: OfficialNnueNetwork): string {
        const exactBytes = _('%1 bytes', network.bytes.toLocaleString());
        return `${network.file} · ${formatNnueSize(network.bytes)} · ${exactBytes}`;
    }
}

class FsfDebugSettings extends BooleanSettings {
    readonly analysisSettings: AnalysisSettings;

    constructor(analysisSettings: AnalysisSettings) {
        super('fsfDebug', false);
        this.analysisSettings = analysisSettings;
    }

    update(): void {
        const ctrl = this.analysisSettings.ctrl;
        if ('fsfDebug' in ctrl) {
            ctrl.fsfDebug = this.value;
            ctrl.pvboxIni();
        }
    }

    view(): VNode {
        return h('div.fsfDebug-toggle', toggleSwitch(this, 'fsfDebug-enabled', _('Enable engine debug'), false));
    }
}

export const analysisSettings = new AnalysisSettings();

export class EngineSettings extends BooleanSettings {
    ctrl: AnalysisController;

    constructor(ctrl: AnalysisController) {
        super('localAnalysis', false);
        this.ctrl = ctrl;
    }

    update(): void {
        if (this.value && this.ctrl.isLocalAnalysisBlockedByAntiCheat()) {
            this._value = false;
            localStorage[this.name] = false;
            this.ctrl.disableLocalAnalysisForAntiCheat();
            this.ctrl.refreshLocalAnalysisAvailabilityForAntiCheat();
            return;
        }
        if (this.value && !this.ctrl.isLocalAnalysisAllowedByExtension()) {
            this.ctrl.suspendLocalAnalysisForExtension();
            this.ctrl.refreshLocalAnalysisAvailabilityForAntiCheat();
            return;
        }

        this.ctrl.localAnalysis = this.value;
        if (this.ctrl.localAnalysis) {
            this.ctrl.vinfo = patch(this.ctrl.vinfo, h('info#info', '-'));
        } else {
            this.ctrl.engineStop();
        }
        this.ctrl.pvboxIni();
    }

    view(): VNode {
        return h(
            'div.engine-toggle',
            toggleSwitch(
                this,
                'engine-enabled',
                _('Local engine'),
                !this.ctrl.analysisContext.capabilities.localAnalysisAllowed ||
                    this.ctrl.isLocalAnalysisBlockedByAntiCheat() ||
                    !this.ctrl.isLocalAnalysisAllowedByExtension() ||
                    !this.ctrl.isSelectedEngineReady(),
                true,
            ),
        );
    }
}
