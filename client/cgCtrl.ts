import * as cg from 'chessgroundx/types';
import { Chessground } from 'chessgroundx/chessground';
import { Api } from 'chessgroundx/api';

import { FairyStockfish, Board, Notation } from 'ffish-es6';

import { boardSettings, BoardController } from '@/boardSettings';
import { CGMove, uci2cg } from '@/chess';
import { BoardName, PyChessModel } from '@/types';
import { fogFen, Variant, VARIANTS, moddedVariant } from '@/variants';
import { clearPassMoveAnimation } from '@/passMove';
import { bindBoardResize } from '@/miniBoard';

type MouchEvent = Event & Partial<MouseEvent & TouchEvent>;

export abstract class ChessgroundController implements BoardController {
    private readonly onBoardUnload = () => this.ffishBoard.delete();
    private readonly unbindBoardResize?: () => void;
    boardName: BoardName;
    readonly home: string;

    chessground: Api;
    ffish: FairyStockfish;
    ffishBoard: Board;
    notationAsObject: Notation;

    readonly variant: Variant;
    readonly engineVariant: string;
    readonly chess960: boolean;
    readonly hasPockets: boolean;
    readonly anon: boolean;
    mycolor: cg.Color;
    oppcolor: cg.Color;

    fullfen: string;
    notation: cg.Notation;
    fog: boolean;

    constructor(
        el: HTMLElement,
        model: PyChessModel,
        fullfen: string,
        pocket0: HTMLElement,
        pocket1: HTMLElement,
        boardName: BoardName = '',
    ) {
        this.boardName = boardName;
        this.home = model.home;
        this.ffish = model.ffish;
        this.variant = VARIANTS[model.variant];
        this.chess960 = model.chess960 === 'True';
        this.hasPockets = !!this.variant.pocket;
        this.anon = model.anon === 'True';
        this.mycolor = 'white';
        this.oppcolor = 'black';
        this.fullfen = fullfen;
        this.notation = this.variant.notation;
        this.fog = this.variant.hiddenInfoMode === 'fog';

        const parts = this.fullfen.split(' ');
        const fen = this.fog ? ([fogFen(parts[0]), ...parts.slice(1)].join(' ') as cg.FEN) : (this.fullfen as cg.FEN);

        this.chessground = Chessground(
            el,
            {
                fen,
                dimensions: this.variant.board.dimensions,
                notation: this.notation,
                addDimensionsCssVarsTo: document.body,
                dimensionsCssVarsSuffix: this.boardName,
                kingRoles: this.variant.kingRoles,
                pocketRoles: this.variant.pocket?.roles,
                events: { insert: this.onInsert() },
            },
            pocket0,
            pocket1,
        );

        if (this.variant.hasBoard && !this.boardName) {
            this.unbindBoardResize = bindBoardResize(this.chessground);
        }

        if (this.boardName === 'b') {
            boardSettings.ctrl2 = this;
        } else {
            boardSettings.ctrl = this;
        }
        boardSettings.assetURL = model.assetURL;
        const boardFamily = this.variant.boardFamily;
        boardSettings.updateScopedBoardStyle(this.variant, el);
        boardSettings.updateScopedPieceStyle(this.variant, el, model.initialFen || this.fullfen);
        boardSettings.updateActivePieceStyle(this.variant);
        boardSettings.updateZoom(boardFamily, '');

        this.notationAsObject = this.notation2ffishjs(this.notation);
        this.engineVariant = moddedVariant(
            this.variant.name,
            this.chess960,
            this.chessground.state.boardState.pieces,
            parts[2],
            model.initialFen || this.fullfen,
        );
        this.ffishBoard = new this.ffish.Board(this.engineVariant, this.fullfen, this.chess960);
        window.addEventListener('beforeunload', this.onBoardUnload);
    }

    destroy(): void {
        window.removeEventListener('beforeunload', this.onBoardUnload);
        this.unbindBoardResize?.();
        this.chessground.destroy();
        this.ffishBoard.delete();
    }

