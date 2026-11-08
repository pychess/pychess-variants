import { afterEach, expect, test } from '@jest/globals';
import * as util from 'chessgroundx/util';

import { initPieceRow } from '../client/editor/pieceRow';
import type { EditorController } from '../client/editor/editorCtrl';
import { registerCataloguedVariant, unregisterCataloguedVariant, VARIANTS } from '../client/variants';

const name = 'editor-shogi-palette';
const pieces = ['k', 'q', 'r', 'b', 'n', 'p', 'l', 's', 'g'] as const;

afterEach(() => {
    unregisterCataloguedVariant(name);
    document.body.textContent = '';
});

test.each([false, true])(
    'Shogi editor aligns promoted pieces when the final base piece cannot promote (flipped: %s)',
    flipped => {
        registerCataloguedVariant({
            name,
            displayName: 'Editor Shogi Palette',
            ini: '',
            source: 'fairy-stockfish-builtin',
            fsfBuiltinVariant: 'okisakishogi',
            baseVariant: '',
            clientVariant: 'shogi',
            width: 10,
            height: 10,
            startFen: 'lnsgkqgsnl/1r6b1/pppppppppp/10/10/10/10/PPPPPPPPPP/1B6R1/LNSGQKGSNL[-] w 0 1',
            pieces: [...pieces],
            kingRoles: ['k'],
            promotionType: 'shogi',
            promotionRoles: ['p', 'l', 'n', 's', 'b', 'r'],
            promotionOrder: ['+', ''],
        });
        const ctrl = {
            variant: VARIANTS[name],
            mycolor: 'white',
            oppcolor: 'black',
            flipped: () => flipped,
        } as EditorController;
        document.body.innerHTML = '<div id="pieces0"></div><div id="pieces1"></div>';
        initPieceRow(ctrl, document.getElementById('pieces0')!, document.getElementById('pieces1')!);

        for (const position of ['top', 'bottom']) {
            const row = document.querySelector(`.editor.${position}`) as HTMLElement;
            const roles = Array.from(row.children).map(
                square => square.querySelector('piece')?.getAttribute('data-role') ?? '',
            );
            expect(roles).toEqual([
                ...pieces.map(util.roleOf),
                '',
                '',
                '',
                'pr-piece',
                'pb-piece',
                'pn-piece',
                'pp-piece',
                'pl-piece',
                'ps-piece',
                '',
            ]);
            expect(row.style.getPropertyValue('--piecerows')).toBe('2');
            const color = position === 'top' ? (flipped ? 'white' : 'black') : flipped ? 'black' : 'white';
            const orientation = flipped ? 'black' : 'white';
            for (const piece of row.querySelectorAll('piece')) {
                expect(piece.getAttribute('data-color')).toBe(color);
                expect(piece.classList.contains(color === orientation ? 'ally' : 'enemy')).toBe(true);
            }
        }
    },
);
