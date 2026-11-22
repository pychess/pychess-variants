import { ExternalEngineError } from './externalSearchBackend';

/** Match Fishnet's minimal definition chain; unrelated/hidden definitions stay out. */
export function externalRulesIni(allIni: string, engineVariant: string): string | undefined {
    const headers = [...allIni.matchAll(/^\[([A-Za-z0-9_-]+)(?::([A-Za-z0-9_-]+))?\][ \t]*\r?$/gm)];
    const definitions = new Map<string, { base?: string; ini: string }>();
    headers.forEach((header, index) => {
        if (definitions.has(header[1])) throw new ExternalEngineError('rules_mismatch');
        definitions.set(header[1], {
            base: header[2],
            ini: allIni.slice(header.index, headers[index + 1]?.index ?? allIni.length).trim(),
        });
    });
    const chain: string[] = [];
    const seen = new Set<string>();
    let name: string | undefined = engineVariant;
    while (name) {
        if (seen.has(name) || seen.size >= 64) throw new ExternalEngineError('rules_mismatch');
        seen.add(name);
        const definition = definitions.get(name);
        if (!definition) break;
        chain.push(definition.ini);
        name = definition.base;
    }
    return chain.length ? chain.reverse().join('\n') + '\n' : undefined;
}

export async function hashExternalRules(ini: string): Promise<{ ini: string; sha256: string }> {
    const bytes = new TextEncoder().encode(ini);
    if (bytes.length > 64 * 1024) throw new ExternalEngineError('invalid_rules');
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    return { ini, sha256: [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('') };
}
