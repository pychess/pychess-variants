import { h } from 'snabbdom';
import { patch } from './document';
import { gameListView, loadGameVariantDefinitions, renderGames, Game } from './profile';
import { renderTimeago } from './datetime';
import { PyChessModel } from './types';
import { _ } from './i18n';
import { boardSettings } from './boardSettings';
import { selectVariant } from './variants';

export function gameSearchView(model: PyChessModel) {
    boardSettings.assetURL = model.assetURL;
    return gameListView(h('div#game-search-sentinel'));
}

export function initGameSearch(model: PyChessModel): void {
    const form = document.getElementById('game-search-form') as HTMLFormElement | null;
    const sentinel = document.getElementById('game-search-sentinel');
    if (!form || !sentinel) return;

    boardSettings.assetURL = model.assetURL;

    const params = new URLSearchParams(window.location.search);
    if (params.get('variant') === 'all') params.delete('variant');
    const variantPlaceholder = document.getElementById('game-search-variant');
    if (variantPlaceholder instanceof Element) {
        patch(
            variantPlaceholder,
            h('div#game-search-variant', [
                selectVariant(
                    'variant',
                    params.get('variant'),
                    () => undefined,
                    () => undefined,
                    [],
                    'all',
                    _('Any variant'),
                ),
            ]),
        );
    }

    const variantSelect = form.elements.namedItem('variant') as HTMLSelectElement | null;
    form.addEventListener('submit', () => {
        if (!variantSelect) return;
        if (variantSelect.selectedIndex !== 0 && variantSelect.value && variantSelect.value !== 'all') return;

        // Native GET form submission must omit the synthetic "Any variant" option.
        variantSelect.disabled = true;
        window.setTimeout(() => {
            variantSelect.disabled = false;
        }, 0);
    });

    const playerRoleNames = ['white', 'black', 'winner', 'loser'];
    params.forEach((value, name) => {
        if (playerRoleNames.includes(name)) return;
        const field = form.elements.namedItem(name) as HTMLInputElement | HTMLSelectElement | null;
        if (!field) return;
        if (field instanceof HTMLInputElement && field.type === 'checkbox') {
            field.checked = value === '1';
        } else {
            field.value = value;
        }
    });

    const playerInputs = ['player1', 'player2'].map(name => form.elements.namedItem(name) as HTMLInputElement | null);
    const playerSelectors = playerRoleNames.map(name => form.elements.namedItem(name) as HTMLSelectElement | null);

    function refreshPlayerSelectors(): void {
        const players: string[] = [];
        const seenPlayers = new Set<string>();
        for (const input of playerInputs) {
            const player = input?.value.trim() || '';
            const key = player.toLowerCase();
            if (player && !seenPlayers.has(key)) {
                players.push(player);
                seenPlayers.add(key);
            }
        }
        for (const select of playerSelectors) {
            if (!select) continue;
            const selected = select.value.toLowerCase();
            select.replaceChildren(new Option(_('Any player'), ''));
            for (const player of players) select.add(new Option(player, player));
            select.value = players.find(player => player.toLowerCase() === selected) || '';
            select.closest('.player-role-row')?.toggleAttribute('hidden', players.length === 0);
        }
    }
    for (const input of playerInputs) input?.addEventListener('input', refreshPlayerSelectors);
    refreshPlayerSelectors();
    for (const role of playerRoleNames) {
        const select = form.elements.namedItem(role) as HTMLSelectElement | null;
        const requested = params.get(role);
        if (select && requested) {
            const option = Array.from(select.options).find(
                candidate => candidate.value.toLowerCase() === requested.toLowerCase(),
            );
            if (option) select.value = option.value;
        }
    }

    let meaningful = false;
    params.forEach((value, key) => {
        if (key !== 'p' && value) meaningful = true;
    });
    if (!meaningful) return;

    let page = 0;
    let loading = false;
    let done = false;
    const error = document.getElementById('game-search-error');
    const resultsHeader = document.getElementById('game-search-results-header');
    const observer = new IntersectionObserver(
        entries => {
            if (!done && !loading && entries.some(entry => entry.isIntersecting)) void load();
        },
        { rootMargin: '200px' },
    );

    async function load(): Promise<void> {
        loading = true;
        const query = new URLSearchParams(params);
        query.set('p', String(page));
        try {
            const response = await fetch(`/api/games/search?${query.toString()}`);
            const data = (await response.json()) as {
                games?: Game[];
                error?: string;
                hasMore?: boolean;
            };
            if (!response.ok || data.error) {
                if (error) error.textContent = data.error || 'Search failed.';
                done = true;
                return;
            }
            resultsHeader?.removeAttribute('hidden');
            const games = data.games || [];
            if (games.length) {
                await loadGameVariantDefinitions(games);
                const oldVNode = document.getElementById('games');
                if (oldVNode instanceof Element) {
                    patch(oldVNode, h('table#games', renderGames(model, games)));
                }
                renderTimeago();
            }
            page += 1;
            done = !data.hasMore;
        } catch {
            if (error) error.textContent = 'Search failed.';
            done = true;
        } finally {
            loading = false;
        }
    }
    observer.observe(sentinel);
}
