import { h, VNode } from 'snabbdom';

import { alertDialog } from './alertDialog';
import { confirmDialog } from './confirmDialog';
import { ensureCataloguedBoardCSS, ensurePieceCSS, patch, removeCataloguedBoardCSS } from './document';
import { checkRulesWithFsfWasm } from './fairyStockfish';
import { _ } from './i18n';
import { PyChessModel } from './types';
import {
    BOARD_FAMILIES,
    CataloguedVariantClientDocument,
    PIECE_FAMILIES,
    cataloguedCompatibleBoardFamily,
    cataloguedCompatiblePieceFamily,
    isBuiltinVariantName,
    registerCataloguedVariant,
    unregisterCataloguedVariant,
    VARIANTS,
} from './variants';

type VariantVisibility = 'private' | 'unlisted' | 'public';
type MessageTone = 'neutral' | 'success' | 'error';
type ManagementSort = 'updated' | 'played' | 'favorited' | 'newest' | 'name';

const MAX_DISPLAY_NAME_LENGTH = 50;
const DISPLAY_NAME_PATTERN = new RegExp('^[\\p{L}\\p{Nd} _.+/()_-]+$', 'u');
const DISPLAY_NAME_HAS_LETTER_OR_NUMBER = /[\p{L}\p{Nd}]/u;

type ManagedVariant = CataloguedVariantClientDocument & {
    author?: string;
    archived?: boolean;
    enabled?: boolean;
    gameCount?: number;
    locked?: boolean;
    visibility?: VariantVisibility;
    hasPieceSet?: boolean;
    pieceSetRevision?: string;
    hasBoard?: boolean;
    boardRevision?: string;
};

type State = {
    loaded: boolean;
    saving: boolean;
    variants: ManagedVariant[];
    maxVariants: number | null;
    variantSlotsUsed: number;
    total: number;
    page: number;
    pages: number;
    prevPage: number | null;
    nextPage: number | null;
    filtersInitialized: boolean;
    filterQ: string;
    filterAuthor: string;
    filterSort: ManagementSort;
    editing: ManagedVariant | null;
    message: string;
    formMessage: string;
    formMessageTone: MessageTone;
    draftDisplayName: string;
    draftDescription: string;
    draftPieceNames: string;
    draftPieceSetDirectional: boolean;
    draftPieceFamilyOverride: string;
    draftBoardFamilyOverride: string;
    draftVisibility: VariantVisibility;
    draftIni: string;
    piecePreviewVariant: string;
    boardPreviewVariant: string;
};

const state: State = {
    loaded: false,
    saving: false,
    variants: [],
    maxVariants: null,
    variantSlotsUsed: 0,
    total: 0,
    page: 1,
    pages: 1,
    prevPage: null,
    nextPage: null,
    filtersInitialized: false,
    filterQ: '',
    filterAuthor: '',
    filterSort: 'updated',
    editing: null,
    message: '',
    formMessage: '',
    formMessageTone: 'neutral',
    draftDisplayName: '',
    draftDescription: '',
    draftPieceNames: '',
    draftPieceSetDirectional: false,
    draftPieceFamilyOverride: '',
    draftBoardFamilyOverride: '',
    draftVisibility: 'private',
    draftIni: '',
    piecePreviewVariant: '',
    boardPreviewVariant: '',
};

let rootVNode: VNode | Element | null = null;
let managementPopstateBound = false;

function bindManagementPopstate(model: PyChessModel): void {
    if (!model.admin || managementPopstateBound) return;
    managementPopstateBound = true;
    window.addEventListener('popstate', () => {
        initializeManagementFilters(model, true);
        state.loaded = false;
        state.editing = null;
        clearDraft();
        void loadMine(model);
        rerender(model);
    });
}

function rerender(model: PyChessModel): void {
    if (!rootVNode) return;
    rootVNode = patch(rootVNode, renderRoot(model));
}

function isSystemManagedVariant(variant: ManagedVariant | null | undefined): boolean {
    return !!variant?.system || variant?.source === 'fairy-stockfish-builtin';
}

function managementSort(value: string | null): ManagementSort {
    return value === 'played' || value === 'favorited' || value === 'newest' || value === 'name' ? value : 'updated';
}

function positivePage(value: string | null): number {
    const page = Number.parseInt(value ?? '1', 10);
    return Number.isFinite(page) && page > 0 ? page : 1;
}

function initializeManagementFilters(model: PyChessModel, force = false): void {
    if (state.filtersInitialized && !force) return;

    const query = new URLSearchParams(window.location.search);
    state.page = positivePage(query.get('page'));
    if (model.admin) {
        state.filterQ = (query.get('q') ?? '').slice(0, 80);
        state.filterAuthor = query.has('author') ? (query.get('author') ?? '').slice(0, 40) : model.username;
        state.filterSort = managementSort(query.get('sort'));
    }
    state.filtersInitialized = true;
}

function managementLocationUrl(model: PyChessModel): string {
    const query = new URLSearchParams();
    if (model.admin) {
        const q = state.filterQ.trim();
        if (q) query.set('q', q);
        query.set('author', state.filterAuthor.trim());
        if (state.filterSort !== 'updated') query.set('sort', state.filterSort);
    }
    if (state.page > 1) query.set('page', String(state.page));
    const queryString = query.toString();
    return `${window.location.pathname}${queryString ? `?${queryString}` : ''}`;
}

function syncManagementLocation(model: PyChessModel, replace: boolean): void {
    if (!model.admin) return;
    const url = managementLocationUrl(model);
    if (replace) window.history.replaceState(null, '', url);
    else window.history.pushState(null, '', url);
}

function myVariantsUrl(model: PyChessModel): string {
    initializeManagementFilters(model);
    const query = new URLSearchParams();
    if (model.admin) {
        const q = state.filterQ.trim();
        if (q) query.set('q', q);
        query.set('author', state.filterAuthor.trim());
        if (state.filterSort !== 'updated') query.set('sort', state.filterSort);
    }
    if (state.page > 1) query.set('page', String(state.page));
    const queryString = query.toString();
    return `/api/catalogued-variants/mine${queryString ? `?${queryString}` : ''}`;
}

async function responseError(response: Response): Promise<string> {
    const text = await response.text();
    return text || `${_('Request failed')} (${response.status})`;
}

async function loadMine(model: PyChessModel, options: { clearMessage?: boolean } = {}): Promise<void> {
    try {
        const response = await fetch(myVariantsUrl(model));
        if (!response.ok) throw new Error(await responseError(response));
        const payload = (await response.json()) as {
            variants: ManagedVariant[];
            maxVariants?: number | null;
            variantSlotsUsed?: number | null;
            total?: number;
            page?: number;
            pages?: number;
            prevPage?: number | null;
            nextPage?: number | null;
            q?: string;
            author?: string;
            sort?: ManagementSort;
        };
        state.variants = payload.variants || [];
        state.maxVariants = payload.maxVariants ?? null;
        state.variantSlotsUsed = payload.variantSlotsUsed ?? 0;
        state.total = payload.total ?? state.variants.length;
        state.page = payload.page ?? 1;
        state.pages = payload.pages ?? 1;
        state.prevPage = payload.prevPage ?? null;
        state.nextPage = payload.nextPage ?? null;
        if (model.admin) {
            state.filterQ = payload.q ?? state.filterQ;
            state.filterAuthor = payload.author ?? state.filterAuthor;
            state.filterSort = managementSort(payload.sort ?? state.filterSort);
            syncManagementLocation(model, true);
        }
        state.loaded = true;
        if (options.clearMessage !== false) state.message = '';
    } catch (err) {
        state.loaded = true;
        state.message = err instanceof Error ? err.message : _('Failed to load variants');
    }
    rerender(model);
}

