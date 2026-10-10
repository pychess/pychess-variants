import { h, VNode } from 'snabbdom';

import * as cg from 'chessgroundx/types';
import { Api } from 'chessgroundx/api';

import { _ } from './i18n';
import { getDocumentData } from './document';
import {
    ensureBoardStyleOverride,
    ensureCataloguedBoardCSS,
    ensurePieceCSS,
    pieceStyleClass,
    removeCataloguedBoardCSS,
} from './document';
import { Settings, NumberSettings, BooleanSettings } from './settings';
import { slider, checkbox } from './view';
import { BoardName, PyChessModel } from './types';
import { BOARD_FAMILIES, cwdaArmyClassNames, isCataloguedVariant, PIECE_FAMILIES, Variant, VARIANTS } from './variants';
import { renderResized, updateBounds } from 'chessgroundx/render';
import { setSquareColors } from './boardColors';
import { clampZoom, minZoomPercent, setBoardZoom } from './two-board/squareUnit';

export interface BoardController {
    readonly chessground: Api;

    boardName: BoardName;
    readonly variant: Variant;
    readonly mycolor: cg.Color;
    readonly oppcolor: cg.Color;
    readonly hasPockets: boolean;

    notation: cg.Notation;
    fullfen: string;

    model?: PyChessModel;
    autoPromote?: boolean;
    autoClaimDraw?: boolean;
    arrow?: boolean;
    multipv?: number;
    evalFile?: string;
    materialDifference?: boolean;
    updateMaterial?: any;
    pvboxIni?: any;
    nnueIni?: any;
    chartFunctions?: any[];
    vmaterial0?: VNode | HTMLElement;
    vmaterial1?: VNode | HTMLElement;

    flipped(): boolean;
}

interface PieceCSSOption {
    css: string;
    idx: number;
}

function pieceCSSOptions(pieceFamily: keyof typeof PIECE_FAMILIES | string, variant?: Variant): PieceCSSOption[] {
    const excluded = new Set(variant?.pieceCSSExclude ?? []);
    return PIECE_FAMILIES[pieceFamily].pieceCSS
        .map((css, idx) => ({ css, idx }))
        .filter(({ css }) => css !== 'letters' && css !== 'invisible' && !excluded.has(css));
}

function isCataloguedPreviewStyle(pieceFamily: string, css: string): boolean {
    return pieceFamily.startsWith('catalogued-') && (css.startsWith('custom') || css === 'disguised');
}

function selectedPieceCSS(pieceFamily: keyof typeof PIECE_FAMILIES | string, idx: number, variant?: Variant): string {
    switch (idx) {
        case 98:
            return 'invisible';
        case 99:
            return 'letters';
        default: {
            const css = PIECE_FAMILIES[pieceFamily].pieceCSS[idx];
            const excluded = variant?.pieceCSSExclude ?? [];
            if (css && !excluded.includes(css)) return css;
            return pieceCSSOptions(pieceFamily, variant)[0]?.css ?? PIECE_FAMILIES[pieceFamily].pieceCSS[0];
        }
    }
}

function defaultPieceStyleIndex(pieceFamily: keyof typeof PIECE_FAMILIES | string, variant?: Variant): number {
    const styles = PIECE_FAMILIES[pieceFamily]?.pieceCSS ?? [];
    if (variant && isCataloguedVariant(variant.name) && styles.length === 1 && styles[0] === 'disguised') {
        return 99;
    }
    return 0;
}

function pieceStyleSettingsName(pieceFamily: string, variant?: Variant): string {
    return (variant?.name ?? pieceFamily) + '-piece';
}

function boardStyleSettingsName(variant: Variant): string {
    return variant.name + '-board';
}

function selectedBoardCSS(boardFamily: keyof typeof BOARD_FAMILIES | string, idx: number): string {
    return BOARD_FAMILIES[boardFamily].boardCSS[idx] ?? BOARD_FAMILIES[boardFamily].boardCSS[0];
}

function setBoardStyle(target: HTMLElement, assetURL: string, css: string): void {
    ensureBoardStyleOverride();
    target.style.setProperty('--board-image', `url(${assetURL}/images/board/${css})`);
    // The theme's two square colours, published for anything drawn on a square that has
    // to contrast with it. Set here so they change with the image and never separately.
    setSquareColors(target, css);
}

