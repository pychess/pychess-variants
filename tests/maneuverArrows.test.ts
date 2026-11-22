import { describe, expect, test } from '@jest/globals';
import { maneuverArrows } from '../client/analysis/maneuverArrows';

describe('maneuver arrows', () => {
    test('follows consecutive moves of the first PV piece across opponent replies', () => {
        expect(maneuverArrows('g1f3 d7d5 f3e5 c7c6 e5d3')).toEqual([
            { orig: 'f3', dest: 'e5', brush: 'paleGreen', modifiers: { lineWidth: 6 } },
            { orig: 'e5', dest: 'd3', brush: 'paleGreen', modifiers: { lineWidth: 6 } },
        ]);
    });
    test('stops when another friendly piece moves, even if the original returns later', () => {
        expect(maneuverArrows('g1f3 d7d5 c2c4 d5c4 f3e5')).toEqual([]);
        expect(maneuverArrows('g1f3 d7d5 f3e5 c7c6 c2c4 d5c4 e5d3')).toEqual([
            { orig: 'f3', dest: 'e5', brush: 'paleGreen', modifiers: { lineWidth: 6 } },
        ]);
    });
    test('limits the maneuver to three arrows total, including the initial arrow', () => {
        expect(maneuverArrows('g1f3 a7a6 f3e5 a6a5 e5d3 a5a4 d3c5')).toHaveLength(2);
    });
    test('rejects paths overlapping previously drawn arrows', () => {
        expect(maneuverArrows('g1f3 a7a6 f3g1 a6a5')).toEqual([]);
    });
    test('does not trace drops or promotions', () => {
        expect(maneuverArrows('P@e4 e7e5 e4e5')).toEqual([]);
        expect(maneuverArrows('e7e8q a7a6 e8e7')).toEqual([]);
    });
});
