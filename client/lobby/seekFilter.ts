import type { Seek } from '../lobbyType';

export type SeekRatedFilter = 'all' | 'rated' | 'casual';

// Keep '' as the "no variant filter" sentinel so it lines up with the empty
// option emitted by selectVariant() in the lobby UI.
export function filterSeeks(
    seeks: Seek[],
    variantFilter: string,
    ratedFilter: SeekRatedFilter,
): Seek[] {
    return seeks.filter(seek => {
        if (variantFilter !== '' && seek.variant !== variantFilter) {
            return false;
        }
        if (ratedFilter === 'rated' && !seek.rated) {
            return false;
        }
        if (ratedFilter === 'casual' && seek.rated) {
            return false;
        }
        return true;
    });
}