function setCataloguedBoardStyle(target: HTMLElement, variant: Variant): void {
    ensureCataloguedBoardCSS(variant.name, variant.boardRevision);
    target.style.removeProperty('--board-image');
}

function setPieceStyleClass(target: HTMLElement, family: string, css: string, variant: Variant): void {
    for (const className of Array.from(target.classList)) {
        if (className.startsWith('piece-style-')) target.classList.remove(className);
    }
    target.classList.add(pieceStyleClass(family, css));
    const catalogued = isCataloguedVariant(variant.name);
    const pieceFamily = PIECE_FAMILIES[family];
    const imageLayer = pieceFamily?.imageLayerCSS?.includes(css) ?? false;
    const wallArtwork = pieceFamily?.wallCSS?.includes(css) ?? false;
    target.classList.toggle('catalogued-piece-variant', catalogued);
    target.classList.toggle('catalogued-piece-wall-artwork', catalogued && wallArtwork);
    target.classList.toggle(
        'catalogued-missing-piece-fallback',
        catalogued &&
            !family.startsWith('catalogued-') &&
            !imageLayer &&
            !wallArtwork &&
            css !== 'disguised' &&
            css !== 'letters' &&
            css !== 'invisible',
    );
}

function setCwdaArmyClasses(target: HTMLElement, initialFen: string): void {
    for (const className of Array.from(target.classList)) {
        if (className.startsWith('cwda-white-') || className.startsWith('cwda-black-')) {
            target.classList.remove(className);
        }
    }
    target.classList.add(...cwdaArmyClassNames(initialFen));
}

function pieceStyleTargets(variant: Variant, root: ParentNode = document): Set<HTMLElement> {
    const targets = new Set<HTMLElement>();
    const selector = `[data-piece-variant="${variant.name}"]`;

    if (root instanceof HTMLElement && root.matches(selector)) targets.add(root);
    root.querySelectorAll(selector).forEach(el => {
        if (el instanceof HTMLElement) targets.add(el);
    });
    return targets;
}

function boardStyleTargets(variant: Variant, root: ParentNode = document): Set<HTMLElement> {
    const targets = new Set<HTMLElement>();
    const selector = `[data-board-variant="${variant.name}"]`;

    if (root instanceof HTMLElement && root.matches(selector)) targets.add(root);
    root.querySelectorAll(selector).forEach(el => {
        if (el instanceof HTMLElement) targets.add(el);
    });
    return targets;
}

class BoardSettings {
    ctrl: BoardController;
    ctrl2: BoardController;
    settings: { [key: string]: Settings<number | boolean | string> };
    assetURL: string;

    constructor() {
        this.settings = {};
        this.settings['animation'] = new AnimationSettings(this);
        this.settings['confirmresign'] = new ConfirmResignSettings(this);
        this.settings['showDests'] = new ShowDestsSettings(this);
        this.settings['autoPromote'] = new AutoPromoteSettings(this);
        this.settings['autoClaimDraw'] = new AutoClaimDrawSettings(this);
        this.settings['confirmCorrMove'] = new ConfirmCorrMoveSettings(this);
        this.settings['materialDifference'] = new MaterialDifferenceSettings(this);
    }

    getSettings(settingsType: string, family: string, boardName: BoardName = '', variant?: Variant) {
        const fullName =
            settingsType === 'BoardStyle' && variant
                ? boardStyleSettingsName(variant)
                : settingsType === 'PieceStyle'
                  ? pieceStyleSettingsName(family, variant)
                  : family + settingsType + boardName;
        const existing = this.settings[fullName];
        if (
            existing &&
            settingsType === 'BoardStyle' &&
            variant &&
            (!(existing instanceof BoardStyleSettings) ||
                existing.boardFamily !== family ||
                existing.variant !== variant)
        ) {
            delete this.settings[fullName];
        }
        if (
            existing &&
            settingsType === 'PieceStyle' &&
            (!(existing instanceof PieceStyleSettings) ||
                existing.pieceFamily !== family ||
                existing.variant !== variant)
        ) {
            delete this.settings[fullName];
        }
        if (!this.settings[fullName]) {
            switch (settingsType) {
                case 'BoardStyle':
                    if (!variant) throw 'BoardStyle settings require a variant';
                    this.settings[fullName] = new BoardStyleSettings(this, family, variant);
                    break;
                case 'PieceStyle':
                    this.settings[fullName] = new PieceStyleSettings(this, family, variant);
                    break;
                case 'Zoom':
                    this.settings[fullName] = new ZoomSettings(this, family, boardName);
                    break;
                default:
                    throw 'Unknown settings type ' + settingsType;
            }
        }
        return this.settings[fullName];
    }

