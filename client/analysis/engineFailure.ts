/** Fatal hash-allocation diagnostics may be emitted as plain engine output, not UCI info. */
export function parseHashAllocationFailure(line: string): number | undefined {
    const match = /^Failed to allocate (\d+)MB for transposition table\.$/.exec(line.trim());
    return match ? Number(match[1]) : undefined;
}