type VariantFormBody = {
    displayName: string;
    description: string;
    pieceNames: string;
    pieceSetDirectional: boolean;
    pieceFamilyOverride: string;
    boardFamilyOverride: string;
    visibility: VariantVisibility;
    ini: string;
};

function isSitePieceFamilyOverride(pieceFamily: string): boolean {
    return (
        !!pieceFamily &&
        Object.prototype.hasOwnProperty.call(PIECE_FAMILIES, pieceFamily) &&
        !pieceFamily.startsWith('catalogued-')
    );
}

function cleanPieceFamilyOverrideDraft(pieceFamily: string | undefined | null): string {
    const cleaned = (pieceFamily ?? '').trim();
    return isSitePieceFamilyOverride(cleaned) ? cleaned : '';
}

function isSiteBoardFamilyOverride(boardFamily: string): boolean {
    return (
        !!boardFamily &&
        Object.prototype.hasOwnProperty.call(BOARD_FAMILIES, boardFamily) &&
        !boardFamily.startsWith('catalogued')
    );
}

function cleanBoardFamilyOverrideDraft(boardFamily: string | undefined | null): string {
    const cleaned = (boardFamily ?? '').trim();
    return isSiteBoardFamilyOverride(cleaned) ? cleaned : '';
}

function readForm(): VariantFormBody {
    return {
        displayName:
            (document.getElementById('catalogued-display-name') as HTMLInputElement | null)?.value ??
            state.draftDisplayName,
        description:
            (document.getElementById('catalogued-description') as HTMLTextAreaElement | null)?.value ??
            state.draftDescription,
        pieceNames:
            (document.getElementById('catalogued-piece-names') as HTMLTextAreaElement | null)?.value ??
            state.draftPieceNames,
        pieceSetDirectional:
            (document.getElementById('catalogued-piece-set-directional') as HTMLInputElement | null)?.checked ??
            state.draftPieceSetDirectional,
        pieceFamilyOverride: cleanPieceFamilyOverrideDraft(
            (document.getElementById('catalogued-piece-family-override') as HTMLSelectElement | null)?.value ??
                state.draftPieceFamilyOverride,
        ),
        boardFamilyOverride: cleanBoardFamilyOverrideDraft(
            (document.getElementById('catalogued-board-family-override') as HTMLSelectElement | null)?.value ??
                state.draftBoardFamilyOverride,
        ),
        visibility:
            ((document.getElementById('catalogued-visibility') as HTMLSelectElement | null)?.value as
                | VariantVisibility
                | undefined) ?? state.draftVisibility,
        ini: (document.getElementById('catalogued-ini') as HTMLTextAreaElement | null)?.value ?? state.draftIni,
    };
}

function normalizeDisplayName(displayName: string): string {
    const normalized = displayName
        .normalize('NFKC')
        .trim()
        .replace(/([ _-])[ _-]+/g, '$1');
    if (!normalized) return '';
    if (
        !DISPLAY_NAME_PATTERN.test(normalized) ||
        !DISPLAY_NAME_HAS_LETTER_OR_NUMBER.test(normalized) ||
        /^[ _-]|[ _-]$/.test(normalized) ||
        Array.from(normalized).length > MAX_DISPLAY_NAME_LENGTH
    ) {
        throw new Error(
            _(
                'Display names must be at most 50 characters, contain a letter or number, and use only letters, numbers, spaces, hyphens, underscores, periods, plus signs, slashes, and parentheses.',
            ),
        );
    }
    return normalized;
}

function clearDraft(): void {
    state.draftDisplayName = '';
    state.draftDescription = '';
    state.draftPieceNames = '';
    state.draftPieceSetDirectional = false;
    state.draftPieceFamilyOverride = '';
    state.draftBoardFamilyOverride = '';
    state.draftVisibility = 'private';
    state.draftIni = '';
    state.formMessage = '';
    state.formMessageTone = 'neutral';
}

function formatPieceNames(pieceNames: Readonly<Record<string, string>> | undefined): string {
    return Object.entries(pieceNames ?? {})
        .map(([piece, name]) => `${piece}:${name}`)
        .join(', ');
}

function setDraftFromVariant(variant: ManagedVariant): void {
    state.draftDisplayName = variant.displayName ?? '';
    state.draftDescription = variant.tooltip === 'Catalogued variant' ? '' : (variant.tooltip ?? '');
    state.draftPieceNames = formatPieceNames(variant.pieceNames);
    state.draftPieceSetDirectional = variant.pieceSetDirectional ?? false;
    state.draftPieceFamilyOverride = cleanPieceFamilyOverrideDraft(variant.pieceFamilyOverride);
    state.draftBoardFamilyOverride = cleanBoardFamilyOverrideDraft(variant.boardFamilyOverride);
    state.draftVisibility = variant.visibility ?? 'private';
    state.draftIni = variant.ini ?? '';
}

function registerFromPayload(payload: { oldName?: string; variant?: ManagedVariant }): void {
    if (payload.oldName && payload.variant?.name && payload.oldName !== payload.variant.name) {
        unregisterCataloguedVariant(payload.oldName);
    }
    if (!payload.variant) return;
    if (payload.variant.enabled !== false && payload.variant.archived !== true) {
        registerCataloguedVariant(payload.variant);
    } else {
        unregisterCataloguedVariant(payload.variant.name);
    }
}

const SECTION_RE = /^\s*\[\s*([A-Za-z0-9_-]+)(?::[^\]]+)?\s*\]\s*$/gm;
function extractVariantName(ini: string): string {
    const sections = [...ini.matchAll(SECTION_RE)].map(match => match[1]);
    if (sections.length !== 1) throw new Error(_('The INI must contain exactly one variant section.'));
    const name = sections[0];
    if (!/^[a-z][a-z0-9_-]{2,31}$/.test(name)) {
        throw new Error(
            _(
                'Variant names must be 3-32 chars, start with a lowercase letter, and contain only lowercase letters, digits, hyphens, and underscores.',
            ),
        );
    }
    return name;
}

function validateVariantNameAvailable(name: string, editingName?: string): void {
    if (isBuiltinVariantName(name)) {
        throw new Error(_('This variant name conflicts with an existing site variant.'));
    }
    if (editingName && name === editingName) return;
    if (Object.prototype.hasOwnProperty.call(VARIANTS, name)) {
        throw new Error(_('A variant with this name already exists.'));
    }
}

function validateBasicIni(ini: string, editingName?: string): string {
    const name = extractVariantName(ini);
    validateVariantNameAvailable(name, editingName);

    const previousIni = state.editing?.ini ?? '';
    const rulesChanged = !!editingName && ini.trim() !== previousIni.trim();
    if (rulesChanged && name === editingName) {
        throw new Error(
            _(
                'Changing rules requires a new variant section name, because Fairy-Stockfish cannot replace an already loaded runtime variant.',
            ),
        );
    }
    return name;
}

async function checkRulesStrictly(ini: string): Promise<void> {
    await checkRulesWithFsfWasm(ini);
}

async function checkRulesOnServer(ini: string, currentName?: string | null): Promise<void> {
    const response = await fetch('/api/catalogued-variants/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ini, currentName }),
    });
    if (!response.ok) throw new Error(await responseError(response));
}

function currentRulesChanged(ini: string): boolean {
    if (!state.editing) return true;
    return ini.trim() !== (state.editing.ini ?? '').trim();
}