    updateBoardAndPieceStyles() {
        Object.values(VARIANTS).forEach(variant => {
            this.updateActiveBoardStyle(variant);
            this.updateActivePieceStyle(variant);
        });
    }

    boardCSS(family: keyof typeof BOARD_FAMILIES, variant: Variant) {
        const idx = this.getSettings('BoardStyle', family as string, '', variant).value as number;
        return selectedBoardCSS(family, idx);
    }

    updateActiveBoardStyle(variant: Variant) {
        const family = variant.boardFamily;
        const css = this.boardCSS(family, variant);
        if (variant.hasBoard) {
            boardStyleTargets(variant).forEach(target => setCataloguedBoardStyle(target, variant));
        } else {
            removeCataloguedBoardCSS(variant.name);
            boardStyleTargets(variant).forEach(target => setBoardStyle(target, this.assetURL, css));
        }
    }

    updateScopedBoardStyle(variant: Variant, el?: Element) {
        const family = variant.boardFamily;
        const css = this.boardCSS(family, variant);

        if (el instanceof HTMLElement) {
            const target = (el.closest('.' + family) as HTMLElement | null) ?? el;
            target.dataset.boardVariant = variant.name;
            if (variant.hasBoard) setCataloguedBoardStyle(target, variant);
            else {
                removeCataloguedBoardCSS(variant.name);
                setBoardStyle(target, this.assetURL, css);
            }
        }
    }

    updateActivePieceStyle(variant: Variant) {
        const family = variant.pieceFamily;
        const css = this.pieceCSS(family, variant);
        ensurePieceCSS(this.assetURL, family as string, css);

        const targets = pieceStyleTargets(variant);
        if (this.ctrl?.variant.name === variant.name || this.ctrl2?.variant.name === variant.name) {
            const root =
                document.getElementById('mainboard')?.closest('.round-app, .analysis-app, .embed-app, .editor-app') ??
                document;
            if (root instanceof HTMLElement && root.classList.contains(family)) targets.add(root);
            root.querySelectorAll('.' + family).forEach(el => {
                if (el instanceof HTMLElement) targets.add(el);
            });
        }

        targets.forEach(target => setPieceStyleClass(target, family as string, css, variant));
        this.updateDropSuggestion();
    }

    pieceCSS(family: keyof typeof PIECE_FAMILIES, variant?: Variant) {
        const idx = this.getSettings('PieceStyle', family as string, '', variant).value as number;
        return selectedPieceCSS(family, idx, variant);
    }

    updateScopedPieceStyle(variant: Variant, el?: Element, initialFen = '') {
        const family = variant.pieceFamily;
        const css = this.pieceCSS(family, variant);
        ensurePieceCSS(this.assetURL, family as string, css);

        if (el instanceof HTMLElement) {
            const target = (el.closest('.' + family) as HTMLElement | null) ?? el;
            target.dataset.pieceVariant = variant.name;
            if (variant.name === 'cwda') setCwdaArmyClasses(target, initialFen);
            setPieceStyleClass(target, family as string, css, variant);
        }
    }

    updateDropSuggestion() {
        this.updateDropSuggestionCtrl(this.ctrl);
        this.updateDropSuggestionCtrl(this.ctrl2);
    }

    updateDropSuggestionCtrl(ctrl: BoardController) {
        // Redraw the piece being suggested for dropping in the new piece style
        if (ctrl && ctrl.hasPockets) {
            const chessground = this.ctrl.chessground;
            const el = document.querySelector('svg image') as HTMLElement;
            // if there is any
            if (el) {
                chessground.redrawAll();
            }
        }
    }

