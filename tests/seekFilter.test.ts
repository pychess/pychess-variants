import { expect, test } from '@jest/globals';

import { filterSeeks } from '../client/lobby/seekFilter';
import type { Seek } from '../client/lobbyType';

function makeSeek(variant: string, rated: boolean): Seek {
    return {
        user: 'tester',
        variant,
        color: 'w',
        fen: '',
        base: 1,
        inc: 0,
        byoyomi: 0,
        day: 0,
        chess960: false,
        rated,
        bot: false,
        rating: 1500,
        seekID: Math.random().toString(),
        target: '',
        title: '',
        bugPlayer1: '',
        player2: '',
        bugPlayer2: '',
    };
}

const seeks: Seek[] = [
    makeSeek('chess', true),
    makeSeek('chess', false),
    makeSeek('shogi', true),
    makeSeek('shogi', false),
];

test('no filters keeps every seek', () => {
    expect(filterSeeks(seeks, '', 'all')).toHaveLength(4);
});

test('variant filter alone narrows to that variant', () => {
    const result = filterSeeks(seeks, 'chess', 'all');
    expect(result).toHaveLength(2);
    expect(result.every(seek => seek.variant === 'chess')).toBe(true);
});

test('rated filter alone keeps only rated seeks', () => {
    const result = filterSeeks(seeks, '', 'rated');
    expect(result).toHaveLength(2);
    expect(result.every(seek => seek.rated)).toBe(true);
});

test('casual filter alone keeps only casual seeks', () => {
    const result = filterSeeks(seeks, '', 'casual');
    expect(result).toHaveLength(2);
    expect(result.every(seek => !seek.rated)).toBe(true);
});

// This is the core of issue #648: the two filters must combine (AND), not reset
// each other.
test('variant and rated combine (AND) instead of resetting', () => {
    const result = filterSeeks(seeks, 'chess', 'rated');
    expect(result).toHaveLength(1);
    expect(result[0].variant).toBe('chess');
    expect(result[0].rated).toBe(true);
});

test('variant and casual combine (AND)', () => {
    const result = filterSeeks(seeks, 'shogi', 'casual');
    expect(result).toHaveLength(1);
    expect(result[0].variant).toBe('shogi');
    expect(result[0].rated).toBe(false);
});
