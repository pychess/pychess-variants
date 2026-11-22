import { allVariantsIni } from '../variants';
import { hashExternalRules } from '../analysis/externalRules';
import { ExternalEngineError } from '../analysis/externalSearchBackend';

/** Prepare without touching the active chapter; apply only after navigation is verified. */
export async function buildStudyEngineRules(
    variant: string,
    baseIni: string,
    documents?: readonly unknown[],
): Promise<{ variant: string; engineVariant: string; ini: string }> {
    const sources = documents
        ? [
              baseIni,
              ...documents.flatMap(doc =>
                  doc !== null && typeof doc === 'object' && 'ini' in doc && typeof doc.ini === 'string'
                      ? [doc.ini]
                      : [],
              ),
          ]
        : [allVariantsIni(baseIni)];
    const definitions = new Map<string, { base?: string; ini: string }>();
    for (const source of sources) {
        const headers = [...source.matchAll(/^\[([A-Za-z0-9_-]+)(?::([A-Za-z0-9_-]+))?\][ \t]*\r?$/gm)];
        headers.forEach((header, index) => {
            // The selected saved snapshot replaces its live metadata in the response.
            // It also takes precedence over a checked-in definition with that name.
            definitions.set(header[1], {
                base: header[2],
                ini: source.slice(header.index, headers[index + 1]?.index ?? source.length).trim(),
            });
        });
    }
    const chain: Array<{ name: string; ini: string }> = [];
    const seen = new Set<string>();
    let name: string | undefined = variant;
    while (name) {
        if (seen.has(name) || seen.size >= 64) throw new ExternalEngineError('rules_mismatch');
        seen.add(name);
        const definition = definitions.get(name);
        if (!definition) break;
        chain.unshift({ name, ini: definition.ini });
        name = definition.base;
    }
    if (!chain.length) throw new ExternalEngineError('rules_mismatch');
    const aliases = new Map<string, string>();
    for (let index = 0; index < chain.length; index++) {
        const scoped =
            chain
                .slice(0, index + 1)
                .map(section => section.ini)
                .join('\n') + '\n';
        const { sha256 } = await hashExternalRules(scoped);
        aliases.set(chain[index].name, 'studysnap_' + sha256.slice(0, 20));
    }
    const ini =
        chain
            .map(section => section.ini)
            .join('\n')
            .replace(
                /^\[([^\]:]+)(?::([^\]]+))?\]/gm,
                (_header, key: string, base?: string) =>
                    `[${aliases.get(key) ?? key}${base ? ':' + (aliases.get(base) ?? base) : ''}]`,
            ) + '\n';
    return { variant, engineVariant: aliases.get(variant)!, ini };
}
