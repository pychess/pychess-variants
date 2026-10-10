import { expect, jest, test } from '@jest/globals';

import { patch } from '../client/document';
import { inboxView } from '../client/inbox';
import type { PyChessModel } from '../client/types';

function jsonResponse(payload: unknown): Response {
    return { ok: true, status: 200, text: async () => JSON.stringify(payload) } as Response;
}

test('opening a thread acknowledges it with POST before refreshing unread status', async () => {
    jest.useFakeTimers();
    const fetchDescriptor = Object.getOwnPropertyDescriptor(window, 'fetch');
    const eventSourceDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'EventSource');
    let acknowledge!: (response: Response) => void;
    const acknowledgement = new Promise<Response>(resolve => { acknowledge = resolve; });
    const fetchMock = jest.fn(async (input: RequestInfo | URL, _init?: RequestInit): Promise<Response> => {
        switch (String(input)) {
            case '/api/blocks': return jsonResponse({ blocks: [] });
            case '/api/inbox/threads': return jsonResponse({ threads: [] });
            case '/api/inbox/thread/alice':
                return jsonResponse({
                    contact: { name: 'alice' },
                    messages: [{ _id: 'message1', from: 'alice', text: 'hello bob', createdAt: '2026-10-06T00:00:00Z' }],
                });
            case '/api/inbox/thread/alice/read': return acknowledgement;
            default: throw new Error(`Unexpected request: ${String(input)}`);
        }
    });
    Object.defineProperty(window, 'fetch', { configurable: true, writable: true, value: fetchMock });
    Object.defineProperty(globalThis, 'EventSource', {
        configurable: true,
        value: jest.fn(() => ({ close: jest.fn() })),
    });

    try {
        document.body.innerHTML = '<div id="mount"></div>';
        patch(document.getElementById('mount')!, inboxView({ profileid: 'alice', username: 'bob' } as PyChessModel));
        await jest.advanceTimersByTimeAsync(0);

        expect(fetchMock).toHaveBeenCalledWith('/api/inbox/thread/alice/read', { method: 'POST' });
        expect(fetchMock.mock.calls.filter(([url]) => url === '/api/inbox/threads')).toHaveLength(1);

        acknowledge(jsonResponse({ ok: true }));
        await jest.advanceTimersByTimeAsync(0);

        expect(fetchMock.mock.calls.filter(([url]) => url === '/api/inbox/threads')).toHaveLength(2);
        expect(document.getElementById('inbox-app')?.textContent).toContain('hello bob');
    } finally {
        if (fetchDescriptor) Object.defineProperty(window, 'fetch', fetchDescriptor);
        else Reflect.deleteProperty(window, 'fetch');
        if (eventSourceDescriptor) Object.defineProperty(globalThis, 'EventSource', eventSourceDescriptor);
        else Reflect.deleteProperty(globalThis, 'EventSource');
        document.body.innerHTML = '';
        jest.useRealTimers();
    }
});
