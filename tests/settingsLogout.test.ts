import { beforeEach, expect, jest, test } from '@jest/globals';

import { patch } from '@/document';
import { settingsView } from '@/settingsView';

beforeEach(() => {
    document.body.innerHTML = `
        <div id="pychess-variants" data-anon="False"></div>
        <div id="mount"></div>
    `;
    Object.defineProperty(HTMLDialogElement.prototype, 'showModal', {
        configurable: true,
        value: jest.fn(function (this: HTMLDialogElement) {
            this.setAttribute('open', '');
        }),
    });
    Object.defineProperty(HTMLDialogElement.prototype, 'close', {
        configurable: true,
        value: jest.fn(function (this: HTMLDialogElement) {
            this.removeAttribute('open');
            this.dispatchEvent(new Event('close'));
        }),
    });
});

test('logout confirmation uses a POST request', async () => {
    const fetchMock = jest.fn(async () => ({ ok: true }) as Response);
    Object.defineProperty(window, 'fetch', {
        configurable: true,
        writable: true,
        value: fetchMock,
    });

    patch(document.getElementById('mount')!, settingsView('chess'));
    document.querySelector<HTMLButtonElement>('#btn-logout')!.click();
    document.querySelector<HTMLButtonElement>('.confirm-dialog-confirm')!.click();
    await Promise.resolve();

    expect(fetchMock).toHaveBeenCalledWith('/logout', { method: 'POST' });
});
