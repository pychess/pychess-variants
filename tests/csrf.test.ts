import { expect, jest, test } from '@jest/globals';
import { installCsrfProtection } from '@/csrf';

test('adds the session CSRF token to same-origin unsafe fetches and forms', async () => {
    document.body.innerHTML = `
        <div id="root" data-csrf-token="csrf-test-token"></div>
        <form id="delete-form" method="post" action="/account/delete"></form>
    `;

    const fetchMock = jest.fn(async () => ({ ok: true } as Response));
    Object.defineProperty(window, 'fetch', {
        configurable: true,
        writable: true,
        value: fetchMock,
    });

    const root = document.getElementById('root');
    installCsrfProtection(root);

    await window.fetch('/api/example', { method: 'POST', headers: { 'Content-Type': 'application/json' } });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const fetchInit = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(fetchInit.headers).get('X-CSRF-Token')).toBe('csrf-test-token');
    expect(new Headers(fetchInit.headers).get('Content-Type')).toBe('application/json');

    const form = document.getElementById('delete-form') as HTMLFormElement;
    const hidden = form.elements.namedItem('_csrf_token') as HTMLInputElement;
    expect(hidden).toBeInstanceOf(HTMLInputElement);
    expect(hidden.type).toBe('hidden');
    expect(hidden.value).toBe('csrf-test-token');
});