async function validateCurrentForm(model: PyChessModel): Promise<void> {
    if (isSystemManagedVariant(state.editing)) {
        state.formMessage = _('Fairy-Stockfish built-in catalogue entries do not have editable INI rules.');
        state.formMessageTone = 'neutral';
        rerender(model);
        return;
    }

    const body = readForm();
    if (!body.ini.trim()) {
        await alertDialog({ text: _('Paste one Fairy-Stockfish variant definition first.') });
        return;
    }

    const currentName = state.editing?.name;
    try {
        const name = validateBasicIni(body.ini.trim(), currentName);
        state.saving = true;
        if (!currentRulesChanged(body.ini)) {
            state.formMessage = _('These rules are unchanged and already passed validation.');
            state.formMessageTone = 'success';
            return;
        }
        state.formMessage = `${_('Checking rules for')} ${name}...`;
        state.formMessageTone = 'neutral';
        rerender(model);
        await checkRulesStrictly(body.ini.trim());
        await checkRulesOnServer(body.ini, currentName);
        state.formMessage = `${_('Fairy-Stockfish check passed for')} ${name}.`;
        state.formMessageTone = 'success';
    } catch (err) {
        state.formMessage = err instanceof Error ? err.message : _('Variant check failed');
        state.formMessageTone = 'error';
    } finally {
        state.saving = false;
        rerender(model);
    }
}

async function saveVariant(model: PyChessModel): Promise<void> {
    const body = readForm();
    try {
        body.displayName = normalizeDisplayName(body.displayName);
        state.draftDisplayName = body.displayName;
    } catch (err) {
        state.formMessage = err instanceof Error ? err.message : _('Invalid display name');
        state.formMessageTone = 'error';
        rerender(model);
        return;
    }
    const editingSystem = isSystemManagedVariant(state.editing);
    if (!editingSystem && !body.ini.trim()) {
        await alertDialog({ text: _('Paste one Fairy-Stockfish variant definition first.') });
        return;
    }

    const editingName = state.editing?.name;
    if (!editingSystem) {
        try {
            validateBasicIni(body.ini.trim(), editingName);
        } catch (err) {
            state.formMessage = err instanceof Error ? err.message : _('Variant check failed');
            state.formMessageTone = 'error';
            rerender(model);
            return;
        }
    }

    const rulesChanged = !editingSystem && currentRulesChanged(body.ini);
    state.saving = true;
    state.formMessage = editingSystem
        ? _('Saving metadata and visibility...')
        : rulesChanged
          ? `${_('Checking rules for')} ${extractVariantName(body.ini.trim())}...`
          : _('Saving metadata and visibility...');
    state.formMessageTone = 'neutral';
    rerender(model);

    const url = editingName
        ? `/api/catalogued-variants/${encodeURIComponent(editingName)}`
        : '/api/catalogued-variants';
    try {
        if (rulesChanged) await checkRulesStrictly(body.ini.trim());
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(
                editingSystem
                    ? {
                          displayName: body.displayName,
                          description: body.description,
                          pieceNames: body.pieceNames,
                          pieceSetDirectional: body.pieceSetDirectional,
                          pieceFamilyOverride: body.pieceFamilyOverride,
                          boardFamilyOverride: body.boardFamilyOverride,
                          visibility: body.visibility,
                      }
                    : body,
            ),
        });
        if (!response.ok) throw new Error(await responseError(response));
        const payload = (await response.json()) as { oldName?: string; variant?: ManagedVariant };
        registerFromPayload(payload);
        state.editing = null;
        clearDraft();
        state.formMessage = editingName ? _('Variant updated.') : _('Variant uploaded.');
        state.formMessageTone = 'success';
        await loadMine(model);
    } catch (err) {
        state.formMessage = err instanceof Error ? err.message : _('Failed to save variant');
        state.formMessageTone = 'error';
    } finally {
        state.saving = false;
        rerender(model);
    }
}

async function postAction(
    model: PyChessModel,
    variant: ManagedVariant,
    action: 'delete' | 'archive' | 'restore' | 'clone',
): Promise<void> {
    const labels = {
        delete: _('delete'),
        archive: _('archive'),
        restore: _('restore'),
        clone: _('clone'),
    };
    if (action === 'delete' || action === 'archive') {
        const confirmed = await confirmDialog({
            text: `${labels[action]} ${variant.displayName}?`,
            confirmText: action === 'delete' ? _('Delete') : _('Archive'),
            cancelText: _('Cancel'),
            danger: true,
        });
        if (!confirmed) return;
    }

    state.saving = true;
    rerender(model);
    try {
        const response = await fetch(`/api/catalogued-variants/${encodeURIComponent(variant.name)}/${action}`, {
            method: 'POST',
        });
        if (!response.ok) throw new Error(await responseError(response));
        const payload = (await response.json()) as { deleted?: string; archived?: string; variant?: ManagedVariant };
        if (payload.deleted) {
            unregisterCataloguedVariant(payload.deleted);
            removeCataloguedBoardCSS(payload.deleted);
        }
        if (payload.archived) unregisterCataloguedVariant(payload.archived);
        registerFromPayload(payload);
        state.message = _('Done.');
        await loadMine(model, { clearMessage: false });
    } catch (err) {
        state.message = err instanceof Error ? err.message : _('Action failed');
    } finally {
        state.saving = false;
        rerender(model);
    }
}

function cataloguedCustomPieceCss(variant: ManagedVariant): string {
    return variant.pieceSetRevision ? `custom-${variant.pieceSetRevision}` : 'custom';
}

function ensureCataloguedCustomPieceCSS(model: PyChessModel, variant: ManagedVariant): void {
    ensurePieceCSS(model.assetURL, `catalogued-${variant.name}`, cataloguedCustomPieceCss(variant));
}

function ensureCataloguedCustomBoardCSS(variant: ManagedVariant): void {
    ensureCataloguedBoardCSS(variant.name, variant.boardRevision);
}

function expectedPieceSetFiles(variant: ManagedVariant): string[] {
    const pieces = [
        ...new Set((variant.pieces?.length ? variant.pieces : ['k']).map(piece => piece.toLowerCase())),
    ].sort();
    const promoted =
        variant.promotionType === 'shogi'
            ? [...new Set((variant.promotionRoles ?? []).map(piece => piece.toLowerCase()))].sort()
            : [];
    const names: string[] = [];
    for (const color of ['w', 'b']) {
        for (const piece of pieces) names.push(`${color}${piece.toUpperCase()}.svg`);
        for (const piece of promoted) names.push(`${color}+${piece.toUpperCase()}.svg`);
    }
    return names;
}

function expectedSingleColorPieceSetFiles(variant: ManagedVariant, color: 'w' | 'b'): string[] {
    return expectedPieceSetFiles(variant).filter(filename => filename.startsWith(color));
}

async function uploadPieceSet(model: PyChessModel, variant: ManagedVariant, files: FileList | null): Promise<void> {
    if (!files || files.length === 0) return;
    const expected = expectedPieceSetFiles(variant);
    const singleColorCount = expectedSingleColorPieceSetFiles(variant, 'w').length;
    const validCount =
        files.length === expected.length || (variant.directionalPieceSet && files.length === singleColorCount);
    if (!validCount) {
        const expectedDescription = variant.directionalPieceSet
            ? `${singleColorCount} ${_('all-white or all-black files')}, ${_('or')} ${expected.length} ${_('paired files')}`
            : expected.join(', ');
        await alertDialog({
            text: `${_('Custom piece sets must be complete. Expected files')}: ${expectedDescription}`,
        });
        return;
    }

    const form = new FormData();
    for (const file of Array.from(files)) form.append('pieces', file, file.name);

    state.saving = true;
    rerender(model);
    try {
        const response = await fetch(`/api/catalogued-variants/${encodeURIComponent(variant.name)}/piece-set`, {
            method: 'POST',
            body: form,
        });
        if (!response.ok) throw new Error(await responseError(response));
        const payload = (await response.json()) as { variant?: ManagedVariant };
        registerFromPayload(payload);
        if (payload.variant?.hasPieceSet) {
            ensureCataloguedCustomPieceCSS(model, payload.variant);
            state.piecePreviewVariant = payload.variant.name;
        }
        state.message = _('Custom piece set uploaded.');
        await loadMine(model, { clearMessage: false });
    } catch (err) {
        const message = err instanceof Error ? err.message : _('Failed to upload piece set');
        state.message = message;
        await alertDialog({ text: message });
    } finally {
        state.saving = false;
        rerender(model);
    }
}

