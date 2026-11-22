import { expect, test } from '@jest/globals';
import { parseHashAllocationFailure } from '../client/analysis/engineFailure';

test('recognizes fatal hash-allocation output without UCI info prefix', () => {
    expect(parseHashAllocationFailure('Failed to allocate 512MB for transposition table.')).toBe(512);
    expect(parseHashAllocationFailure('Failed to allocate 64MB for transposition table.')).toBe(64);
    expect(parseHashAllocationFailure('info string ERROR: engine terminated')).toBeUndefined();
    expect(parseHashAllocationFailure('info depth 12')).toBeUndefined();
});
