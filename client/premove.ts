import { createBetzaPremove, type BetzaPremove } from '@pychess/betza';
import { premove } from 'chessgroundx/premove';
import * as cg from 'chessgroundx/types';
import * as util from 'chessgroundx/util';
import { variantsIni } from './variantsIni';

interface PremoveMetadata {
    readonly name: string;
    readonly source?: 'user' | 'fairy-stockfish-builtin';
    readonly ini?: string;
    // Fairy-Stockfish registered-parent inheritance; empty when a built-in
    // starts from an internal variant.cpp helper.
    readonly baseVariant?: string;
    // General pychess compatibility profile. This intentionally preserves
    // client semantics without overloading baseVariant's engine meaning.
    readonly clientVariant?: string;
    // Optional narrower chessground premove fallback.
    readonly premoveVariant?: string;
    readonly betzaPieces?: Readonly<Record<string, string>>;
}

interface PremoveDefinition {
    readonly fallbackVariant?: string;
    readonly movements: ReadonlyMap<string, BetzaPremove>;
    readonly promotedPieceTypes: ReadonlyMap<string, string>;
    readonly kingRoleLetter?: string;
}

interface ParsedIniOption {
    readonly key: string;
    readonly value: string;
}

const cataloguedPremoveDefinitions = new Map<string, PremoveDefinition>();
const sitePremoveDefinitions = new Map<string, PremoveDefinition>();

// Site variants opt in individually; all others retain chessgroundx premoves.
const sitePremoveFallbacks: ReadonlyMap<string, string> = new Map([['yokai', 'shogi']]);

// Named Fairy-Stockfish piece assignments used by the opted-in site variants.
// The king keeps the fallback's variant-specific geometry and castling rules.
const namedPieceBetza: ReadonlyMap<string, string> = new Map([
    ['shogipawn', 'fW'],
    ['gold', 'WfF'],
    ['knight', 'N'],
]);