async function deletePieceSet(model: PyChessModel, variant: ManagedVariant): Promise<void> {
    if (!variant.hasPieceSet) return;
    const confirmed = await confirmDialog({
        text: `${_('delete')} ${_('custom piece set')}?`,
        confirmText: _('Delete'),
        cancelText: _('Cancel'),
        danger: true,
    });
    if (!confirmed) return;
    state.saving = true;
    rerender(model);
    try {
        const response = await fetch(`/api/catalogued-variants/${encodeURIComponent(variant.name)}/piece-set/delete`, {
            method: 'POST',
        });
        if (!response.ok) throw new Error(await responseError(response));
        const payload = (await response.json()) as { variant?: ManagedVariant };
        registerFromPayload(payload);
        if (state.piecePreviewVariant === variant.name) state.piecePreviewVariant = '';
        state.message = _('Custom piece set deleted.');
        await loadMine(model, { clearMessage: false });
    } catch (err) {
        state.message = err instanceof Error ? err.message : _('Failed to delete piece set');
    } finally {
        state.saving = false;
        rerender(model);
    }
}

async function uploadBoard(model: PyChessModel, variant: ManagedVariant, files: FileList | null): Promise<void> {
    if (!files || files.length === 0) return;
    if (files.length !== 1) {
        await alertDialog({ text: _('Upload exactly one board SVG file.') });
        return;
    }

    const form = new FormData();
    form.append('board', files[0], files[0].name);

    state.saving = true;
    rerender(model);
    try {
        const response = await fetch(`/api/catalogued-variants/${encodeURIComponent(variant.name)}/board`, {
            method: 'POST',
            body: form,
        });
        if (!response.ok) throw new Error(await responseError(response));
        const payload = (await response.json()) as { variant?: ManagedVariant };
        registerFromPayload(payload);
        if (payload.variant?.hasBoard) {
            ensureCataloguedCustomBoardCSS(payload.variant);
            state.boardPreviewVariant = payload.variant.name;
        }
        state.message = _('Custom board uploaded.');
        await loadMine(model, { clearMessage: false });
    } catch (err) {
        const message = err instanceof Error ? err.message : _('Failed to upload board');
        state.message = message;
        await alertDialog({ text: message });
    } finally {
        state.saving = false;
        rerender(model);
    }
}

async function deleteBoard(model: PyChessModel, variant: ManagedVariant): Promise<void> {
    if (!variant.hasBoard) return;
    const confirmed = await confirmDialog({
        text: `${_('delete')} ${_('custom board')}?`,
        confirmText: _('Delete'),
        cancelText: _('Cancel'),
        danger: true,
    });
    if (!confirmed) return;
    state.saving = true;
    rerender(model);
    try {
        const response = await fetch(`/api/catalogued-variants/${encodeURIComponent(variant.name)}/board/delete`, {
            method: 'POST',
        });
        if (!response.ok) throw new Error(await responseError(response));
        const payload = (await response.json()) as { variant?: ManagedVariant };
        registerFromPayload(payload);
        removeCataloguedBoardCSS(variant.name);
        if (state.boardPreviewVariant === variant.name) state.boardPreviewVariant = '';
        state.message = _('Custom board deleted.');
        await loadMine(model, { clearMessage: false });
    } catch (err) {
        state.message = err instanceof Error ? err.message : _('Failed to delete board');
    } finally {
        state.saving = false;
        rerender(model);
    }
}

function playVariant(model: PyChessModel, variant: ManagedVariant): void {
    if (variant.archived || variant.enabled === false || variant.replayOnly) return;
    localStorage.seek_variant = variant.name;
    window.location.assign(`${model.home}/?any&variant=${encodeURIComponent(variant.name)}`);
}

function playVariantWithAI(model: PyChessModel, variant: ManagedVariant): void {
    if (variant.archived || variant.enabled === false || variant.replayOnly) return;
    localStorage.seek_variant = variant.name;
    window.location.assign(`${model.home}/?ai&variant=${encodeURIComponent(variant.name)}`);
}

function openAnalysisBoard(model: PyChessModel, variant: ManagedVariant): void {
    if (variant.archived || variant.enabled === false || variant.replayOnly) return;
    window.location.assign(`${model.home}/analysis/${encodeURIComponent(variant.name)}`);
}

function openRulesPage(model: PyChessModel, variant: ManagedVariant): void {
    if (variant.archived || variant.enabled === false) return;
    window.location.assign(`${model.home}/variants/${encodeURIComponent(variant.name)}`);
}

function editVariant(model: PyChessModel, variant: ManagedVariant): void {
    state.editing = variant;
    setDraftFromVariant(variant);
    state.formMessage = '';
    state.formMessageTone = 'neutral';
    rerender(model);
    setTimeout(
        () =>
            document.getElementById('catalogued-display-name')?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
        0,
    );
}

function cancelEdit(model: PyChessModel): void {
    state.editing = null;
    clearDraft();
    rerender(model);
}

function visibilityLabel(visibility: VariantVisibility | undefined): string {
    switch (visibility) {
        case 'public':
            return _('Public');
        case 'unlisted':
            return _('Unlisted');
        default:
            return _('Private');
    }
}

function visibilityHelp(visibility: VariantVisibility): string {
    switch (visibility) {
        case 'public':
            return _('Public variants appear on the Community variants page and their games are saved.');
        case 'unlisted':
            return _('Unlisted variants stay out of search; their games are not saved.');
        default:
            return _('Private variants are visible only to you and site admins; their games are not saved.');
    }
}

function sitePieceFamilyOptions(): string[] {
    return Object.keys(PIECE_FAMILIES).filter(isSitePieceFamilyOverride);
}

function pieceFamilyOverrideLabel(pieceFamily: string): string {
    return pieceFamily === 'letter' ? _('Letters') : pieceFamily;
}

function siteBoardFamilyOptions(): string[] {
    const dimensions = state.editing ? { width: state.editing.width, height: state.editing.height } : undefined;
    return Object.keys(BOARD_FAMILIES)
        .filter(isSiteBoardFamilyOverride)
        .filter(family => {
            if (!dimensions) return true;
            const boardDimensions = BOARD_FAMILIES[family].dimensions;
            return boardDimensions.width === dimensions.width && boardDimensions.height === dimensions.height;
        });
}

function boardFamilyOverrideLabel(boardFamily: string): string {
    const dimensions = BOARD_FAMILIES[boardFamily].dimensions;
    return `${boardFamily} (${dimensions.width}×${dimensions.height})`;
}

