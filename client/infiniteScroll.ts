import { _ } from './i18n';

interface InfiniteScrollOptions {
    // Resolve to false after the last page. Reject to offer a manual retry.
    load: () => Promise<boolean>;
    onError?: () => void;
}

/** Shared request scheduling for HTML lists and JSON-backed views. */
export function infiniteScroll(sentinel: HTMLElement, options: InfiniteScrollOptions): () => void {
    let loading = false;
    let stopped = false;
    let failed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const status = document.createElement('span');
    status.setAttribute('role', 'status');
    const retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'button';
    retry.textContent = _('Load more');
    retry.hidden = true;
    sentinel.style.minHeight = '1px';
    sentinel.append(status, retry);

    const observer =
        'IntersectionObserver' in window
            ? new IntersectionObserver(
                  entries => {
                      if (entries.some(entry => entry.isIntersecting)) void load();
                  },
                  { rootMargin: '200px' },
              )
            : undefined;

    const destroy = (): void => {
        stopped = true;
        observer?.disconnect();
        clearTimeout(timer);
    };

    async function load(): Promise<void> {
        if (loading || stopped || failed) return;
        if (!sentinel.isConnected) return destroy();
        loading = true;
        observer?.unobserve(sentinel);
        retry.hidden = true;
        status.textContent = _('Loading...');
        sentinel.setAttribute('aria-busy', 'true');
        try {
            const hasMore = await options.load();
            if (stopped) return;
            status.textContent = '';
            if (!hasMore) destroy();
            else if (observer) {
                // Re-observing also fills short pages whose sentinel never left view.
                // Pace those requests so a tall viewport cannot cause a burst.
                timer = setTimeout(() => {
                    if (!sentinel.isConnected) destroy();
                    else if (!stopped) observer.observe(sentinel);
                }, 500);
            } else retry.hidden = false;
        } catch (error) {
            if (stopped) return;
            failed = true;
            console.warn('Failed to load the next page', error);
            status.textContent = _('Request failed');
            if (options.onError) options.onError();
            else retry.hidden = false;
        } finally {
            loading = false;
            sentinel.removeAttribute('aria-busy');
        }
    }

    retry.addEventListener('click', () => {
        failed = false;
        void load();
    });
    if (observer) observer.observe(sentinel);
    else if (options.onError) options.onError();
    else retry.hidden = false;
    return destroy;
}

const initialized = new WeakSet<HTMLElement>();

/** Adapted from lichess ui/bits/src/bits.infiniteScroll.ts (AGPL-3.0).
 * Keep real paginated URLs as a fallback and append only the next list's entries.
 */
export function initInfiniteScroll(onContentLoaded: () => void): void {
    document.querySelectorAll<HTMLElement>('[data-infinite-scroll]').forEach(root => {
        if (initialized.has(root)) return;
        const content = root.querySelector<HTMLElement>('[data-infinite-scroll-content]');
        const pager = root.querySelector<HTMLElement>('[data-infinite-scroll-pager]');
        const nextLink = (): HTMLAnchorElement | null => pager?.querySelector('a[rel="next"]') ?? null;
        if (!content || !pager || !nextLink()) return;
        if (!('IntersectionObserver' in window)) return;
        initialized.add(root);
        const sentinel = document.createElement('div');
        pager.before(sentinel);
        pager.style.display = 'none';
        const visited = new Set<string>([window.location.href]);
        const keys = new Set(Array.from(content.children, entry => entry.getAttribute('data-infinite-scroll-key')));
        infiniteScroll(sentinel, {
            load: async () => {
                const href = nextLink()?.href;
                if (!href) return false;
                const url = new URL(href, window.location.href);
                if (url.origin !== window.location.origin || visited.has(url.href))
                    throw new Error('Invalid next page URL');
                const response = await fetch(url.href);
                if (!response.ok) throw new Error(`Next page: ${response.status}`);
                const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
                const nextRoot = doc.querySelector(`[data-infinite-scroll="${root.dataset.infiniteScroll}"]`);
                const nextContent = nextRoot?.querySelector('[data-infinite-scroll-content]');
                if (!nextContent) throw new Error('Next page is missing its list');
                const entries = Array.from(nextContent.children);
                for (const entry of entries) {
                    const key = entry.getAttribute('data-infinite-scroll-key');
                    if (key && keys.has(key)) continue;
                    if (key) keys.add(key);
                    content.append(document.importNode(entry, true));
                }
                const nextPager = nextRoot?.querySelector('[data-infinite-scroll-pager]');
                pager.replaceChildren(
                    ...Array.from(nextPager?.childNodes ?? [], node => document.importNode(node, true)),
                );
                visited.add(url.href);
                onContentLoaded();
                return entries.length > 0 && !!nextLink();
            },
            onError: () => {
                pager.style.display = '';
            },
        });
    });
}
