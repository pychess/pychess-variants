import { describe, expect, test } from '@jest/globals';

import { aiDisplayName, aiLevel, result } from '../client/result';
import { VARIANTS } from '../client/variants';

describe('result text rendering', () => {
    test('does not announce a winner for unresolved unknown-finish results', () => {
        expect(result(VARIANTS.xiangqi, 11, '*')).toBe('Unknown reason');
    });
});

describe('AI display rendering', () => {
    test('labels the built-in AI with the dedicated Alice engine name for Alice games', () => {
        expect(aiDisplayName('Fairy-Stockfish', 'alice')).toBe('Alice-Stockfish');
        expect(aiDisplayName('Fairy-Stockfish', 'chess')).toBe('Fairy-Stockfish');
        expect(aiDisplayName('Random-Mover', 'alice')).toBe('Random-Mover');
    });

    test('shows levels for built-in engine opponents', () => {
        expect(aiLevel('Fairy-Stockfish', 6)).toBe(' level 6');
        expect(aiLevel('Alice-Stockfish', 6)).toBe(' level 6');
        expect(aiLevel('Random-Mover', 0)).toBe('');
    });
});