function renderForm(model: PyChessModel): VNode {
    const editing = state.editing;
    const editingSystem = isSystemManagedVariant(editing);
    return h('section.catalogued-card.catalogued-form', [
        h('div.catalogued-form-head', [
            h(
                'h2',
                editingSystem
                    ? _('Edit Fairy-Stockfish variant')
                    : editing
                      ? _('Edit variant')
                      : _('Upload new variant'),
            ),
            editingSystem
                ? h(
                      'p',
                      _(
                          'This entry is backed by a built-in Fairy-Stockfish variant. Its rules are not editable here, so NNUE files can keep matching the original engine variant name.',
                      ),
                  )
                : h(
                      'p',
                      _(
                          'Paste exactly one Fairy-Stockfish variant definition. Rules are locked after the first saved public game.',
                      ),
                  ),
            editingSystem
                ? null
                : h(
                      'p.catalogued-help',
                      _(
                          'For randomized Chess960 starts, use a name ending in 960, explicitly set chess960 = true, and use an 8×8 default position with standard chess back ranks and ordinary king/rook castling rules. Custom starting positions are kept as supplied.',
                      ),
                  ),
            editingSystem
                ? null
                : h(
                      'p.catalogued-help',
                      _('Private and unlisted variants are sandbox variants: games are playable but are not saved.'),
                  ),
            editingSystem
                ? null
                : h(
                      'p.catalogued-help',
                      _(
                          'If you change the rules of an unused variant, also change the INI section name, because Fairy-Stockfish cannot replace an already loaded runtime variant.',
                      ),
                  ),
            editingSystem
                ? h(
                      'p.catalogued-help',
                      _(
                          'Admins can edit metadata, visibility, compatible piece and board styles, piece SVGs, and board SVGs for this system-owned catalogue entry.',
                      ),
                  )
                : null,
            !editingSystem && editing?.locked
                ? h(
                      'p.catalogued-help',
                      _(
                          'This variant already has saved public games. Only metadata and visibility can be changed; clone it to change the rules.',
                      ),
                  )
                : null,
        ]),
        h(
            'form.catalogued-form-grid',
            {
                on: {
                    submit: (event: Event) => {
                        event.preventDefault();
                        void saveVariant(model);
                    },
                },
            },
            [
                h('label.catalogued-field.catalogued-field-half', [
                    h('span', _('Display name')),
                    h('input#catalogued-display-name', {
                        props: {
                            value: state.draftDisplayName,
                            placeholder: _('Display name'),
                            autocomplete: 'off',
                            disabled: state.saving,
                        },
                        attrs: {
                            title: _(
                                'Use letters, numbers, spaces, hyphens, underscores, periods, plus signs, slashes, and parentheses.',
                            ),
                        },
                        on: {
                            input: (event: Event) => {
                                state.draftDisplayName = (event.target as HTMLInputElement).value;
                                state.formMessage = '';
                                state.formMessageTone = 'neutral';
                            },
                        },
                    }),
                    h(
                        'span.catalogued-help',
                        _('Up to 50 characters. Repeated spaces, hyphens, and underscores are collapsed.'),
                    ),
                ]),
                h('label.catalogued-field.catalogued-field-half.catalogued-description-field', [
                    h('span', _('Short description')),
                    h('textarea#catalogued-description.catalogued-description-input', {
                        props: {
                            value: state.draftDescription,
                            placeholder: _('Short description'),
                            autocomplete: 'off',
                            disabled: state.saving,
                            rows: 3,
                        },
                        attrs: {
                            maxlength: '1000',
                        },
                        on: {
                            input: (event: Event) => {
                                state.draftDescription = (event.target as HTMLTextAreaElement).value;
                                state.formMessage = '';
                                state.formMessageTone = 'neutral';
                            },
                        },
                    }),
                ]),
                h('label.catalogued-field.catalogued-field-full', [
                    h('span', _('Piece names (optional)')),
                    h('textarea#catalogued-piece-names', {
                        props: {
                            value: state.draftPieceNames,
                            placeholder: 'p:Soldier, z:Zebra, c:Camel',
                            autocomplete: 'off',
                            disabled: state.saving,
                            rows: 2,
                        },
                        attrs: {
                            maxlength: '2048',
                        },
                        on: {
                            input: (event: Event) => {
                                state.draftPieceNames = (event.target as HTMLTextAreaElement).value;
                                state.formMessage = '';
                                state.formMessageTone = 'neutral';
                            },
                        },
                    }),
                    h(
                        'span.catalogued-help',
                        _(
                            'Comma-separated letter:name pairs used by generated rules, for example p:Soldier, z:Zebra. Built-in names can be overridden; missing names use automatic fallbacks.',
                        ),
                    ),
                ]),
                h('label.catalogued-field.catalogued-field-half.catalogued-checkbox-field', [
                    h('span.catalogued-checkbox-row', [
                        h('span', _('Directional custom pieces')),
                        h('input#catalogued-piece-set-directional', {
                            props: {
                                type: 'checkbox',
                                checked: state.draftPieceSetDirectional,
                                disabled: state.saving,
                            },
                            attrs: {
                                'aria-describedby': 'catalogued-piece-set-directional-help',
                            },
                            on: {
                                change: (event: Event) => {
                                    state.draftPieceSetDirectional = (event.target as HTMLInputElement).checked;
                                    state.formMessage = '';
                                    state.formMessageTone = 'neutral';
                                },
                            },
                        }),
                    ]),
                    h(
                        'span#catalogued-piece-set-directional-help.catalogued-help',
                        _(
                            'Enable for standalone variants whose piece direction shows ownership. One complete white or black SVG set can then serve both players. Shogi-derived variants are detected automatically.',
                        ),
                    ),
                ]),
                h('label.catalogued-field.catalogued-field-half', [
                    h('span', _('Visibility')),
                    h(
                        'select#catalogued-visibility',
                        {
                            props: {
                                value: state.draftVisibility,
                                disabled: state.saving,
                            },
                            on: {
                                change: (event: Event) => {
                                    state.draftVisibility = (event.target as HTMLSelectElement)
                                        .value as VariantVisibility;
                                    state.formMessage = '';
                                    state.formMessageTone = 'neutral';
                                    rerender(model);
                                },
                            },
                        },
                        [
                            h(
                                'option',
                                { props: { value: 'private', selected: state.draftVisibility === 'private' } },
                                _('Private'),
                            ),
                            h(
                                'option',
                                { props: { value: 'unlisted', selected: state.draftVisibility === 'unlisted' } },
                                _('Unlisted'),
                            ),
                            h(
                                'option',
                                { props: { value: 'public', selected: state.draftVisibility === 'public' } },
                                _('Public'),
                            ),
                        ],
                    ),
                    h('span.catalogued-help', visibilityHelp(state.draftVisibility)),
                ]),
                h('fieldset.catalogued-appearance-fields.catalogued-field-full', [
                    h('legend', _('Advanced appearance')),
                    h('label.catalogued-field', [
                        h('span', _('Compatible piece set')),
                        h(
                            'select#catalogued-piece-family-override',
                            {
                                props: {
                                    value: state.draftPieceFamilyOverride,
                                    disabled: state.saving,
                                },
                                on: {
                                    change: (event: Event) => {
                                        state.draftPieceFamilyOverride = (event.target as HTMLSelectElement).value;
                                        state.formMessage = '';
                                        state.formMessageTone = 'neutral';
                                        rerender(model);
                                    },
                                },
                            },
                            [
                                h(
                                    'option',
                                    {
                                        props: {
                                            value: '',
                                            selected: state.draftPieceFamilyOverride === '',
                                        },
                                    },
                                    _('Auto-detect'),
                                ),
                                ...sitePieceFamilyOptions().map(family =>
                                    h(
                                        'option',
                                        {
                                            props: {
                                                value: family,
                                                selected: state.draftPieceFamilyOverride === family,
                                            },
                                        },
                                        pieceFamilyOverrideLabel(family),
                                    ),
                                ),
                            ],
                        ),
                        h(
                            'span.catalogued-help',
                            _(
                                'Overrides automatic built-in piece-set detection; custom SVG piece sets still take precedence.',
                            ),
                        ),
                    ]),
                    h('label.catalogued-field', [
                        h('span', _('Compatible board style')),
                        h(
                            'select#catalogued-board-family-override',
                            {
                                props: {
                                    value: state.draftBoardFamilyOverride,
                                    disabled: state.saving,
                                },
                                on: {
                                    change: (event: Event) => {
                                        state.draftBoardFamilyOverride = (event.target as HTMLSelectElement).value;
                                        state.formMessage = '';
                                        state.formMessageTone = 'neutral';
                                        rerender(model);
                                    },
                                },
                            },
                            [
                                h(
                                    'option',
                                    {
                                        props: {
                                            value: '',
                                            selected: state.draftBoardFamilyOverride === '',
                                        },
                                    },
                                    _('Auto-detect'),
                                ),
                                ...siteBoardFamilyOptions().map(family =>
                                    h(
                                        'option',
                                        {
                                            props: {
                                                value: family,
                                                selected: state.draftBoardFamilyOverride === family,
                                            },
                                        },
                                        boardFamilyOverrideLabel(family),
                                    ),
                                ),
                            ],
                        ),
                        h(
                            'span.catalogued-help',
                            _(
                                'Overrides automatic compatible board detection; an uploaded custom board SVG still takes precedence.',
                            ),
                        ),
                    ]),
                ]),
                h('label.catalogued-field.catalogued-field-full', [
                    h('span', _('Variant definition')),
                    h('textarea#catalogued-ini', {
                        props: {
                            value: state.draftIni,
                            placeholder: editingSystem
                                ? _('Built-in Fairy-Stockfish variant; no INI is stored.')
                                : '[myvariant:chess]\n# inherits chess rules through the section suffix',
                            spellcheck: false,
                            disabled: state.saving || editingSystem,
                        },
                        on: {
                            input: (event: Event) => {
                                state.draftIni = (event.target as HTMLTextAreaElement).value;
                                state.formMessage = '';
                                state.formMessageTone = 'neutral';
                            },
                        },
                    }),
                    editingSystem
                        ? null
                        : h('span.catalogued-help', [
                              h(
                                  'a.catalogued-reference-link',
                                  {
                                      attrs: {
                                          href: 'https://github.com/fairy-stockfish/Fairy-Stockfish/blob/master/src/variants.ini',
                                          target: '_blank',
                                          rel: 'noopener',
                                      },
                                  },
                                  _('Fairy-Stockfish variants.ini reference'),
                              ),
                          ]),
                    editingSystem
                        ? h(
                              'span.catalogued-help',
                              _(
                                  'The catalogue key remains the Fairy-Stockfish UCI_Variant name. Use display name and description for nicer wording.',
                              ),
                          )
                        : h(
                              'span.catalogued-help',
                              _(
                                  'If inherited rules use pieces or promoted pieces that pychess cannot detect automatically, add a comment like # pychessPieces = k,q,r,+r,p,+p. This affects only piece-set upload and board rendering; Fairy-Stockfish ignores it. For locked variants with games, only this pychessPieces metadata can be changed.',
                              ),
                          ),
                ]),
                h('div.catalogued-actions.catalogued-field-full', [
                    h(
                        `button.button-primary.catalogued-primary-action${state.saving ? '.disabled' : ''}`,
                        {
                            props: { type: 'submit', disabled: state.saving },
                        },
                        editing ? _('Save changes') : _('Upload variant'),
                    ),
                    h(
                        'button.catalogued-secondary-action',
                        {
                            props: { type: 'button', disabled: state.saving || editingSystem },
                            on: {
                                click: (event: Event) => {
                                    event.preventDefault();
                                    event.stopPropagation();
                                    void validateCurrentForm(model);
                                },
                            },
                        },
                        _('Check rules'),
                    ),
                    editing
                        ? h(
                              'button.catalogued-secondary-action',
                              {
                                  props: { type: 'button', disabled: state.saving },
                                  on: { click: () => cancelEdit(model) },
                              },
                              _('Cancel'),
                          )
                        : null,
                ]),
                state.formMessage
                    ? h(
                          `p.catalogued-message.catalogued-field-full.${state.formMessageTone}`,
                          { attrs: { 'aria-live': 'polite' } },
                          state.formMessage,
                      )
                    : null,
            ],
        ),
    ]);
}

