import { jest } from '@jest/globals';
import { infiniteScroll, initInfiniteScroll } from '@/infiniteScroll';

let observers: Observer[];
class Observer {
    callback: IntersectionObserverCallback;
    observe = jest.fn();
    unobserve = jest.fn();
    disconnect = jest.fn();
    constructor(callback: IntersectionObserverCallback) {
        this.callback = callback;
        observers.push(this);
    }
    intersect(): void {
        this.callback([{ isIntersecting: true } as IntersectionObserverEntry], this as unknown as IntersectionObserver);
    }
}

const flush = async (): Promise<void> => {
    for (let i = 0; i < 12; i++) await Promise.resolve();
};

beforeEach(() => {
    jest.useFakeTimers();
    observers = [];
    window.IntersectionObserver = Observer as unknown as typeof IntersectionObserver;
    document.body.innerHTML = '<div id="sentinel"></div>';
});

afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
});

test('serializes requests and re-observes short pages, then stops at the end', async () => {
    let resolve!: (hasMore: boolean) => void;
    const load = jest.fn(
        () =>
            new Promise<boolean>(res => {
                resolve = res;
            }),
    );
    infiniteScroll(document.getElementById('sentinel')!, { load });
    observers[0].intersect();
    observers[0].intersect();
    expect(load).toHaveBeenCalledTimes(1);
    resolve(true);
    await flush();
    jest.advanceTimersByTime(500);
    expect(observers[0].observe).toHaveBeenCalledTimes(2);
    observers[0].intersect();
    resolve(false);
    await flush();
    expect(observers[0].disconnect).toHaveBeenCalledTimes(1);
    observers[0].intersect();
    expect(load).toHaveBeenCalledTimes(2);
});

test('pauses on errors and lets the user retry the same load', async () => {
    jest.spyOn(console, 'warn').mockImplementation(() => {});
    const load = jest.fn<() => Promise<boolean>>().mockRejectedValueOnce(new Error('offline')).mockResolvedValue(false);
    const sentinel = document.getElementById('sentinel')!;
    infiniteScroll(sentinel, { load });
    observers[0].intersect();
    await flush();
    expect(sentinel.querySelector('button')!.hidden).toBe(false);
    expect(observers[0].observe).toHaveBeenCalledTimes(1);
    observers[0].intersect();
    expect(load).toHaveBeenCalledTimes(1);
    sentinel.querySelector('button')!.click();
    await flush();
    expect(load).toHaveBeenCalledTimes(2);
    expect(sentinel.querySelector('button')!.hidden).toBe(true);
});

test('destroy cancels pending observation after a request', async () => {
    const destroy = infiniteScroll(document.getElementById('sentinel')!, { load: async () => true });
    observers[0].intersect();
    await flush();
    destroy();
    jest.advanceTimersByTime(500);
    expect(observers[0].observe).toHaveBeenCalledTimes(1);
});

function listPage(entries: string, next = ''): string {
    return `<main data-infinite-scroll="test">
        <table><tbody data-infinite-scroll-content>${entries}</tbody></table>
        <nav data-infinite-scroll-pager>${next ? `<a rel="next" href="${next}">Next</a>` : ''}</nav>
    </main>`;
}
const row = (id: string): string => `<tr data-infinite-scroll-key="${id}"><td>${id}</td></tr>`;

test('appends only list entries, keeps query filters, deduplicates, and ends without another request', async () => {
    document.body.innerHTML = listPage(row('one'), '/list?author=alice&page=2');
    const fetchMock = jest.fn<typeof fetch>().mockResolvedValue({
        ok: true,
        text: async () => listPage(row('one') + row('two')),
    } as Response);
    window.fetch = fetchMock;
    const loaded = jest.fn();
    initInfiniteScroll(loaded);
    initInfiniteScroll(loaded);
    expect(observers).toHaveLength(1);
    observers[0].intersect();
    await flush();
    expect(fetchMock).toHaveBeenCalledWith(`${window.location.origin}/list?author=alice&page=2`);
    expect([...document.querySelectorAll('td')].map(el => el.textContent)).toEqual(['one', 'two']);
    expect(document.querySelectorAll('main')).toHaveLength(1);
    expect(loaded).toHaveBeenCalledTimes(1);
    expect(observers[0].disconnect).toHaveBeenCalled();
});

test('keeps the next link for navigation when loading fails or returns a login page', async () => {
    jest.spyOn(console, 'warn').mockImplementation(() => {});
    document.body.innerHTML = listPage(row('one'), '/list?page=2');
    window.fetch = jest
        .fn<typeof fetch>()
        .mockResolvedValue({ ok: true, text: async () => '<main>Sign in</main>' } as Response);
    initInfiniteScroll(() => {});
    observers[0].intersect();
    await flush();
    const pager = document.querySelector<HTMLElement>('nav')!;
    expect(pager.style.display).toBe('');
    expect(pager.querySelector('a')!.getAttribute('href')).toBe('/list?page=2');
    expect(document.querySelectorAll('td')).toHaveLength(1);
});

test('leaves ordinary navigation available without IntersectionObserver', () => {
    Reflect.deleteProperty(window, 'IntersectionObserver');
    document.body.innerHTML = listPage(row('one'), '/list?page=2');
    initInfiniteScroll(() => {});
    expect(document.querySelector<HTMLElement>('nav')!.style.display).toBe('');
});
