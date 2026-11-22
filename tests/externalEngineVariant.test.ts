import { expect, test } from '@jest/globals';
import { read } from 'chessgroundx/fen';
import { moddedVariant } from '../client/variants';

const dimensions = { width: 10, height: 8 } as const;
const root = 'r3k4r/10/10/10/10/10/10/R3K4R b KQkq - 0 1';
const current = '1kr6r/10/10/10/10/10/10/R5RK2 b - - 2 2';

test('Embassy castling profile remains tied to the initial position after kings and rights move', () => {
    const pieces = read(current, dimensions).pieces;
    expect(moddedVariant('capablanca', false, pieces, '-', root)).toBe('embassy');
    expect(moddedVariant('capahouse', false, pieces, '-', root)).toBe('embassyhouse');
    expect(moddedVariant('capablanca', true, pieces, '-', root)).toBe('capablanca');
});

test('ordinary Capablanca and a root without castling keep their original engine identity', () => {
    const capa = 'rnabqkbcnr/pppppppppp/10/10/10/10/PPPPPPPPPP/RNABQKBCNR w KQkq - 0 1';
    const pieces = read(root, dimensions).pieces;
    expect(moddedVariant('capablanca', false, pieces, 'KQkq', capa)).toBe('capablanca');
    expect(moddedVariant('capablanca', false, pieces, 'KQkq', root.replace('KQkq', '-'))).toBe('capablanca');
    expect(moddedVariant('capablanca', false, pieces, 'KQkq')).toBe('embassy');
});