function pieceSetPreviewRoleClass(filename: string): string {
    const promoted = filename[1] === '+';
    const letter = filename[promoted ? 2 : 1]?.toLowerCase() || 'k';
    return promoted ? `p${letter}-piece` : `${letter}-piece`;
}

function pieceSetPreviewColorClass(filename: string): 'white' | 'black' {
    return filename[0] === 'b' ? 'black' : 'white';
}

function renderPieceSetPreview(model: PyChessModel, variant: ManagedVariant): VNode | null {
    if (!variant.hasPieceSet || state.piecePreviewVariant !== variant.name) return null;
    ensureCataloguedCustomPieceCSS(model, variant);
    const styleClass = `piece-style-catalogued-${variant.name}-custom`;
    return h('div.catalogued-piece-preview', [
        h('div.catalogued-piece-preview-head', [
            h('strong', _('Piece set preview')),
            h(
                'button.catalogued-row-button.catalogued-secondary-action',
                {
                    props: { type: 'button' },
                    on: {
                        click: () => {
                            state.piecePreviewVariant = '';
                            rerender(model);
                        },
                    },
                },
                _('Close'),
            ),
        ]),
        h(
            'div.catalogued-piece-preview-grid',
            { class: { [styleClass]: true } },
            expectedPieceSetFiles(variant).map(filename =>
                h('div.catalogued-piece-preview-cell', [
                    h('piece', {
                        class: {
                            [pieceSetPreviewRoleClass(filename)]: true,
                            [pieceSetPreviewColorClass(filename)]: true,
                            ally: pieceSetPreviewColorClass(filename) === 'white',
                            enemy: pieceSetPreviewColorClass(filename) === 'black',
                        },
                    }),
                    h('span', filename),
                ]),
            ),
        ),
    ]);
}

function renderCompatiblePieceSetInfo(variant: ManagedVariant): VNode | null {
    const family = cataloguedCompatiblePieceFamily(variant, { ignoreCustomPieceSet: true });
    if (!family || family === 'letter') return null;

    const styleCount = PIECE_FAMILIES[family]?.pieceCSS.length ?? 0;
    const styleText = styleCount > 0 ? `${styleCount} ${_('built-in piece styles')}` : _('built-in piece styles');

    if (variant.hasPieceSet) {
        return h(
            'span.catalogued-help.catalogued-piece-compat',
            `${_('Also compatible with')} ${family} (${styleText}). ${_('Delete the custom set to use those built-in styles again.')}`,
        );
    }

    return h(
        'span.catalogued-help.catalogued-piece-compat',
        `${_('Compatible with')} ${family} (${styleText}). ${_('Upload a custom set only if you want to replace these styles.')}`,
    );
}

