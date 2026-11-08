import { jest } from '@jest/globals';
import { patch } from '../client/document';
import { forumView } from '../client/forum';
import type { PyChessModel } from '../client/types';

let observers: Observer[];
let fetchMock: ReturnType<typeof jest.fn<typeof fetch>>;
let originalFetch: typeof fetch;
let originalObserver: typeof IntersectionObserver;

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

function response(payload: unknown, status = 200): Response {
    return { status, text: async () => JSON.stringify(payload) } as Response;
}

function result(id: string) {
    return {
        post: { _id: id, user: 'alice', text: `Post ${id}`, createdAt: '2026-11-08T00:00:00Z' },
        topic: { _id: 'topic1', slug: 'hello', name: 'Hello' },
        categ: { _id: 'feedback', name: 'Feedback' },
    };
}

async function mount(path: string): Promise<void> {
    window.history.replaceState(null, '', path);
    document.body.innerHTML = '<div id="mount"></div>';
    patch(document.getElementById('mount')!, forumView({ username: 'alice', assetURL: '' } as PyChessModel));
    await jest.advanceTimersByTimeAsync(0);
}

beforeEach(() => {
    jest.useFakeTimers();
    observers = [];
    originalFetch = window.fetch;
    originalObserver = window.IntersectionObserver;
    window.IntersectionObserver = Observer as unknown as typeof IntersectionObserver;
    fetchMock = jest.fn<typeof fetch>();
    window.fetch = fetchMock;
});

afterEach(() => {
    window.fetch = originalFetch;
    window.IntersectionObserver = originalObserver;
    window.history.replaceState(null, '', '/');
    document.body.innerHTML = '';
    jest.useRealTimers();
    jest.restoreAllMocks();
});

test('user post history appends search pages, deduplicates shifted results, and stops at the end', async () => {
    fetchMock
        .mockResolvedValueOnce(response({ posts: [result('one')], page: 1, nbPages: 3, total: 3 }))
        .mockResolvedValueOnce(response({ posts: [result('one'), result('two')], page: 2, nbPages: 3, total: 3 }))
        .mockResolvedValueOnce(response({ posts: [result('three')], page: 3, nbPages: 3, total: 3 }));
    await mount('/forum/search?text=user%3Aalice');
    const first = document.querySelector('.search__results tr');
    expect(document.querySelector('.forum-pagination')).toBeNull();
    observers[0].intersect();
    observers[0].intersect();
    await jest.advanceTimersByTimeAsync(0);
    expect(document.querySelectorAll('.search__results tr')).toHaveLength(2);
    expect(document.querySelector('.search__results tr')).toBe(first);
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/forum/search?text=user%3Aalice&page=2');
    await jest.advanceTimersByTimeAsync(500);
    observers[0].intersect();
    await jest.advanceTimersByTimeAsync(0);
    expect(document.querySelectorAll('.search__results tr')).toHaveLength(3);
    expect(document.querySelector('a[href="/forum/redirect/post/three"]')).not.toBeNull();
    expect(observers[0].disconnect).toHaveBeenCalled();
    observers[0].intersect();
    expect(fetchMock).toHaveBeenCalledTimes(3);
});

test('failed next-page requests keep existing posts and restore navigation to that page', async () => {
    jest.spyOn(console, 'warn').mockImplementation(() => {});
    fetchMock
        .mockResolvedValueOnce(response({ posts: [result('one')], page: 2, nbPages: 3, total: 3 }))
        .mockResolvedValueOnce(response({ type: 'error', code: 'forum_unavailable' }, 503));
    await mount('/forum/search?text=user%3Aalice%20chess&page=2');
    observers[0].intersect();
    await jest.advanceTimersByTimeAsync(0);
    expect(document.querySelectorAll('.search__results tr')).toHaveLength(1);
    expect(document.querySelector('.forum-pagination a:last-child')?.getAttribute('href')).toBe(
        '/forum/search?text=user%3Aalice%20chess&page=3',
    );
    expect(observers[0].disconnect).toHaveBeenCalled();
});

test('category topic lists append without replacing existing rows', async () => {
    const topic = (id: string) => ({
        _id: id,
        slug: id,
        name: id,
        lastPostId: `post-${id}`,
        lastPostAt: '2026-11-08T00:00:00Z',
        lastPostUser: 'alice',
    });
    fetchMock
        .mockResolvedValueOnce(response({ topics: [topic('one')], page: 1, nbPages: 2 }))
        .mockResolvedValueOnce(response({ topics: [topic('two')], page: 2, nbPages: 2 }));
    await mount('/forum/feedback');
    observers[0].intersect();
    await jest.advanceTimersByTimeAsync(0);
    expect(document.querySelectorAll('table.topics tbody tr')).toHaveLength(2);
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/forum/feedback/topics?page=2');
});

test('moderation feeds append older posts using the same loader', async () => {
    fetchMock
        .mockResolvedValueOnce(response({ items: [result('one')], page: 1, nbPages: 2 }))
        .mockResolvedValueOnce(response({ items: [result('two')], page: 2, nbPages: 2 }));
    await mount('/forum/feedback/mod-feed');
    observers[0].intersect();
    await jest.advanceTimersByTimeAsync(0);
    expect(document.querySelectorAll('.forum-mod-feed tbody tr')).toHaveLength(2);
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/forum/feedback/mod-feed?page=2');
});

test('direct links to the last page retain previous-page navigation', async () => {
    fetchMock.mockResolvedValueOnce(response({ posts: [result('two')], page: 2, nbPages: 2 }));
    await mount('/forum/search?text=user%3Aalice&page=2');
    expect(document.querySelector('.forum-pagination a')?.getAttribute('href')).toBe(
        '/forum/search?text=user%3Aalice&page=1',
    );
    expect(observers).toHaveLength(0);
});

test('browsers without an observer keep ordinary page navigation', async () => {
    Reflect.deleteProperty(window, 'IntersectionObserver');
    fetchMock.mockResolvedValueOnce(response({ posts: [result('one')], page: 1, nbPages: 2 }));
    await mount('/forum/search?text=user%3Aalice');
    expect(document.querySelector('.forum-pagination a:last-child')?.getAttribute('href')).toBe(
        '/forum/search?text=user%3Aalice&page=2',
    );
    expect(observers).toHaveLength(0);
});
