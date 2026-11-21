import { afterEach, beforeEach, expect, jest, test } from '@jest/globals';

import { patch } from '@/document';
import { settingsView } from '@/settingsView';

const originalFetch = Object.getOwnPropertyDescriptor(window, 'fetch');
const originalNotification = Object.getOwnPropertyDescriptor(window, 'Notification');

beforeEach(() => {
    document.body.innerHTML = `
        <div id="pychess-variants" data-anon="False" data-username="Alice"
            data-corr-browser-enabled="True" data-corr-push-enabled="False"></div>
        <div id="mount"></div>
    `;
    localStorage.clear();
});

afterEach(() => {
    jest.restoreAllMocks();
    if (originalFetch) Object.defineProperty(window, 'fetch', originalFetch);
    else Reflect.deleteProperty(window, 'fetch');
    if (originalNotification) Object.defineProperty(window, 'Notification', originalNotification);
    else Reflect.deleteProperty(window, 'Notification');
});

function mountSettings() {
    patch(document.getElementById('mount')!, settingsView('chess'));
    document.querySelector<HTMLButtonElement>('#btn-settings')!.click();
    document.querySelector<HTMLButtonElement>('#btn-notifications')!.click();
    return document.querySelector<HTMLInputElement>('#corr-browser-enabled')!;
}

test('notification controls have their own menu and no longer appear in Privacy', () => {
    const input = mountSettings();
    expect(document.getElementById('settings-notifications')!.style.display).toBe('flex');
    expect(document.querySelectorAll('#settings-notifications input')).toHaveLength(3);
    expect(document.querySelectorAll('#settings-privacy input')).toHaveLength(1);
    expect(input.checked).toBe(true);
    expect(document.querySelector<HTMLInputElement>('#corr-push-enabled')!.checked).toBe(false);
});

test('saving browser opt-out updates the page and other tabs without changing push subscriptions', async () => {
    const fetchMock = jest.fn<typeof fetch>().mockResolvedValue({ ok: true } as Response);
    Object.defineProperty(window, 'fetch', { configurable: true, value: fetchMock });
    const input = mountSettings();

    input.click();
    expect(input.disabled).toBe(true);
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith('/pref/corr-browser', expect.objectContaining({
        method: 'POST', body: 'corr_browser=false',
    }));
    expect(input.disabled).toBe(false);
    expect(input.checked).toBe(false);
    expect(document.getElementById('pychess-variants')!.getAttribute('data-corr-browser-enabled')).toBe('False');
    expect(localStorage.getItem('corr-browser:Alice')).toBe('False');
    expect(document.querySelector<HTMLInputElement>('#corr-push-enabled')!.checked).toBe(false);
});

test('a failed save restores the browser preference and shows an error', async () => {
    const fetchMock = jest.fn<typeof fetch>().mockResolvedValue({ ok: false, status: 500 } as Response);
    Object.defineProperty(window, 'fetch', { configurable: true, value: fetchMock });
    jest.spyOn(console, 'warn').mockImplementation(() => {});
    const input = mountSettings();

    input.click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(input.disabled).toBe(false);
    expect(input.checked).toBe(true);
    expect(document.getElementById('notification-setting-error')!.hidden).toBe(false);
    expect(document.getElementById('pychess-variants')!.getAttribute('data-corr-browser-enabled')).toBe('True');
    expect(localStorage.getItem('corr-browser:Alice')).toBeNull();
});

test('an unanswered browser permission prompt does not block saving the preference', async () => {
    const fetchMock = jest.fn<typeof fetch>().mockResolvedValue({ ok: true } as Response);
    Object.defineProperty(window, 'fetch', { configurable: true, value: fetchMock });
    const requestPermission = jest.fn<() => Promise<NotificationPermission>>(() => new Promise(() => {}));
    Object.defineProperty(window, 'Notification', {
        configurable: true, value: { permission: 'default', requestPermission },
    });
    document.getElementById('pychess-variants')!.setAttribute('data-corr-browser-enabled', 'False');
    const input = mountSettings();

    input.click();
    await new Promise(resolve => setTimeout(resolve, 0));

    expect(requestPermission).toHaveBeenCalledTimes(1);
    expect(input.disabled).toBe(false);
    expect(input.checked).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith('/pref/corr-browser', expect.objectContaining({ body: 'corr_browser=true' }));
    expect(document.getElementById('pychess-variants')!.getAttribute('data-corr-browser-enabled')).toBe('True');
});
