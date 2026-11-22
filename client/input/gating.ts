import { h, VNode, toVNode } from 'snabbdom';

import * as util from 'chessgroundx/util';
import * as cg from 'chessgroundx/types';

import { colorCase, promotionSuffix } from '@/chess';
import { GameController } from '@/gameCtrl';
import { patch, bind } from '@/document';
import { ExtraInput } from './input';

export class GatingInput extends ExtraInput {
    private choices: Partial<Record<cg.Key, (cg.Role | '')[]>>;

    constructor(ctrl: GameController) {
        super(ctrl);
        this.type = 'gating';
        this.choices = {};
    }

    /*
     * Seirawan-style gating: a piece from hand may enter on the square vacated
     * by an unmoved back-rank piece, or on the rook square while castling.
     */
    start(piece: cg.Piece, orig: cg.Orig, dest: cg.Key, meta: cg.MoveMetadata): void {
        this.data = { piece, orig, dest, meta };

        if (!this.ctrl.variant.rules.gate || util.isDropOrig(orig) || !this.canGate(orig)) {
            this.next('-'); // The '-' suffix means gating is not initiated and tell the controller to initiate promotion instead
            return;
        }

        this.choices = {};
        this.choices[orig] = this.gatingChoices(orig, dest);

        if (piece.role === 'k-piece' && orig[1] === dest[1]) {
            // Handle castling giving gating choices on two squares
            const rookOrig = this.ctrl.chess960 ? dest : (((dest[0] === 'g' ? 'h' : 'a') + orig[1]) as cg.Key);
            const rookChoices = this.gatingChoices(rookOrig, orig);
            if (rookChoices.length > 0) {
                rookChoices.push(''); // Add the empty choice to the rook square for aesthetics
                this.choices[rookOrig] = rookChoices;
                if (this.choices[orig]!.length <= 1)
                    // Delete the choice from the king's square
                    // if you can gate on the rook's square but not the king's
                    // This is purely for aesthetics
                    delete this.choices[orig];
            }
        }

        const keys = Object.keys(this.choices);
        if (keys.length === 1 && this.choices[keys[0] as cg.Key]!.length === 1)
            // Handle the cases of 960 castling with no possible gating square
            // and S-House moving an unmoved piece with nothing in the pocket
            this.finish(this.choices[keys[0] as cg.Key]![0], orig);
        else {
            if (meta.premove) meta.premove = false;
            this.drawGating(piece.color, this.ctrl.chessground.state.orientation);
        }
    }

    private canGate(orig: cg.Key): boolean {
        const fen = this.ctrl.fullfen;
        const parts = fen.split(' ');
        const castling = parts[2];
        const color = parts[1] === 'w' ? 'white' : 'black';
        const height = this.ctrl.variant.board.dimensions.height;
        const origRank = util.key2pos(orig)[1];
        const gateRank = color === 'white' ? 0 : height - 1;
        if (origRank === gateRank) {
            if (castling.includes(colorCase(color, orig[0]))) {
                return true;
            }
            if (!this.ctrl.chess960) {
                // In non-960, if both the king and the corresponding rook haven't moved,
                // the virginity of BOTH pieces will be encoded in the castling right
                if (orig[0] === 'e' || orig[0] === 'h') if (castling.includes(colorCase(color, 'K'))) return true;
                if (orig[0] === 'e' || orig[0] === 'a') if (castling.includes(colorCase(color, 'Q'))) return true;
            }
        }
        return false;
    }

    private gatingChoices(orig: cg.Key, dest: cg.Key): (cg.Role | '')[] {
        const possibleGating = this.ctrl.legalMoves().filter(move => move.includes(orig + dest));
        return possibleGating.map(promotionSuffix).map(s => (s === '' ? '' : util.roleOf(s as cg.Letter)));
    }

    private gate(piece: cg.Piece, key: cg.Key): void {
        this.ctrl.chessground.newPiece(piece, key, true);
    }

    private drawGating(color: cg.Color, orientation: cg.Color): void {
        const container = toVNode(document.querySelector('extension') as Node);
        patch(container, this.view(color, orientation));
    }

    private drawNoGating(): void {
        const container = document.getElementById('extension_choice') as HTMLElement;
        if (container) patch(container, h('extension'));
    }

    private finish(role: cg.Role | '', key: cg.Key): void {
        if (this.data) {
            console.log(role, key);
            this.drawNoGating();
            const letter = role === '' ? '' : util.letterOf(role);
            if (role === '') {
                this.next('');
            } else {
                this.gate({ role: role, color: this.data.piece.color }, key);
                if (key === this.data.orig) this.next(letter);
                else this.castlingNext(letter, key);
            }
            this.choices = {};
        }
    }

    skipGating(): void {
        if (this.data) {
            this.finish('', this.data.dest);
        }
    }

    private castlingNext(suffix: string, key: cg.Key): void {
        // Handle gating on the rook's square in castling
        if (this.data)
            this.ctrl.processInput(this.data.piece, key, this.data.orig as cg.Key, this.data.meta, suffix, this.type);
        this.data = undefined;
    }

    private cancel(): void {
        this.drawNoGating();
        this.ctrl.goPly(this.ctrl.ply);
    }

    private squareView(orig: cg.Key, color: cg.Color, orientation: cg.Color): VNode[] {
        const width = this.ctrl.variant.board.dimensions.width;
        const height = this.ctrl.variant.board.dimensions.height;
        const leftFile = util.key2pos(orig)[0];
        const left = (orientation === 'white' ? leftFile : width - 1 - leftFile) * (100 / width);
        return this.choices[orig]!.map((role, i) => {
            const top = (color === orientation ? height - 1 - i : i) * (100 / height);
            console.log(role, orig);
            return h(
                'square',
                {
                    style: { top: top + '%', left: left + '%' },
                    hook: bind(
                        'click',
                        e => {
                            e.stopPropagation();
                            this.finish(role, orig);
                        },
                        null,
                    ),
                },
                [h('piece.' + role + '.' + color)],
            );
        });
    }

    private view(color: cg.Color, orientation: cg.Color): VNode {
        const direction = color === orientation ? 'top' : 'bottom';
        let squares: VNode[] = [];
        const pocket = this.ctrl.variant.pocket!.roles[color];
        let orig: cg.Key;
        for (orig in this.choices) {
            this.choices[orig]!.sort((a, b) => pocket.indexOf(a as cg.Role) - pocket.indexOf(b as cg.Role));
            squares.push(...this.squareView(orig, color, orientation));
        }
        return h(
            'div#extension_choice.' + direction,
            {
                hook: {
                    insert: vnode => {
                        const el = vnode.elm as HTMLElement;
                        el.addEventListener('click', () => this.cancel());
                        el.addEventListener('contextmenu', e => {
                            e.preventDefault();
                            return false;
                        });
                    },
                },
            },
            squares,
        );
    }
}
