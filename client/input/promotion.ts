import { h, toVNode, VNode } from 'snabbdom';

import * as util from 'chessgroundx/util';
import * as cg from 'chessgroundx/types';

import { CGMove, PromotionSuffix, UCIMove, unpromotedRole, promotionSuffix, uci2cg } from '@/chess';
import type { DrawShape } from 'chessgroundx/draw';
import { patch, bind } from '@/document';
import { GameController } from '@/gameCtrl';
import { ExtraInput } from './input';

type PromotionChoices = Partial<Record<cg.Role, PromotionSuffix>>;
type QueuedPromotion = {
    piece: cg.Piece;
    orig: cg.Orig;
    dest: cg.Key;
    meta?: cg.SetPremoveMetadata;
    suffix?: PromotionSuffix;
};

function matchesMove(move: string, orig: cg.Orig, dest: cg.Key): boolean {
    const prefix = orig + dest;
    return move.startsWith(prefix) || (util.isDropOrig(orig) && move.startsWith('+' + prefix));
}

export class PromotionInput extends ExtraInput {
    private choices: PromotionChoices;
    private queued?: QueuedPromotion;
    private preview?: DrawShape;
    private selectionId = 0;
    private vnode?: VNode;

    constructor(ctrl: GameController) {
        super(ctrl);
        this.type = 'promotion';
        this.choices = {};
    }

    start(piece: cg.Piece, orig: cg.Orig, dest: cg.Key, meta: cg.MoveMetadata): void {
        const queued =
            meta.premove && this.queued?.orig === orig && this.queued.dest === dest ? this.queued : undefined;
        this.dismiss();
        meta = { ...meta, ctrlKey: meta.ctrlKey ?? queued?.meta?.ctrlKey };
        this.data = { piece, orig, dest, meta };

        // in 960 castling case (king takes rook) dest piece may be undefined
        if (this.ctrl.chessground.state.boardState.pieces.get(dest) === undefined) {
            this.next('');
            return;
        }

        const choices = this.promotionChoices(piece, orig, dest);
        if (queued?.suffix !== undefined) {
            const role = (Object.keys(choices) as cg.Role[]).find(role => choices[role] === queued.suffix);
            if (role) {
                this.choices = choices;
                this.finish(role);
            } else this.cancel(); // The actual reply can invalidate a choice available in the preview.
            return;
        }
        this.choose(choices, meta.ctrlKey);
        // A choice made after our turn starts must charge the time spent choosing it.
        if (Object.keys(this.choices).length > 1) meta.premove = false;
        this.showOrFinish(dest, piece.color);
    }

    preparePremove(orig: cg.Orig, dest: cg.Key, meta?: cg.SetPremoveMetadata): void {
        this.dismiss();
        const color = this.ctrl.chessground.state.movable.color;
        const piece = util.isDropOrig(orig)
            ? color === 'white' || color === 'black'
                ? { role: util.roleOf(orig), color }
                : undefined
            : this.ctrl.chessground.state.boardState.pieces.get(orig);
        const variant = this.ctrl.variant;
        if (
            !piece ||
            !variant.promotion.roles.includes(
                variant.promotion.type === 'shogi' ? unpromotedRole(variant, piece) : piece.role,
            )
        )
            return;
        this.queued = { piece, orig, dest, meta };
        this.refreshPremove();
    }

    refreshPremove(): void {
        const queued = this.queued;
        if (!queued || queued.suffix !== undefined) return;
        const board = this.ctrl.ffishBoard;
        // Immediately after our own move, the engine still awaits the server acknowledgement.
        if (board.turn() === (queued.piece.color === 'white')) return;

        const preview = new this.ctrl.ffish.Board(this.ctrl.engineVariant, board.fen(true), this.ctrl.chess960);
        const suffixes = new Set<PromotionSuffix>();
        try {
            // Look one opponent turn ahead. This keeps regions, optional promotions,
            // capture premoves and position-dependent promotion limits in the engine.
            for (const reply of preview.legalMoves().split(' ').filter(Boolean)) {
                if (!preview.push(reply)) continue;
                for (const move of preview.legalMoves().split(' ')) {
                    const cgMove = uci2cg(move as UCIMove);
                    if (matchesMove(cgMove, queued.orig, queued.dest)) suffixes.add(promotionSuffix(cgMove as CGMove));
                }
                preview.pop();
            }
        } finally {
            preview.delete();
        }
        if (![...suffixes].some(suffix => suffix !== '')) {
            this.drawNoPromo();
            this.choices = {};
            return;
        }
        this.choose(this.choicesForSuffixes(queued.piece, [...suffixes]), queued.meta?.ctrlKey);
        this.showOrFinish(queued.dest, queued.piece.color);
    }

    dismissPremove(): void {
        // Chessground also unsets a premove after executing it. Its promotion input
        // has already taken ownership by then, so leave that live picker alone.
        if (this.queued) this.dismiss();
    }

    dismiss(): void {
        this.selectionId++;
        this.drawNoPromo();
        this.clearPreview();
        this.queued = undefined;
        this.data = undefined;
        this.choices = {};
    }

    private choose(choices: PromotionChoices, disableAutoPromote?: boolean): void {
        const autoSuffix = this.ctrl.variant.promotion.order[0];
        const autoRole =
            this.ctrl.variant.promotion.type === 'shogi' ? undefined : util.roleOf(autoSuffix as cg.Letter);

        if (
            this.ctrl.variant.promotion.autoPromoteable &&
            this.ctrl.autoPromote &&
            !disableAutoPromote &&
            autoRole &&
            autoSuffix &&
            choices[autoRole] === autoSuffix
        )
            this.choices = { [autoRole]: autoSuffix };
        else this.choices = choices;
    }