function sitePremoveDefinition(name: string): PremoveDefinition | undefined {
    const fallback = sitePremoveFallbacks.get(name);
    if (!fallback) return undefined;

    let definition = sitePremoveDefinitions.get(name);
    if (!definition) {
        // The compiler expects one section, not the complete site rules file.
        const ini = variantsIni
            .split(/(?=^\[)/m)
            .find(section => section.startsWith(`[${name}]`) || section.startsWith(`[${name}:`));
        definition = parsePremoveDefinition({ name, ini, premoveVariant: fallback });
        sitePremoveDefinitions.set(name, definition);
    }
    return definition;
}

function iniOptions(ini: string): ParsedIniOption[] {
    const options: ParsedIniOption[] = [];
    for (const line of ini.split(/\r?\n/)) {
        const stripped = line.trim();
        if (!stripped || stripped.startsWith('#') || stripped.startsWith(';') || !stripped.includes('=')) continue;

        const [left, ...right] = stripped.split('=');
        const key = left.trim();
        const value = right.join('=').split('#', 1)[0].split(';', 1)[0].trim();
        if (key) options.push({ key, value });
    }
    return options;
}

function normalRoleLetter(value: string): string | undefined {
    const match = /^(\+?[a-z])$/i.exec(value.trim());
    return match?.[1].toLowerCase();
}

function promotedPieceTypes(options: readonly ParsedIniOption[]): Map<string, string> {
    const result = new Map<string, string>();
    const value = options.find(option => option.key.toLowerCase() === 'promotedpiecetype')?.value;
    if (!value) return result;

    for (const token of value.split(/\s+/)) {
        const match = /^([a-z]):([a-z-])$/i.exec(token);
        if (!match) continue;
        result.set(match[1].toLowerCase(), match[2].toLowerCase());
    }
    return result;
}

function parsePremoveDefinition(meta: PremoveMetadata): PremoveDefinition {
    const options = iniOptions(meta.ini ?? '');
    const movements = new Map<string, BetzaPremove>();
    let kingRoleLetter: string | undefined;

    for (const [roleLetter, betza] of Object.entries(meta.betzaPieces ?? {})) {
        const normalizedRole = normalRoleLetter(roleLetter);
        if (normalizedRole) movements.set(normalizedRole, createBetzaPremove(betza));
    }

    for (const { key, value } of options) {
        const normalizedKey = key.toLowerCase();
        const namedMovement = namedPieceBetza.get(normalizedKey);
        if (namedMovement) {
            const roleLetter = normalRoleLetter(value);
            if (roleLetter) movements.set(roleLetter, createBetzaPremove(namedMovement));
            continue;
        }
        if (!(normalizedKey === 'king' || /^custompiece\d+$/i.test(key)) || value === '-') continue;

        const explicit = /^([a-z]):(.*)$/i.exec(value);
        if (!explicit) continue;
        const roleLetter = explicit[1].toLowerCase();
        movements.set(roleLetter, createBetzaPremove(explicit[2].trim()));
        if (normalizedKey === 'king') kingRoleLetter = roleLetter;
    }

    return {
        fallbackVariant: meta.premoveVariant || meta.clientVariant || meta.baseVariant,
        movements,
        promotedPieceTypes: promotedPieceTypes(options),
        kingRoleLetter,
    };
}

export function registerCataloguedPremove(meta: PremoveMetadata): void {
    // Catalogued registrations have their own lifecycle; permanent site
    // definitions are compiled separately from the shared site rules.
    if (!meta.name) return;
    cataloguedPremoveDefinitions.set(meta.name, parsePremoveDefinition(meta));
}

export function unregisterCataloguedPremove(name: string | undefined | null): void {
    if (name) cataloguedPremoveDefinitions.delete(name);
}

function destinationsForMovement(
    movement: BetzaPremove,
    boardState: cg.BoardState,
    key: cg.Key,
    dimensions: cg.BoardDimensions,
): cg.Key[] {
    const piece = boardState.pieces.get(key);
    if (!piece) return [];

    return movement({
        origin: util.key2pos(key),
        color: piece.color,
        board: dimensions,
    }).map(position => util.pos2key([position[0], position[1]]));
}

function fallbackAsRole(
    fallback: cg.Premove,
    boardState: cg.BoardState,
    key: cg.Key,
    canCastle: boolean,
    roleLetter: string,
): cg.Key[] {
    const piece = boardState.pieces.get(key);
    if (!piece || !normalRoleLetter(roleLetter)) return [];

    const pieces = new Map(boardState.pieces);
    pieces.set(key, { ...piece, role: util.roleOf(roleLetter as cg.Letter) });
    return fallback({ ...boardState, pieces }, key, canCastle);
}

function mergeDestinations(primary: readonly cg.Key[], extra: readonly cg.Key[]): cg.Key[] {
    if (!extra.length) return [...primary];
    return [...new Set([...primary, ...extra])];
}

function specialFallbackDestinations(
    fallback: cg.Premove,
    boardState: cg.BoardState,
    key: cg.Key,
    canCastle: boolean,
    roleLetter?: string,
): cg.Key[] {
    if (!canCastle) return [];

    const withSpecial = roleLetter
        ? fallbackAsRole(fallback, boardState, key, true, roleLetter)
        : fallback(boardState, key, true);
    const withoutSpecial = new Set(
        roleLetter ? fallbackAsRole(fallback, boardState, key, false, roleLetter) : fallback(boardState, key, false),
    );
    return withSpecial.filter(destination => !withoutSpecial.has(destination));
}

export function premoveForVariant(variantName: string, chess960: boolean, dimensions: cg.BoardDimensions): cg.Premove {
    const definition = cataloguedPremoveDefinitions.get(variantName) ?? sitePremoveDefinition(variantName);
    if (!definition) return premove(variantName, chess960, dimensions);

    const fallback = premove(definition.fallbackVariant ?? variantName, chess960, dimensions);
    return (boardState, key, canCastle) => {
        const piece = boardState.pieces.get(key);
        if (!piece) return [];

        const letter = util.letterOf(piece.role).toLowerCase();
        if (letter.startsWith('+')) {
            const source = letter.slice(1);
            const target = definition.promotedPieceTypes.get(source);
            if (target && target !== '-') {
                const promotedMovement = definition.movements.get(target);
                if (promotedMovement) {
                    return mergeDestinations(
                        destinationsForMovement(promotedMovement, boardState, key, dimensions),
                        specialFallbackDestinations(fallback, boardState, key, canCastle, target),
                    );
                }
                return fallbackAsRole(fallback, boardState, key, canCastle, target);
            }
        }

        const movement = definition.movements.get(letter);
        if (movement) {
            return mergeDestinations(
                destinationsForMovement(movement, boardState, key, dimensions),
                specialFallbackDestinations(
                    fallback,
                    boardState,
                    key,
                    canCastle,
                    letter === definition.kingRoleLetter ? 'k' : undefined,
                ),
            );
        }
        return fallback(boardState, key, canCastle);
    };
}