function renderPieceSetControls(model: PyChessModel, variant: ManagedVariant): VNode {
    const expected = expectedPieceSetFiles(variant);
    const whiteFiles = expectedSingleColorPieceSetFiles(variant, 'w');
    const blackFiles = expectedSingleColorPieceSetFiles(variant, 'b');
    const requiredFilesText = variant.directionalPieceSet
        ? `${whiteFiles.length} ${_('one-color')} ${_('or')} ${expected.length} ${_('paired')}`
        : `${expected.length}`;
    const requiredFilesTitle = variant.directionalPieceSet
        ? `${_('One-color set')}: ${whiteFiles.join(', ')} ${_('or')} ${blackFiles.join(', ')}. ${_('Paired set')}: ${expected.join(', ')}`
        : expected.join(', ');
    const compatibleFamily = cataloguedCompatiblePieceFamily(variant, { ignoreCustomPieceSet: true });
    const pieceStatus = variant.hasPieceSet
        ? _('Custom')
        : compatibleFamily && compatibleFamily !== 'letter'
          ? _('Built-in')
          : _('Letters');
    return h('div.catalogued-piece-set-controls', [
        h('strong', pieceStatus),
        renderCompatiblePieceSetInfo(variant),
        h(
            'span.catalogued-help',
            { attrs: { title: requiredFilesTitle } },
            `${_('Required SVG files')}: ${requiredFilesText}`,
        ),
        h('label.catalogued-row-button.catalogued-secondary-action.catalogued-file-action', [
            _('Upload set'),
            h('input', {
                props: {
                    type: 'file',
                    accept: '.svg,image/svg+xml',
                    multiple: true,
                    disabled: state.saving || !!variant.archived || variant.enabled === false,
                },
                on: {
                    change: (event: Event) => {
                        const input = event.target as HTMLInputElement;
                        void uploadPieceSet(model, variant, input.files);
                        input.value = '';
                    },
                },
            }),
        ]),
        variant.hasPieceSet
            ? h(
                  'button.catalogued-row-button.catalogued-secondary-action',
                  {
                      props: { type: 'button', disabled: state.saving },
                      on: {
                          click: () => {
                              if (state.piecePreviewVariant === variant.name) state.piecePreviewVariant = '';
                              else {
                                  ensureCataloguedCustomPieceCSS(model, variant);
                                  state.piecePreviewVariant = variant.name;
                              }
                              rerender(model);
                          },
                      },
                  },
                  state.piecePreviewVariant === variant.name ? _('Hide preview') : _('Preview'),
              )
            : null,
        variant.hasPieceSet
            ? h(
                  'button.catalogued-row-button.catalogued-secondary-action',
                  {
                      props: { type: 'button', disabled: state.saving },
                      on: { click: () => void deletePieceSet(model, variant) },
                  },
                  _('Delete set'),
              )
            : null,
        renderPieceSetPreview(model, variant),
    ]);
}

function renderBoardPreview(model: PyChessModel, variant: ManagedVariant): VNode | null {
    if (!variant.hasBoard || state.boardPreviewVariant !== variant.name) return null;
    ensureCataloguedCustomBoardCSS(variant);
    return h('div.catalogued-board-preview', [
        h('div.catalogued-piece-preview-head', [
            h('strong', _('Board preview')),
            h(
                'button.catalogued-row-button.catalogued-secondary-action',
                {
                    props: { type: 'button' },
                    on: {
                        click: () => {
                            state.boardPreviewVariant = '';
                            rerender(model);
                        },
                    },
                },
                _('Close'),
            ),
        ]),
        h('div.catalogued-board-preview-surface', {
            attrs: { 'data-board-variant': variant.name },
            style: { aspectRatio: `${variant.width} / ${variant.height}` },
        }),
    ]);
}

function renderBoardControls(model: PyChessModel, variant: ManagedVariant): VNode {
    const compatibleFamily = cataloguedCompatibleBoardFamily(variant);
    const boardStatus = variant.hasBoard ? _('Custom') : compatibleFamily ? _('Built-in') : _('Default');
    const boardHelp = variant.hasBoard
        ? compatibleFamily
            ? `${_('This variant uses its uploaded board SVG.')} ${_('Delete it to use')} ${compatibleFamily}.`
            : _('This variant uses its uploaded board SVG.')
        : compatibleFamily
          ? `${_('Compatible board style')}: ${compatibleFamily}.`
          : _('Default generated checkerboard. Upload an SVG board if the variant needs special regions.');
    return h('div.catalogued-board-controls', [
        h('strong', boardStatus),
        h('span.catalogued-help', boardHelp),
        h('label.catalogued-row-button.catalogued-secondary-action.catalogued-file-action', [
            _('Upload board'),
            h('input', {
                props: {
                    type: 'file',
                    accept: '.svg,image/svg+xml',
                    multiple: false,
                    disabled: state.saving || !!variant.archived || variant.enabled === false,
                },
                on: {
                    change: (event: Event) => {
                        const input = event.target as HTMLInputElement;
                        void uploadBoard(model, variant, input.files);
                        input.value = '';
                    },
                },
            }),
        ]),
        variant.hasBoard
            ? h(
                  'button.catalogued-row-button.catalogued-secondary-action',
                  {
                      props: { type: 'button', disabled: state.saving },
                      on: {
                          click: () => {
                              if (state.boardPreviewVariant === variant.name) state.boardPreviewVariant = '';
                              else {
                                  ensureCataloguedCustomBoardCSS(variant);
                                  state.boardPreviewVariant = variant.name;
                              }
                              rerender(model);
                          },
                      },
                  },
                  state.boardPreviewVariant === variant.name ? _('Hide preview') : _('Preview'),
              )
            : null,
        variant.hasBoard
            ? h(
                  'button.catalogued-row-button.catalogued-secondary-action',
                  {
                      props: { type: 'button', disabled: state.saving },
                      on: { click: () => void deleteBoard(model, variant) },
                  },
                  _('Delete board'),
              )
            : null,
        renderBoardPreview(model, variant),
    ]);
}

function renderAdminFilters(model: PyChessModel): VNode | null {
    if (!model.admin) return null;

    const submit = (event: Event): void => {
        event.preventDefault();
        if (state.saving) return;
        state.page = 1;
        state.loaded = false;
        state.editing = null;
        clearDraft();
        syncManagementLocation(model, false);
        void loadMine(model);
        rerender(model);
    };

    return h('form.community-variants-search.catalogued-management-search', { on: { submit } }, [
        h('label', [
            _('Search'),
            h('input', {
                props: { type: 'search', value: state.filterQ, placeholder: _('Name, description, or uploader') },
                on: { input: event => (state.filterQ = (event.target as HTMLInputElement).value) },
            }),
        ]),
        h('label', [
            _('Uploaded by'),
            h('input', {
                props: { type: 'search', value: state.filterAuthor, placeholder: _('Exact username') },
                on: { input: event => (state.filterAuthor = (event.target as HTMLInputElement).value) },
            }),
        ]),
        h('label', [
            _('Sort'),
            h(
                'select',
                {
                    props: { value: state.filterSort },
                    on: {
                        change: event => (state.filterSort = managementSort((event.target as HTMLSelectElement).value)),
                    },
                },
                [
                    h('option', { props: { value: 'updated' } }, _('Recently updated')),
                    h('option', { props: { value: 'played' } }, _('Most played')),
                    h('option', { props: { value: 'favorited' } }, _('Most favorited')),
                    h('option', { props: { value: 'newest' } }, _('Newest')),
                    h('option', { props: { value: 'name' } }, _('Name')),
                ],
            ),
        ]),
        h(
            'button.button.catalogued-secondary-action',
            { props: { type: 'submit', disabled: state.saving } },
            _('Search'),
        ),
    ]);
}

function renderPagination(model: PyChessModel): VNode | null {
    if (!state.loaded || state.pages <= 1) return null;

    const changePage = (page: number | null): void => {
        if (page === null || page === state.page || state.saving) return;
        state.page = page;
        syncManagementLocation(model, false);
        state.loaded = false;
        state.editing = null;
        clearDraft();
        void loadMine(model);
        rerender(model);
    };

    return h('nav.catalogued-management-pages', [
        state.prevPage === null
            ? null
            : h(
                  'button.catalogued-row-button.catalogued-secondary-action',
                  {
                      props: { type: 'button', disabled: state.saving },
                      on: { click: () => changePage(state.prevPage) },
                  },
                  _('Previous'),
              ),
        h('span', `${_('Page')} ${state.page} / ${state.pages}`),
        state.nextPage === null
            ? null
            : h(
                  'button.catalogued-row-button.catalogued-secondary-action',
                  {
                      props: { type: 'button', disabled: state.saving },
                      on: { click: () => changePage(state.nextPage) },
                  },
                  _('Next'),
              ),
    ]);
}