    private showOrFinish(dest: cg.Key, color: cg.Color): void {
        if (Object.keys(this.choices).length === 0) {
            this.cancel();
            return;
        }
        if (Object.keys(this.choices).length === 1) {
            const role = Object.keys(this.choices)[0] as cg.Role;
            this.finish(role);
        } else {
            this.drawPromo(dest, color);
        }
    }

    private promotionChoices(piece: cg.Piece, orig: cg.Orig, dest: cg.Key): PromotionChoices {
        const possiblePromotions = this.ctrl.legalMoves().filter(move => matchesMove(move, orig, dest));
        return this.choicesForSuffixes(piece, possiblePromotions.map(promotionSuffix));
    }

    private choicesForSuffixes(piece: cg.Piece, suffixes: PromotionSuffix[]): PromotionChoices {
        const variant = this.ctrl.variant;
        const choices: PromotionChoices = {};

        suffixes.forEach(suffix => {
            let role: cg.Role;
            // '+' always denotes the promoted FEN role, including mixed promotion games.
            if (suffix === '+') role = ('p' + piece.role) as cg.Role;
            else if (suffix === '-') role = unpromotedRole(variant, piece);
            else if (suffix === '') role = piece.role;
            else role = util.roleOf(suffix);
            choices[role] = suffix;
        });

        return choices;
    }

    private promote(key: cg.Key, role: cg.Role): void {
        const ground = this.ctrl.chessground;
        const piece = ground.state.boardState.pieces.get(key);
        if (piece && piece.role !== role) {
            ground.setPieces(
                new Map([
                    [
                        key,
                        {
                            color: piece.color,
                            role: role,
                            promoted: true,
                        },
                    ],
                ]),
            );
        }
    }

    private drawPromo(dest: cg.Key, color: cg.Color): void {
        const container = this.ctrl.chessground.state.dom.elements.container;
        const old =
            this.vnode?.elm && container.contains(this.vnode.elm)
                ? this.vnode
                : toVNode(container.querySelector('extension, #extension_choice') as Node);
        this.vnode = patch(old, this.view(dest, color, this.ctrl.chessground.state.orientation));
    }

    private drawNoPromo(): void {
        const container = this.ctrl.chessground.state.dom.elements.container.querySelector('#extension_choice');
        if (container) patch(container, h('extension'));
        this.vnode = undefined;
    }

    private finish(role: cg.Role): void {
        const suffix = this.choices[role];
        if (suffix === undefined) return;
        this.selectionId++;
        if (this.queued) {
            this.queued.suffix = suffix;
            this.drawNoPromo();
            this.clearPreview();
            this.preview = { orig: this.queued.dest, piece: { color: this.queued.piece.color, role }, brush: '' };
            this.ctrl.chessground.setAutoShapes([...this.ctrl.chessground.state.drawable.autoShapes, this.preview]);
            return;
        }
        if (this.data) {
            this.drawNoPromo();
            this.promote(this.data.dest, role);
            if (util.isDropOrig(this.data.orig)) this.dropNext(role);
            else this.next(suffix);
        }
    }

    private dropNext(role: cg.Role): void {
        // Drop promotion is executed by modifying the orig
        if (this.data)
            this.ctrl.processInput(
                this.data.piece,
                util.dropOrigOf(role),
                this.data.dest,
                this.data.meta,
                '',
                'promotion',
            );
        this.data = undefined;
    }

    private cancel(): void {
        const queued = !!this.queued;
        this.dismiss();
        if (queued) this.ctrl.chessground.cancelPremove();
        else this.ctrl.cancelPromotionInput();
    }

    private clearPreview(): void {
        if (!this.preview) return;
        this.ctrl.chessground.setAutoShapes(
            this.ctrl.chessground.state.drawable.autoShapes.filter(shape => shape !== this.preview),
        );
        this.preview = undefined;
    }

    private view(dest: cg.Key, color: cg.Color, orientation: cg.Color): VNode {
        const selectionId = this.selectionId;
        const variant = this.ctrl.variant;
        const width = variant.board.dimensions.width;
        const height = variant.board.dimensions.height;
        const pos = util.key2pos(dest);

        const choices = Object.keys(this.choices) as cg.Role[];
        choices.sort(
            (a, b) =>
                variant.promotion.order.indexOf(this.choices[a]!) - variant.promotion.order.indexOf(this.choices[b]!),
        );

        const direction = color === orientation ? 'bottom' : 'top';
        const leftFile = orientation === 'white' ? pos[0] : width - 1 - pos[0];
        const left = leftFile * (100 / width);
        const topRank = orientation === 'white' ? height - 1 - pos[1] : pos[1];

        const side = color === orientation ? 'ally' : 'enemy';

        return h(
            'div#extension_choice',
            {
                hook: {
                    insert: vnode => {
                        const el = vnode.elm as HTMLElement;
                        el.addEventListener('click', () => {
                            if (selectionId === this.selectionId) this.cancel();
                        });
                        el.addEventListener('contextmenu', e => {
                            e.preventDefault();
                            return false;
                        });
                    },
                },
            },
            choices.map((role, i) => {
                const rank = topRank + (direction === 'bottom' ? i : -i);
                const top = rank * (100 / height);
                return h(
                    'square',
                    {
                        style: { top: top + '%', left: left + '%' },
                        hook: bind(
                            'click',
                            e => {
                                e.stopPropagation();
                                if (selectionId === this.selectionId) this.finish(role as cg.Role);
                            },
                            null,
                        ),
                    },
                    [h(`piece.${role}.${color}.${side}`)],
                );
            }),
        );
    }
}