    // The board this slider resizes, which is NOT the board it is named after.
    //
    // A zoom slider is keyed by COLUMN: `--zoom-a` scales the left column, whose
    // board is the viewer's own in every seating, because roundCtrl switches the
    // boards between columns rather than re-keying the tracks. `boardName` names a
    // board by IDENTITY. The two coincide only for a board-A viewer, and for a
    // board-B one they cross: measured on a live game, moving slider `a` took the
    // left column's track from 453px to 226px while the board sitting in it stayed
    // at 446.67 — never told to re-measure, and therefore resolving every click
    // against bounds for a box it no longer occupies.
    //
    // Read from the role classes, which is where markRoles() records which board is
    // in which column and the same thing the stylesheet selects on. Absent — the
    // analysis page marks no roles — this falls back to identity, which is what
    // that page's own single grid means by A and B.
    zoomedBoard(boardName: BoardName): BoardController | undefined {
        if (!boardName) return this.ctrl;
        const el = document.querySelector(boardName === 'a' ? '.own-board' : '.partner-board');
        const inColumn = el?.id === 'bugboard' ? 'b' : el?.id === 'mainboard' ? 'a' : boardName;
        return inColumn === this.ctrl2?.boardName ? this.ctrl2 : this.ctrl;
    }

    updateZoom(family: keyof typeof BOARD_FAMILIES, boardName: BoardName = '') {
        const variant = this.ctrl?.variant;
        if (variant && variant.boardFamily === family) {
            const suffix = boardName ? '-' + boardName : '';
            const zoomSettings = this.getSettings('Zoom', family as string, boardName) as ZoomSettings;
            // A bughouse board has a floor, and it is a SIZE rather than a percentage — see
            // `minZoomPercent()`. Clamped here rather than on the stored value: the setting is
            // the user's standing preference, and a window they resize should not silently
            // rewrite it. What is clamped is what this window draws with.
            const zoom = boardName ? clampZoom(boardName, zoomSettings.value) : zoomSettings.value;
            const el = document.querySelector('.cg-wrap') as HTMLElement;
            if (el) {
                document.body.style.setProperty('--zoom' + suffix, `${zoom}`);

                // The bughouse tracks are built from a unit that is quantised at
                // this scale, so the unit has to be republished before the board
                // is measured against it. Arithmetic, not a measurement — see
                // setBoardZoom().
                if (boardName) setBoardZoom(boardName, zoomSettings.value);

                // Analysis needs to zoom analysisChart and movetimeChart as well
                if ('chartFunctions' in this.ctrl && this.ctrl.chartFunctions) {
                    this.ctrl.chartFunctions.forEach((func: any) => {
                        func(this.ctrl);
                    });
                }
            }
        }
    }

    view(variantName: string, modelVariant: string) {
        if (!variantName) return h('div#board-settings');
        const variant = VARIANTS[variantName];

        const settingsList: VNode[] = [];

        const boardFamily = VARIANTS[variantName].boardFamily;
        const pieceFamily = VARIANTS[variantName].pieceFamily;

        settingsList.push(this.settings['animation'].view());

        settingsList.push(this.settings['confirmresign'].view());

        settingsList.push(this.settings['showDests'].view());

        if (variant.promotion.autoPromoteable) settingsList.push(this.settings['autoPromote'].view());

        settingsList.push(this.settings['autoClaimDraw'].view());

        settingsList.push(this.settings['confirmCorrMove'].view());

        settingsList.push(this.settings['materialDifference'].view());

        if (variantName === modelVariant)
            if (variant.twoBoards) {
                settingsList.push(this.getSettings('Zoom', boardFamily as string, 'a').view());
                settingsList.push(this.getSettings('Zoom', boardFamily as string, 'b').view());
            } else {
                settingsList.push(this.getSettings('Zoom', boardFamily as string, '').view());
            }

        settingsList.push(
            h('div#style-settings', [
                this.getSettings('BoardStyle', boardFamily as string, '', variant).view(),
                (this.getSettings('PieceStyle', pieceFamily as string, '', variant) as PieceStyleSettings).view(),
            ]),
        );

        settingsList.push();

        return h('div#board-settings', settingsList);
    }
}

class AnimationSettings extends BooleanSettings {
    readonly boardSettings: BoardSettings;

    constructor(boardSettings: BoardSettings) {
        super('animation', true);
        this.boardSettings = boardSettings;
    }

    update(): void {
        this.boardSettings.ctrl?.chessground.set({ animation: { enabled: this.value } });
        this.boardSettings.ctrl2?.chessground.set({ animation: { enabled: this.value } });
    }

    view(): VNode {
        return h('div', checkbox(this, 'animation', _('Piece animation')));
    }
}

class ConfirmResignSettings extends BooleanSettings {
    readonly boardSettings: BoardSettings;

    constructor(boardSettings: BoardSettings) {
        super('confirmresign', true);
        this.boardSettings = boardSettings;
    }

    update(): void {}

