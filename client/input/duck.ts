import { h } from 'snabbdom';
import * as cg from 'chessgroundx/types';

import { GameController } from '@/gameCtrl';
import { chatMessage } from '@/chat';
import { ExtraInput } from './input';
import { patch } from '@/document';
import { _ } from '@/i18n';

export class DuckInput extends ExtraInput {
    inputState?: undefined | 'move';
    duckDests: cg.Key[];

    constructor(ctrl: GameController) {
        super(ctrl);
        this.type = 'duck';
        this.inputState = undefined;
        this.duckDests = [];
    }

    private setPlacementActive(active: boolean): void {
        // A Duck turn is sent as one compound move, but is entered in two stages.
        // While active, the normal piece leg exists only on the client and `undo()`
        // cancels that partial input by restoring the current server ply. Reuse the
        // undo slot for that local action until the duck leg completes.
        this.inputState = active ? 'move' : undefined;
        this.ctrl.onDuckInputStateChange(active);

        const undo = document.getElementById('undo') as HTMLElement | null;
        if (!undo) return;
        patch(
            undo,
            active
                ? h(
                      'button#undo',
                      {
                          on: { click: () => this.ctrl.undo() },
                          props: { title: _('Cancel piece move'), type: 'button' },
                      },
                      [h('i', { class: { icon: true, 'icon-reply': true } })],
                  )
                : h('div#undo'),
        );
    }

    cancel(): void {
        // Board navigation and server resyncs can interrupt the turn between its
        // two legs, so clear both the temporary UI and all staged move data.
        this.setPlacementActive(false);
        this.data = undefined;
        this.duckDests = [];
    }

    start(piece: cg.Piece, orig: cg.Orig, dest: cg.Key, meta: cg.MoveMetadata): void {
        this.data = { piece, orig, dest, meta };

        if (!this.ctrl.variant.rules.duck) {
            this.next('');
            return;
        }

        this.duckDests = this.ctrl
            .legalMoves()
            .filter(move => move.includes(orig + dest))
            .map(move => move.slice(-2)) as cg.Key[];

        let duckKey: cg.Key | undefined;
        const pieces = this.ctrl.chessground.state.boardState.pieces;
        for (const [k, p] of pieces) {
            if (p.role === '_-piece') {
                duckKey = k;
                break;
            }
        }

        // Automatically move the duck if a king is captured, as the game is already over
        // This assumes each side only has one king in any duck variant
        if (meta.captured && this.ctrl.variant.kingRoles.includes(meta.captured.role)) {
            this.finish(orig as cg.Key);
            return;
        }

        if (meta.premove) meta.premove = false;
        this.setPlacementActive(true);
        // When the game starts there is no duck piece on the board
        if (!duckKey) {
            duckKey = 'a0';
            this.ctrl.chessground.state.boardState.pieces.set(duckKey, { role: '_-piece', color: 'white' });
            const message = _('Place the duck on an empty square.');
            chatMessage('', message, 'roundchat');
        }
        // Change the duck's color so that it became movable by the player
        this.ctrl.chessground.state.boardState.pieces.get(duckKey)!.color = piece.color;
        this.ctrl.chessground.set({
            turnColor: piece.color,
            movable: {
                dests: new Map([[duckKey, this.duckDests]]),
            },
        });
        this.ctrl.chessground.selectSquare(duckKey, false);
    }

    finish(key: cg.Key): void {
        if (this.duckDests.includes(key) && this.data) {
            this.ctrl.chessground.state.lastMove = [this.data.orig, this.data.dest, key];
            this.setPlacementActive(false);
            this.next(',' + this.data.dest + key);
            this.duckDests = [];
        }
    }
}
