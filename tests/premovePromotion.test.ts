import fs from 'node:fs';
import path from 'node:path';
import { afterEach, beforeAll, beforeEach, describe, expect, jest, test } from '@jest/globals';
import { Chessground } from 'chessgroundx/chessground';
import type * as cg from 'chessgroundx/types';
import { opposite } from 'chessgroundx/util';
import type { FairyStockfish } from 'ffish-es6';

import { GameController } from '../client/gameCtrl';
import { GatingInput } from '../client/input/gating';
import { PromotionInput } from '../client/input/promotion';
import { DuckInput } from '../client/input/duck';
import { ArrowingInput } from '../client/input/arrowing';
import { VARIANTS } from '../client/variants';
import { moveDests, UCIMove } from '../client/chess';
import { premoveForVariant } from '../client/premove';
import { variantsIni } from '../client/variantsIni';
import { predrop } from 'chessgroundx/predrop';

let ffish: FairyStockfish;
const controllers: GameController[] = [];
const promotionFen = '7k/P7/8/8/8/8/8/7K b - - 0 1';
const flushCallbacks = () => new Promise(resolve => setTimeout(resolve, 15));

beforeAll(async () => {
    const moduleNs: any = await import('ffish-es6');
    const init = moduleNs.default?.default ?? moduleNs.default ?? moduleNs;
    ffish = await init({
        wasmBinary: fs.readFileSync(path.resolve('node_modules/ffish-es6/ffish.wasm')),
        printErr: () => {},
    });
    ffish.loadVariantConfig('[limitedpromo:chess]\npromotionLimit = q:1\n');
    ffish.loadVariantConfig(variantsIni);
});

beforeEach(() => {
    document.body.innerHTML = '';
});

afterEach(async () => {
    await flushCallbacks();
    for (const ctrl of controllers.splice(0)) {
        ctrl.promotion.dismiss();
        ctrl.chessground.destroy();
        ctrl.ffishBoard.delete();
    }
});

function controller(fen = promotionFen, variant = 'chess', engineVariant = variant, color: cg.Color = 'white') {
    const el = document.createElement('div');
    document.body.appendChild(el);
    const sent: { move: string; premove: boolean }[] = [];
    const ctrl = Object.assign(Object.create(GameController.prototype), {
        variant: VARIANTS[variant],
        engineVariant,
        ffish,
        ffishBoard: new ffish.Board(engineVariant, fen),
        fullfen: fen,
        chess960: false,
        mycolor: color,
        turnColor: opposite(color),
        autoPromote: false,
        preaction: false,
        ply: 0,
        steps: [],
        doSendMove: jest.fn((move: string) => sent.push({ move, premove: ctrl.preaction })),
        goPly: jest.fn(() => {
            ctrl.promotion.dismiss();
            ctrl.chessground.set({ fen: ctrl.ffishBoard.fen() });
        }),
    }) as GameController;
    const hooks = ctrl as unknown as {
        setPremove(orig: cg.Orig, dest: cg.Key, meta?: cg.SetPremoveMetadata): void;
        unsetPremove(): void;
        onUserMove(orig: cg.Key, dest: cg.Key, meta: cg.MoveMetadata): void;
        onUserDrop(piece: cg.Piece, dest: cg.Key, meta: cg.MoveMetadata): void;
    };
    ctrl.chessground = Chessground(el, {
        fen,
        dimensions: ctrl.variant.board.dimensions,
        pocketRoles: ctrl.variant.pocket?.roles,
        turnColor: opposite(color),
        orientation: color,
        animation: { enabled: false },
        movable: {
            color,
            free: false,
            events: {
                after: (orig, dest, meta) => hooks.onUserMove(orig, dest, meta),
                afterNewPiece: (piece, dest, meta) => hooks.onUserDrop(piece, dest, meta),
            },
        },
        premovable: {
            enabled: true,
            premoveFunc: premoveForVariant(variant, false, ctrl.variant.board.dimensions),
            predropFunc: predrop(variant, ctrl.variant.board.dimensions),
            events: {
                set: (orig, dest, meta) => hooks.setPremove(orig, dest, meta),
                unset: () => hooks.unsetPremove(),
            },
        },
    });
    ctrl.gating = new GatingInput(ctrl);
    ctrl.promotion = new PromotionInput(ctrl);
    ctrl.duck = new DuckInput(ctrl);
    ctrl.arrowing = new ArrowingInput(ctrl);
    controllers.push(ctrl);
    return { ctrl, sent, el };
}

async function queue(ctrl: GameController, orig: cg.Key = 'a7', dest: cg.Key = 'a8') {
    ctrl.chessground.selectSquare(orig);
    ctrl.chessground.selectSquare(dest);
    await flushCallbacks();
    expect(ctrl.premove).toMatchObject({ orig, dest });
}