    onInsert = () => {
        return (elements: cg.Elements) => {
            console.log('onInsert()');
            const el = document.createElement('cg-resize');
            elements.container.appendChild(el);

            const startResize = (start: MouchEvent) => {
                start.preventDefault();

                // THE COLUMN THE BOARD IS IN, NOT THE BOARD'S OWN NAME.
                //
                // On a two-board page `boardName` is the board's IDENTITY — 'a' is `#mainboard`,
                // 'b' is `#bugboard` — while every zoom setting is keyed by the COLUMN: 'a' is the
                // viewer's own stack and 'b' the partner's, which is why `zoomedBoard()` in
                // boardSettings.ts looks up which board sits in the column it was asked about.
                //
                // The two coincide for a player whose own board is board A, and disagree for one
                // whose own board is board B — where this handle drove the OTHER column. Measured
                // on a seat holding `#bugboard`: dragging the own board's handle wrote `zoom-b`,
                // which sizes the partner's column, so the own board did not move at all and the
                // partner's shrank to its floor.
                const column: BoardName = this.boardName
                    ? el.closest('.own-board') !== null
                        ? 'a'
                        : 'b'
                    : this.boardName;

                const zoomSettings = boardSettings.getSettings('Zoom', this.variant.boardFamily, column);
                const sliderEl = document.getElementById('zoom' + column) as HTMLInputElement;

                // The green "being dragged" look belongs to THIS handle. `site.css` hangs it off
                // `body.resizing`, which matches every handle on the page — invisible on a
                // one-board page and wrong on a two-board one, where both corners lit up whichever
                // was grabbed. The body class stays: it also suppresses text selection, which does
                // have to be page-wide.
                el.classList.add('resizing');

                const mousemoveEvent = start.type === 'touchstart' ? 'touchmove' : 'mousemove',
                    mouseupEvent = start.type === 'touchstart' ? 'touchend' : 'mouseup',
                    startPos = eventPosition(start)!,
                    initialZoom = zoomSettings.value as number;

                let zoom = initialZoom;

                const resize = (move: MouchEvent) => {
                    const pos = eventPosition(move)!,
                        delta = pos[0] - startPos[0] + pos[1] - startPos[1];

                    zoom = Math.round(Math.min(100, Math.max(0, initialZoom + delta / 10)));

                    zoomSettings.value = zoom;
                    sliderEl.value = zoom.toString();
                    zoomSettings.update();
                };

                document.body.classList.add('resizing');

                document.addEventListener(mousemoveEvent, resize);

                document.addEventListener(
                    mouseupEvent,
                    () => {
                        document.removeEventListener(mousemoveEvent, resize);
                        document.body.classList.remove('resizing');
                        el.classList.remove('resizing');
                    },
                    { once: true },
                );
            };

            el.addEventListener('touchstart', startResize, { passive: false });
            el.addEventListener('mousedown', startResize, { passive: false });
        };
    };

    toggleOrientation(): void {
        clearPassMoveAnimation(this.chessground);
        this.chessground.toggleOrientation();
    }

    flipped(): boolean {
        return this.chessground.state.orientation === 'black';
    }

    legalMoves(): CGMove[] {
        return this.ffishBoard.legalMoves().split(' ').map(uci2cg) as CGMove[];
    }

    notation2ffishjs(n: cg.Notation): Notation {
        switch (n) {
            case cg.Notation.ALGEBRAIC:
                return this.ffish.Notation.SAN;
            case cg.Notation.SHOGI_ARBNUM:
                return this.ffish.Notation.SHOGI_HODGES_NUMBER;
            case cg.Notation.JANGGI:
                return this.ffish.Notation.JANGGI;
            case cg.Notation.XIANGQI_ARBNUM:
                return this.ffish.Notation.XIANGQI_WXF;
            default:
                return this.ffish.Notation.SAN;
        }
    }
}

function eventPosition(e: MouchEvent): [number, number] | undefined {
    if (e.clientX || e.clientX === 0) return [e.clientX, e.clientY!];
    if (e.targetTouches?.[0]) return [e.targetTouches[0].clientX, e.targetTouches[0].clientY];
    return;
}