    view(): VNode {
        return h('div', checkbox(this, 'confirmresign', _('Confirm resigning')));
    }
}

class ConfirmCorrMoveSettings extends BooleanSettings {
    readonly boardSettings: BoardSettings;

    constructor(boardSettings: BoardSettings) {
        super('confirmCorrMove', true);
        this.boardSettings = boardSettings;
    }

    update(): void {}

    view(): VNode {
        return h('div', checkbox(this, 'confirmCorrMove', _('Confirm correspondence move')));
    }
}

class BoardStyleSettings extends NumberSettings {
    readonly boardSettings: BoardSettings;
    readonly boardFamily: string;
    readonly variant: Variant;

    constructor(boardSettings: BoardSettings, boardFamily: string, variant: Variant) {
        super(boardStyleSettingsName(variant), Number(localStorage[boardFamily + '-board'] ?? 0));
        this.boardSettings = boardSettings;
        this.boardFamily = boardFamily;
        this.variant = variant;
    }

    update(): void {
        this.boardSettings.updateActiveBoardStyle(this.variant);
    }

    view(): VNode {
        if (this.variant.hasBoard) {
            ensureCataloguedBoardCSS(this.variant.name, this.variant.boardRevision);
            return h('settings-board', [
                h('input#board0', {
                    props: { type: 'radio', name: 'board', value: 0, checked: true, disabled: true },
                }),
                h(
                    'label.board.catalogued-custom-board-preview',
                    {
                        attrs: { for: 'board0', 'data-board-variant': this.variant.name },
                        style: {
                            aspectRatio: `${this.variant.board.dimensions.width} / ${this.variant.board.dimensions.height}`,
                        },
                    },
                    '',
                ),
            ]);
        }

        const vboard = this.value;
        const boards: VNode[] = [];

        const boardCSS = BOARD_FAMILIES[this.boardFamily].boardCSS;
        for (let i = 0; i < boardCSS.length; i++) {
            boards.push(
                h('input#board' + i, {
                    on: { change: evt => (this.value = Number((evt.target as HTMLInputElement).value)) },
                    props: { type: 'radio', name: 'board', value: i },
                    attrs: { checked: vboard === i, 'aria-label': styleName(boardCSS[i]) },
                }),
            );
            boards.push(
                h(
                    'label.board.board' + i + '.' + this.boardFamily,
                    {
                        attrs: { for: 'board' + i },
                        style: { backgroundImage: `url('/static/images/board/${boardCSS[i]}')` },
                    },
                    '',
                ),
            );
        }
        return h('settings-board', boards);
    }
}

class PieceStyleSettings extends NumberSettings {
    readonly boardSettings: BoardSettings;
    readonly pieceFamily: string;
    readonly variant?: Variant;

    constructor(boardSettings: BoardSettings, pieceFamily: string, variant?: Variant) {
        const settingsName = pieceStyleSettingsName(pieceFamily, variant);
        const defaultValue = defaultPieceStyleIndex(pieceFamily, variant);
        super(settingsName, defaultValue);
        this.boardSettings = boardSettings;
        this.pieceFamily = pieceFamily;
        this.variant = variant;

        if (!getDocumentData(settingsName) && localStorage.getItem(settingsName) === null) {
            this._value = defaultValue;
        }
    }

    update(): void {
        if (this.variant) this.boardSettings.updateActivePieceStyle(this.variant);
    }

