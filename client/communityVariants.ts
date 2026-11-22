import { _ } from './i18n';
import { Chessground } from 'chessgroundx/chessground';

import { boardSettings } from './boardSettings';
import { bindBoardResize } from './miniBoard';
import { ensureCataloguedVariantsLoaded, VARIANTS } from './variants';

type ChessgroundFactory = typeof Chessground;
type MiniBoardResizeBinder = typeof bindBoardResize;
type CataloguedStartBoardMount = {
    chessground: ReturnType<ChessgroundFactory>;
    unbindResize: ReturnType<MiniBoardResizeBinder>;
};

const cataloguedStartBoardMounts = new WeakMap<HTMLElement, CataloguedStartBoardMount>();

async function mountCataloguedStartBoard(
    preview: HTMLElement,
    createChessground: ChessgroundFactory,
    bindResize: MiniBoardResizeBinder,
): Promise<void> {
    if (preview.dataset.chessgroundMounted === 'true') return;

    const variantName = preview.dataset.variant;
    if (variantName && !VARIANTS[variantName]) {
        try {
            await ensureCataloguedVariantsLoaded([variantName]);
        } catch (error) {
            console.warn(`Failed to load the ${variantName} starting position`, error);
            return;
        }
        if (!preview.isConnected || preview.dataset.chessgroundMounted === 'true') return;
    }
    const variant = variantName ? VARIANTS[variantName] : undefined;
    if (!variant?.startFen) return;

    preview.classList.add(variant.boardFamily, variant.pieceFamily);
    if (variant.ui.boardMark) preview.classList.add(variant.ui.boardMark);
    if (variant.pocket) {
        preview.classList.add('with-pockets');
        preview.style.setProperty('--catalogued-board-ranks', String(variant.board.dimensions.height));
    }

    const boardWrap = document.createElement('div');
    boardWrap.classList.add('cg-wrap', variant.board.cg, 'mini');
    if (preview instanceof HTMLAnchorElement) boardWrap.setAttribute('aria-hidden', 'true');
    else {
        boardWrap.setAttribute('role', 'img');
        boardWrap.setAttribute('aria-label', preview.dataset.label || _('Default starting position'));
    }
    preview.appendChild(boardWrap);

    try {
        boardSettings.updateScopedBoardStyle(variant, boardWrap);
        boardSettings.updateScopedPieceStyle(variant, boardWrap, variant.startFen);
        const chessground = createChessground(boardWrap, {
            fen: variant.startFen,
            dimensions: variant.board.dimensions,
            coordinates: false,
            viewOnly: true,
            addDimensionsCssVarsTo: preview,
            pocketRoles: variant.pocket?.roles,
            animation: { enabled: false },
        });
        const unbindResize = bindResize(chessground);
        cataloguedStartBoardMounts.set(preview, { chessground, unbindResize });
        preview.dataset.chessgroundMounted = 'true';
    } catch (error) {
        boardWrap.remove();
        preview.classList.remove(variant.boardFamily, variant.pieceFamily);
        preview.classList.remove('with-pockets');
        preview.style.removeProperty('--catalogued-board-ranks');
        if (variant.ui.boardMark) preview.classList.remove(variant.ui.boardMark);
        console.warn(`Failed to render the ${variant.name} starting position`, error);
    }
}

function disposeCataloguedStartBoard(preview: HTMLElement): void {
    const mount = cataloguedStartBoardMounts.get(preview);
    if (!mount) return;

    mount.unbindResize();
    mount.chessground.destroy();
    cataloguedStartBoardMounts.delete(preview);
    delete preview.dataset.chessgroundMounted;
}

export function mountCataloguedStartBoards(
    assetURL = '',
    createChessground: ChessgroundFactory = Chessground,
    bindResize: MiniBoardResizeBinder = bindBoardResize,
): void {
    boardSettings.assetURL = assetURL;
    const previews = document.querySelectorAll<HTMLElement>('.catalogued-start-board-preview');
    if (!('IntersectionObserver' in window)) {
        previews.forEach(preview => { void mountCataloguedStartBoard(preview, createChessground, bindResize); });
        return;
    }

    const observer = new IntersectionObserver(
        entries => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                const preview = entry.target;
                if (!(preview instanceof HTMLElement)) return;
                observer.unobserve(preview);
                void mountCataloguedStartBoard(preview, createChessground, bindResize);
            });
        },
        { rootMargin: '256px 0px' },
    );
    previews.forEach(preview => observer.observe(preview));
}

function setFavoriteButton(button: HTMLButtonElement, favorite: boolean): void {
    button.classList.toggle('is-favorite', favorite);
    button.setAttribute('aria-pressed', favorite ? 'true' : 'false');
    const label = favorite ? _('Remove from favorites') : _('Add to favorites');
    button.setAttribute('aria-label', label);
    button.setAttribute('title', label);
    button.textContent = favorite ? '♥' : '♡';

    const card = button.closest('.community-variant-card');
    if (card) card.classList.toggle('community-variant-card--favorite', favorite);
}

async function favoriteVariant(button: HTMLButtonElement): Promise<void> {
    const name = button.dataset.variant;
    if (!name || button.classList.contains('is-busy')) return;

    const favorite = button.getAttribute('aria-pressed') !== 'true';
    button.classList.add('is-busy');
    button.disabled = true;

    try {
        const response = await fetch(`/api/catalogued-variants/${encodeURIComponent(name)}/favorite`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ favorite }),
        });
        if (!response.ok) {
            const text = await response.text();
            throw new Error(text || _('Failed to update favorite'));
        }
        const payload = (await response.json()) as { favorite?: boolean; favoriteCount?: number };
        const savedFavorite = !!payload.favorite;
        setFavoriteButton(button, savedFavorite);
        const favoriteCount = button
            .closest('.community-variant-card')
            ?.querySelector<HTMLElement>('.community-variant-favorite-count');
        if (favoriteCount && typeof payload.favoriteCount === 'number') {
            favoriteCount.textContent = String(payload.favoriteCount);
        }

        const page = document.querySelector<HTMLElement>('.community-variants-page');
        if (page?.dataset.favoritesOnly === '1' && !savedFavorite) {
            const card = button.closest('.community-variant-card');
            card?.querySelectorAll<HTMLElement>('.catalogued-start-board-preview').forEach(disposeCataloguedStartBoard);
            card?.remove();
        }
    } catch (err) {
        const message = err instanceof Error ? err.message : _('Failed to update favorite');
        button.setAttribute('title', message);
        console.warn(message);
    } finally {
        button.classList.remove('is-busy');
        button.disabled = false;
    }
}

export function initCommunityVariantFavorites(assetURL = ''): void {
    mountCataloguedStartBoards(assetURL);
    const page = document.querySelector('.community-variants-page');
    if (!page) return;

    page.addEventListener('click', event => {
        const target = event.target as HTMLElement | null;
        const button = target?.closest<HTMLButtonElement>('button.community-variant-favorite');
        if (!button) return;
        event.preventDefault();
        void favoriteVariant(button);
    });
}