function renderRows(model: PyChessModel): VNode {
    if (!state.loaded) return h('p', _('Loading...'));
    if (state.variants.length === 0)
        return h(
            'p.catalogued-empty',
            model.admin ? _('No variants found.') : _('You have not uploaded any variants yet.'),
        );

    return h('div.catalogued-table-wrap', [
        h('table.catalogued-table', [
            h(
                'thead',
                h('tr', [
                    h('th', _('Name')),
                    h('th', _('Status')),
                    h('th', _('Visibility')),
                    h('th', _('Games')),
                    h('th', _('Favorites')),
                    h('th', _('Pieces')),
                    h('th', _('Board')),
                    h('th', _('Actions')),
                ]),
            ),
            h(
                'tbody',
                state.variants.map(variant => {
                    const locked = !!variant.locked;
                    const archived = !!variant.archived || variant.enabled === false;
                    const playDisabled = archived || !!variant.replayOnly;
                    const systemManaged = isSystemManagedVariant(variant);
                    const lockTitle = locked
                        ? _('This variant already has saved public games. Clone it to change the rules.')
                        : '';
                    const systemTitle = systemManaged
                        ? _('Fairy-Stockfish built-in catalogue entries keep their engine rules and key fixed.')
                        : '';
                    const aiTitle = variant.aiDisabled
                        ? _(
                              'Fairy-Stockfish AI is temporarily disabled for this variant; Random-Mover can still be used.',
                          )
                        : '';
                    return h('tr', { class: { archived } }, [
                        h('td.catalogued-name-cell', { attrs: { 'data-label': _('Name') } }, [
                            h('strong', variant.displayName),
                            h('code', variant.name),
                            variant.tooltip ? h('p', variant.tooltip) : null,
                        ]),
                        h(
                            'td',
                            { attrs: { 'data-label': _('Status') } },
                            archived
                                ? _('Archived')
                                : variant.replayOnly
                                  ? _('Replay only')
                                  : systemManaged
                                    ? _('System')
                                    : locked
                                      ? _('Locked')
                                      : _('Editable'),
                        ),
                        h('td', { attrs: { 'data-label': _('Visibility') } }, visibilityLabel(variant.visibility)),
                        h('td', { attrs: { 'data-label': _('Games') } }, String(variant.gameCount ?? 0)),
                        h('td', { attrs: { 'data-label': _('Favorites') } }, String(variant.favoriteCount ?? 0)),
                        h('td', { attrs: { 'data-label': _('Pieces') } }, renderPieceSetControls(model, variant)),
                        h('td', { attrs: { 'data-label': _('Board') } }, renderBoardControls(model, variant)),
                        h('td.catalogued-row-actions', { attrs: { 'data-label': _('Actions') } }, [
                            h(
                                'button.button-primary.catalogued-row-button',
                                {
                                    props: { type: 'button', disabled: playDisabled },
                                    on: { click: () => playVariant(model, variant) },
                                },
                                _('Play'),
                            ),
                            h(
                                'button.catalogued-row-button.catalogued-secondary-action.catalogued-ai-action',
                                {
                                    props: { type: 'button', disabled: playDisabled },
                                    attrs: { title: aiTitle },
                                    on: { click: () => playVariantWithAI(model, variant) },
                                },
                                _('Play AI'),
                            ),
                            h(
                                'button.catalogued-row-button.catalogued-secondary-action.catalogued-analysis-action',
                                {
                                    props: { type: 'button', disabled: playDisabled },
                                    on: { click: () => openAnalysisBoard(model, variant) },
                                },
                                _('Analysis'),
                            ),
                            h(
                                'button.catalogued-row-button.catalogued-secondary-action',
                                {
                                    props: { type: 'button', disabled: archived },
                                    on: { click: () => openRulesPage(model, variant) },
                                },
                                _('Rules'),
                            ),
                            h(
                                'button.catalogued-row-button.catalogued-secondary-action',
                                {
                                    props: { type: 'button', disabled: state.saving },
                                    attrs: { title: systemTitle || lockTitle },
                                    on: { click: () => editVariant(model, variant) },
                                },
                                _('Edit'),
                            ),
                            h(
                                'button.catalogued-row-button.catalogued-secondary-action',
                                {
                                    props: { type: 'button', disabled: systemManaged || locked || state.saving },
                                    attrs: { title: systemTitle || lockTitle },
                                    on: { click: () => void postAction(model, variant, 'delete') },
                                },
                                _('Delete'),
                            ),
                            archived
                                ? h(
                                      'button.catalogued-row-button.catalogued-secondary-action',
                                      {
                                          props: { type: 'button', disabled: state.saving },
                                          on: { click: () => void postAction(model, variant, 'restore') },
                                      },
                                      _('Restore'),
                                  )
                                : h(
                                      'button.catalogued-row-button.catalogued-secondary-action',
                                      {
                                          props: { type: 'button', disabled: state.saving },
                                          on: { click: () => void postAction(model, variant, 'archive') },
                                      },
                                      _('Archive'),
                                  ),
                            h(
                                'button.catalogued-row-button.catalogued-secondary-action',
                                {
                                    props: { type: 'button', disabled: systemManaged || state.saving },
                                    attrs: { title: systemTitle },
                                    on: { click: () => void postAction(model, variant, 'clone') },
                                },
                                _('Clone'),
                            ),
                        ]),
                    ]);
                }),
            ),
        ]),
    ]);
}

function renderRoot(model: PyChessModel): VNode {
    initializeManagementFilters(model);
    const listTitle = model.admin ? _('Variants') : _('My variants');

    return h(
        'main#my-variants.my-variants',
        {
            hook: {
                insert: (vnode: VNode) => {
                    rootVNode = vnode;
                    bindManagementPopstate(model);
                    if (!state.loaded) void loadMine(model);
                },
            },
        },
        [
            h('section.catalogued-page-header', [
                h('h1', _('Manage my variants')),
                h(
                    'p',
                    _(
                        'Uploaded variants stay out of the regular variant catalog. They are always casual/unrated, but can be played from this page against humans or Fairy-Stockfish.',
                    ),
                ),
                h('p', [
                    h('a', { attrs: { href: `${model.home}/variants/community` } }, _('Browse community variants')),
                ]),
            ]),
            model.anon === 'True'
                ? h('section.catalogued-card', [
                      h('h2', _('Sign in required')),
                      h('p', _('Please sign in to upload and manage your variants.')),
                  ])
                : h('div.catalogued-layout', [
                      state.message ? h('p.catalogued-message', state.message) : null,
                      renderForm(model),
                      h('section.catalogued-card.catalogued-list-card', [
                          h('h2', listTitle),
                          renderAdminFilters(model),
                          state.maxVariants === null
                              ? h(
                                    'p.catalogued-help',
                                    `${state.total} ${state.total === 1 ? _('variant') : _('variants')}`,
                                )
                              : h(
                                    'p.catalogued-help',
                                    `${state.variantSlotsUsed}/${state.maxVariants} ${_('variant slots used')}`,
                                ),
                          renderRows(model),
                          renderPagination(model),
                      ]),
                  ]),
        ],
    );
}

export function myVariantsView(model: PyChessModel): VNode[] {
    return [renderRoot(model)];
}