    view(): VNode {
        const vpiece = this.value;
        const pieces: VNode[] = [];

        const pieceCSS = pieceCSSOptions(this.pieceFamily, this.variant);
        const checkedPiece =
            vpiece === 98 || vpiece === 99 || pieceCSS.some(({ idx }) => idx === vpiece)
                ? vpiece
                : (pieceCSS[0]?.idx ?? 99);
        const previewRole = this.variant?.pieceRow.white[0] ?? this.variant?.kingRoles[0] ?? 'k-piece';
        for (const { idx } of pieceCSS) {
            const css = selectedPieceCSS(this.pieceFamily, idx, this.variant);
            const previewClass = css === 'letters' ? 'piece99' : css === 'invisible' ? 'piece98' : 'piece' + idx;
            const isCataloguedPreview = !!this.variant && isCataloguedPreviewStyle(this.pieceFamily, css);
            if (isCataloguedPreview) ensurePieceCSS(this.boardSettings.assetURL, this.pieceFamily, css);
            pieces.push(
                h('input#piece' + idx, {
                    on: { change: e => (this.value = Number((e.target as HTMLInputElement).value)) },
                    props: { type: 'radio', name: 'piece', value: idx },
                    attrs: { checked: checkedPiece === idx, 'aria-label': styleName(css) },
                }),
            );
            pieces.push(
                h(
                    'label.piece.' + previewClass + '.' + this.pieceFamily,
                    {
                        attrs: { for: 'piece' + idx },
                        class: isCataloguedPreview
                            ? {
                                  'catalogued-custom-preview': css.startsWith('custom'),
                                  'catalogued-disguised-preview': css === 'disguised',
                                  [pieceStyleClass(this.pieceFamily, css)]: true,
                                  [previewRole]: true,
                                  white: true,
                              }
                            : undefined,
                    },
                    '',
                ),
            );
        }

        // Add invisible piece
        const i = 98;
        pieces.push(
            h('input#piece' + i, {
                on: { change: e => (this.value = Number((e.target as HTMLInputElement).value)) },
                props: { type: 'radio', name: 'piece', value: i },
                attrs: { checked: vpiece === i, 'aria-label': styleName('invisible') },
            }),
        );
        pieces.push(h('label.piece.piece98', { attrs: { for: 'piece' + i } }, ''));

        // Finally add letter piece
        const l = 99;
        pieces.push(
            h('input#piece' + l, {
                on: { change: e => (this.value = Number((e.target as HTMLInputElement).value)) },
                props: { type: 'radio', name: 'piece', value: l },
                attrs: { checked: vpiece === l, 'aria-label': styleName('letters') },
            }),
        );
        pieces.push(h('label.piece.piece99', { attrs: { for: 'piece' + l } }, ''));
        return h('settings-pieces', pieces);
    }
}