async function reply(ctrl: GameController, move = 'h8g8') {
    expect(ctrl.ffishBoard.push(move)).toBe(true);
    ctrl.fullfen = ctrl.ffishBoard.fen();
    ctrl.turnColor = ctrl.mycolor;
    ctrl.chessground.set({ fen: ctrl.fullfen, turnColor: ctrl.mycolor });
    ctrl.chessground.set({
        movable: {
            dests: moveDests(
                ctrl.ffishBoard.legalMoves().split(' ') as UCIMove[],
                false,
                ctrl.chessground.state.boardState.pieces,
                ctrl.mycolor,
            ),
        },
    });
    ctrl.performPremove();
    await flushCallbacks();
}

function choose(el: HTMLElement, role: cg.Role) {
    const piece = el.querySelector(`#extension_choice piece.${role}`);
    expect(piece).not.toBeNull();
    (piece!.parentElement as HTMLElement).click();
}

describe('promotion premoves', () => {
    test('chooses the promoted form of a Kyoto shogi predrop before the opponent moves', async () => {
        const { ctrl, el, sent } = controller('4k/5/5/5/K4[P] b 0 1', 'kyotoshogi');
        ctrl.chessground.selectPocket({ role: 'p-piece', color: 'white' });
        ctrl.chessground.selectSquare('b2');
        await flushCallbacks();
        expect(el.querySelectorAll('#extension_choice square')).toHaveLength(2);
        choose(el, 'pp-piece');
        expect(sent).toEqual([]);
        await reply(ctrl, 'e5d5');
        expect(sent).toEqual([{ move: '+P@b2', premove: true }]);
    });
    test('handles an opponent reply arriving before the deferred premove-set callback', async () => {
        const { ctrl, el, sent } = controller();
        ctrl.chessground.selectSquare('a7');
        ctrl.chessground.selectSquare('a8');
        expect(ctrl.premove).toBeUndefined();
        expect(ctrl.ffishBoard.push('h8g8')).toBe(true);
        ctrl.fullfen = ctrl.ffishBoard.fen();
        ctrl.turnColor = 'white';
        ctrl.chessground.set({ fen: ctrl.fullfen, turnColor: 'white' });
        ctrl.setDests();
        // The real board handler skips performPremove here because the callback
        // has not registered the premove on the controller yet.
        await flushCallbacks();
        expect(el.querySelectorAll('#extension_choice square')).toHaveLength(4);
        choose(el, 'n-piece');
        expect(sent).toEqual([{ move: 'a7a8n', premove: false }]);
    });
    test('supports Black promotion from a flipped board', async () => {
        const { ctrl, el, sent } = controller('7k/8/8/8/8/8/p7/7K w - - 0 1', 'chess', 'chess', 'black');
        await queue(ctrl, 'a2', 'a1');
        expect(el.querySelectorAll('#extension_choice square')).toHaveLength(4);
        choose(el, 'n-piece');
        await reply(ctrl, 'h1g1');
        expect(sent).toEqual([{ move: 'a2a1n', premove: true }]);
        expect(ctrl.chessground.state.boardState.pieces.get('a1')?.color).toBe('black');
    });
    test('chooses a knight before the opponent moves, then submits the complete premove', async () => {
        const { ctrl, el, sent } = controller();
        const fen = ctrl.ffishBoard.fen();
        await queue(ctrl);
        expect(el.querySelectorAll('#extension_choice square')).toHaveLength(4);
        expect(ctrl.ffishBoard.fen()).toBe(fen);
        expect(ctrl.ffishBoard.moveStack()).toBe('');
        expect(ctrl.chessground.state.boardState.pieces.has('a8')).toBe(false);
        choose(el, 'n-piece');
        expect(sent).toEqual([]);
        expect(ctrl.chessground.state.boardState.pieces.get('a7')?.role).toBe('p-piece');
        expect(ctrl.chessground.state.drawable.autoShapes[0].piece?.role).toBe('n-piece');
        await reply(ctrl);
        expect(sent).toEqual([{ move: 'a7a8n', premove: true }]);
        expect(ctrl.chessground.state.drawable.autoShapes).toEqual([]);
        expect(ctrl.premove).toBeUndefined();
    });

    test('keeps the picker usable when the opponent moves before selection, charging selection time', async () => {
        const { ctrl, el, sent } = controller();
        await queue(ctrl);
        const staleChoice = el.querySelector('#extension_choice piece.r-piece')!.parentElement!;
        await reply(ctrl);
        expect(el.querySelectorAll('#extension_choice square')).toHaveLength(4);
        expect(sent).toEqual([]);
        staleChoice.click();
        expect(sent).toEqual([]);
        choose(el, 'r-piece');
        expect(sent).toEqual([{ move: 'a7a8r', premove: false }]);
    });

    test('auto-promotion stores a queen without moving or sending the pawn early', async () => {
        const { ctrl, el, sent } = controller();
        ctrl.autoPromote = true;
        await queue(ctrl);
        expect(el.querySelector('#extension_choice')).toBeNull();
        expect(sent).toEqual([]);
        expect(ctrl.chessground.state.boardState.pieces.get('a7')?.role).toBe('p-piece');
        await reply(ctrl);
        expect(sent).toEqual([{ move: 'a7a8q', premove: true }]);
    });

    test('Ctrl disables auto-promotion through premove execution', async () => {
        const { ctrl, el, sent } = controller();
        ctrl.autoPromote = true;
        ctrl.chessground.state.stats.ctrlKey = true;
        await queue(ctrl);
        expect(el.querySelectorAll('#extension_choice square')).toHaveLength(4);
        await reply(ctrl);
        expect(sent).toEqual([]);
        choose(el, 'b-piece');
        expect(sent).toEqual([{ move: 'a7a8b', premove: false }]);
    });

    test('offers promotion for a capture onto a square the opponent has yet to occupy', async () => {
        const { ctrl, el, sent } = controller('7k/P7/2n5/8/8/8/8/7K b - - 0 1');
        await queue(ctrl, 'a7', 'b8');
        expect(el.querySelectorAll('#extension_choice square')).toHaveLength(4);
        choose(el, 'n-piece');
        await reply(ctrl, 'c6b8');
        expect(sent).toEqual([{ move: 'a7b8n', premove: true }]);
    });

    test('drops the choice if the opponent captures the queued pawn', async () => {
        const { ctrl, el, sent } = controller('7k/Pr6/8/8/8/8/8/7K b - - 0 1');
        await queue(ctrl);
        choose(el, 'n-piece');
        await reply(ctrl, 'b7a7');
        expect(sent).toEqual([]);
        expect(ctrl.premove).toBeUndefined();
        expect(ctrl.chessground.state.drawable.autoShapes).toEqual([]);
    });

    test('rejects a stored suffix made illegal by the actual reply rather than substituting another', async () => {
        const { ctrl, el, sent } = controller('7k/P7/8/8/8/8/Qr6/7K b - - 0 1', 'chess', 'limitedpromo');
        await queue(ctrl);
        choose(el, 'q-piece'); // Available if Black captures our existing queen.
        await reply(ctrl, 'b2b3');
        expect(sent).toEqual([]);
        expect(ctrl.goPly).toHaveBeenCalledWith(0);
        expect(ctrl.chessground.state.drawable.autoShapes).toEqual([]);
    });

    test('canceling or replacing a premove clears its picker and chosen role', async () => {
        const { ctrl, el, sent } = controller();
        await queue(ctrl);
        (el.querySelector('#extension_choice') as HTMLElement).click();
        await flushCallbacks();
        expect(ctrl.premove).toBeUndefined();
        expect(ctrl.goPly).not.toHaveBeenCalled();
        await queue(ctrl);
        choose(el, 'n-piece');
        await queue(ctrl, 'h1', 'g1');
        expect(ctrl.chessground.state.drawable.autoShapes).toEqual([]);
        await reply(ctrl);
        expect(sent).toEqual([{ move: 'h1g1', premove: true }]);
    });

    test('promotion pickers and previews belong to their own board', async () => {
        const a = controller(promotionFen, 'bughouse');
        const b = controller(promotionFen, 'bughouse');
        await queue(a.ctrl);
        await queue(b.ctrl);
        choose(a.el, 'n-piece');
        expect(a.el.querySelector('#extension_choice')).toBeNull();
        expect(b.el.querySelectorAll('#extension_choice square')).toHaveLength(4);
        choose(b.el, 'r-piece');
        await reply(a.ctrl);
        await reply(b.ctrl);
        expect(a.sent).toEqual([{ move: 'a7a8n', premove: true }]);
        expect(b.sent).toEqual([{ move: 'a7a8r', premove: true }]);
    });

    test('refreshes an armed promotion once our previous move is acknowledged', async () => {
        const { ctrl, el, sent } = controller(promotionFen.replace(' b ', ' w '));
        await queue(ctrl);
        expect(el.querySelector('#extension_choice')).toBeNull();
        expect(ctrl.ffishBoard.push('h1g1')).toBe(true);
        ctrl.promotion.refreshPremove();
        expect(el.querySelectorAll('#extension_choice square')).toHaveLength(4);
        choose(el, 'n-piece');
        await reply(ctrl);
        expect(sent).toEqual([{ move: 'a7a8n', premove: true }]);
    });

    test.each(['shogi', 'yokai'])(
        'supports choosing optional %s promotion before the opponent moves',
        async variant => {
            const { ctrl, el, sent } = controller('k8/9/P8/9/9/9/9/9/8K[-] b - - 0 1', variant);
            await queue(ctrl);
            expect(el.querySelectorAll('#extension_choice square')).toHaveLength(2);
            choose(el, 'pp-piece');
            await reply(ctrl, 'a9b9');
            expect(sent).toEqual([{ move: 'a7a8+', premove: true }]);
        },
    );

    test.each(['shogi', 'yokai'])('retains a deliberately declined optional %s promotion', async variant => {
        const { ctrl, el, sent } = controller('k8/9/P8/9/9/9/9/9/8K[-] b - - 0 1', variant);
        await queue(ctrl);
        choose(el, 'p-piece');
        await reply(ctrl, 'a9b9');
        expect(sent).toEqual([{ move: 'a7a8', premove: true }]);
    });

    test.each(['shogi', 'yokai'])('automatically prepares mandatory %s promotion', async variant => {
        const { ctrl, el, sent } = controller('k8/P8/9/9/9/9/9/9/8K[-] b - - 0 1', variant);
        await queue(ctrl, 'a8', 'a9');
        expect(el.querySelector('#extension_choice')).toBeNull();
        expect(sent).toEqual([]);
        await reply(ctrl, 'a9b9');
        expect(sent).toEqual([{ move: 'a8a9+', premove: true }]);
    });

    test('prepares promotion of a Yokai Kitsune before the opponent moves', async () => {
        const { ctrl, el, sent } = controller('k8/9/9/4F4/9/9/9/9/8K[-] b - - 0 1', 'yokai');
        await queue(ctrl, 'e6', 'e7');
        expect(el.querySelectorAll('#extension_choice square')).toHaveLength(2);
        choose(el, 'pf-piece');
        await reply(ctrl, 'a9a8');
        expect(sent).toEqual([{ move: 'e6e7+', premove: true }]);
    });

    test('an already promoted Yokai Tengu can premove backwards as a full knight', async () => {
        const { ctrl, sent } = controller('k8/9/9/9/4+G4/9/9/9/8K[-] b - - 0 1', 'yokai');
        await queue(ctrl, 'e5', 'c4');
        await reply(ctrl, 'a9b9');
        expect(sent).toEqual([{ move: 'e5c4', premove: true }]);
    });

    test('rejects a Yokai premove when the opponent drops a blocker', async () => {
        const { ctrl, el, sent } = controller('1k7/9/9/9/4F4/9/9/9/8K[n] b - - 0 1', 'yokai');
        await queue(ctrl, 'e5', 'e7');
        choose(el, 'f-piece');
        await reply(ctrl, 'N@e6');
        expect(sent).toEqual([]);
        expect(ctrl.premove).toBeUndefined();
        expect(ctrl.chessground.state.boardState.pieces.get('e5')?.role).toBe('f-piece');
    });

    test('a Yokai capture premove can target a piece the opponent has yet to drop', async () => {
        const { ctrl, sent } = controller('1k7/9/9/9/4F4/9/9/9/8K[n] b - - 0 1', 'yokai');
        await queue(ctrl, 'e5', 'f6');
        await reply(ctrl, 'N@f6');
        expect(sent).toEqual([{ move: 'e5f6', premove: true }]);
    });

    test('canceling a queued choice ignores a click from the removed picker', async () => {
        const { ctrl, el, sent } = controller();
        await queue(ctrl);
        const staleChoice = el.querySelector('#extension_choice piece.n-piece')!.parentElement!;
        ctrl.chessground.cancelPremove();
        await flushCallbacks();
        staleChoice.click();
        expect(sent).toEqual([]);
        expect(ctrl.chessground.state.drawable.autoShapes).toEqual([]);
        expect(el.querySelector('#extension_choice')).toBeNull();
    });

    test('preserves unrelated board drawings when clearing the promotion preview', async () => {
        const { ctrl, el } = controller();
        const drawing = { orig: 'h1' as cg.Key, dest: 'h2' as cg.Key, brush: 'green' };
        ctrl.chessground.setAutoShapes([drawing]);
        await queue(ctrl);
        choose(el, 'n-piece');
        expect(ctrl.chessground.state.drawable.autoShapes).toHaveLength(2);
        ctrl.promotion.dismiss();
        expect(ctrl.chessground.state.drawable.autoShapes).toEqual([drawing]);
    });
});