// The style's own file or CSS name ("wood4.jpg", "cburnett"): the picture is all its label shows.
function styleName(file: string): string {
    const name = file
        .replace(/^.*\//, '')
        .replace(/\.[a-z0-9]+$/i, '')
        .replace(/[-_]/g, ' ')
        .replace(/([a-z])([A-Z])/g, '$1 $2')
        .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2');
    // "8x8brown": the size is the board's, not the theme's
    return name.replace(/^\d+x\d+(?=\D)/, '') || name;
}

const ZOOM_DEFAULT = 80;

function zoomSettingName(boardFamily: string, boardName: BoardName = ''): string {
    return boardFamily + '-zoom' + (boardName ? '-' + boardName : '');
}

// The zoom a board will be drawn at, read the way NumberSettings reads it.
//
// Exported because the square unit has to be quantised at the scale the board
// actually draws at, and squareUnit.ts has to publish that before any board — and
// therefore before any ZoomSettings instance — exists. Reading the CSS variable
// instead would give the wrong answer on a first load: `--zoom-a` is only written
// once initBoardSettings() runs, which is after the boards are built, so the
// stylesheet's 100 would be quantised against for a board about to draw at 80.
export function boardZoom(boardFamily: string, boardName: BoardName = ''): number {
    const name = zoomSettingName(boardFamily, boardName);
    return Number(getDocumentData(name) ?? localStorage[name] ?? ZOOM_DEFAULT);
}

class ZoomSettings extends NumberSettings {
    readonly boardSettings: BoardSettings;
    readonly boardFamily: string;
    readonly boardName: BoardName;

    constructor(boardSettings: BoardSettings, boardFamily: string, boardName: BoardName = '') {
        super(zoomSettingName(boardFamily, boardName), ZOOM_DEFAULT);
        this.boardSettings = boardSettings;
        this.boardFamily = boardFamily;
        this.boardName = boardName;
    }

    update(): void {
        this.boardSettings.updateZoom(this.boardFamily, this.boardName);
        if (this.boardName) {
            // A bughouse board is not observed — nothing watches it resize, by
            // design — so the redraw has to be asked for here, on the user's action,
            // which is one of the two points at which a board may be redrawn at all.
            //
            // Synchronous, not on a timer. This used to wait 100ms for "the style to
            // reach layout", which is a guess at a duration rather than an ordering:
            // updateBounds() reads getBoundingClientRect(), and reading layout
            // flushes the pending style and layout first, so it cannot observe a
            // stale box however soon it runs. The variable written just above is
            // therefore already in effect by the time it is measured, and the timer
            // only delayed the redraw by 100ms and made the ordering unprovable.
            // BOTH COLUMNS, NOT JUST THE ONE THAT MOVED — but they need different things.
            //
            // The zoomed board changed SIZE, so it is re-measured and redrawn as before. The OTHER
            // board moved without changing size: the app's first track is
            // `calc(var(--bug-tall-sq-a) * 8)`, so a narrower left board shifts the right one
            // sideways. Nothing tells chessgroundx about a board that merely moves, and every
            // click on it then maps through the rect it had before this slider was touched.
            //
            // Clearing its memo is enough, and is deliberately less than re-measuring: it writes
            // nothing, so it cannot wake the observers that would move the boards again, and the
            // rect is recomputed at the next read rather than at a moment we would have to guess.
            for (const boardName of ['a', 'b'] as const) {
                const board = this.boardSettings.zoomedBoard(boardName);
                if (!board) continue;
                if (boardName === this.boardName) {
                    updateBounds(board.chessground.state);
                    renderResized(board.chessground.state);
                } else {
                    board.chessground.state.dom.bounds.clear();
                }
            }
        }
    }

    view(): VNode {
        return h(
            'div.labelled',
            // The handle stops where the layout does: a bughouse column may not be taken below
            // the smallest stack the left board's square allows, and the two columns reach that
            // size at different percentages.
            slider(
                this,
                'zoom' + this.boardName,
                this.boardName ? minZoomPercent(this.boardName) : 0,
                100,
                this.boardFamily.includes('shogi') ? 1 : 1.15625,
                _('Zoom'),
            ),
        );
    }
}

class ShowDestsSettings extends BooleanSettings {
    readonly boardSettings: BoardSettings;

    constructor(boardSettings: BoardSettings) {
        super('showDests', true);
        this.boardSettings = boardSettings;
    }

    update(): void {
        this.updateCtrl(this.boardSettings.ctrl);
        if (this.boardSettings.ctrl2) this.updateCtrl(this.boardSettings.ctrl2);
    }

    updateCtrl(ctrl: BoardController): void {
        ctrl?.chessground.set({
            movable: {
                showDests: this.value,
            },
        });
    }

    view(): VNode {
        return h('div', checkbox(this, 'showDests', _('Show piece destinations')));
    }
}

class AutoPromoteSettings extends BooleanSettings {
    readonly boardSettings: BoardSettings;

    constructor(boardSettings: BoardSettings) {
        super('autoPromote', false);
        this.boardSettings = boardSettings;
    }

    update(): void {
        this.updateCtrl(this.boardSettings.ctrl);
        if (this.boardSettings.ctrl2) this.updateCtrl(this.boardSettings.ctrl2);
    }

    updateCtrl(ctrl: BoardController): void {
        if ('autoPromote' in ctrl) ctrl.autoPromote = this.value;
    }

    view(): VNode {
        return h('div', checkbox(this, 'autoPromote', _('Promote to the top choice automatically')));
    }
}

class AutoClaimDrawSettings extends BooleanSettings {
    readonly boardSettings: BoardSettings;

    constructor(boardSettings: BoardSettings) {
        super('autoClaimDraw', false);
        this.boardSettings = boardSettings;
    }

    update(): void {
        this.updateCtrl(this.boardSettings.ctrl);
        if (this.boardSettings.ctrl2) this.updateCtrl(this.boardSettings.ctrl2);
    }

    updateCtrl(ctrl: BoardController): void {
        if ('autoClaimDraw' in ctrl) ctrl.autoClaimDraw = this.value;
    }

    view(): VNode {
        return h('div', checkbox(this, 'autoClaimDraw', _('Claim draw automatically when available')));
    }
}

class MaterialDifferenceSettings extends BooleanSettings {
    readonly boardSettings: BoardSettings;

    constructor(boardSettings: BoardSettings) {
        super('materialDifference', false);
        this.boardSettings = boardSettings;
    }

    update(): void {
        this.updateCtrl(this.boardSettings.ctrl);
        if (this.boardSettings.ctrl2) this.updateCtrl(this.boardSettings.ctrl2);
    }

    updateCtrl(ctrl: BoardController): void {
        if ('materialDifference' in ctrl) {
            ctrl.materialDifference = this.value;
            if ('updateMaterial' in ctrl) {
                ctrl.updateMaterial();
            }
        }
    }

    view(): VNode {
        return h('div', checkbox(this, 'captured', _('Show material difference')));
    }
}
export const boardSettings = new BoardSettings();
