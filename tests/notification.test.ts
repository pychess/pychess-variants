import { afterEach, beforeEach, expect, jest, test } from '@jest/globals';

import { notify, setCorrBrowserEnabled } from '../client/notification';

const originalNotification = Object.getOwnPropertyDescriptor(window, 'Notification');

beforeEach(() => {
    jest.useFakeTimers();
    document.body.innerHTML = '<div id="pychess-variants" data-username="Alice" data-anon="False"></div>';
    localStorage.clear();
});

afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
    if (originalNotification) Object.defineProperty(window, 'Notification', originalNotification);
    else Reflect.deleteProperty(window, 'Notification');
});

function installNotification(permission: NotificationPermission = 'granted') {
    const instance = { onclick: null as null | (() => void) };
    const construct = jest.fn(() => instance);
    const requestPermission = jest.fn<() => Promise<NotificationPermission>>();
    Object.defineProperty(window, 'Notification', {
        configurable: true,
        value: Object.assign(construct, { permission, requestPermission }),
    });
    return { construct, requestPermission, instance };
}

test('a browser without notifications is safe even when an iPad identifies itself as a Mac', () => {
    jest.spyOn(navigator, 'userAgent', 'get').mockReturnValue('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)');
    jest.spyOn(navigator, 'platform', 'get').mockReturnValue('MacIntel');
    Reflect.deleteProperty(window, 'Notification');

    expect(() => notify('Your turn', { body: 'Played e4' })).not.toThrow();
    expect(jest.getTimerCount()).toBe(0);
});

test('delivery is deferred so move processing can finish first', () => {
    const { construct, instance } = installNotification();
    const focus = jest.spyOn(window, 'focus').mockImplementation(() => {});

    notify('Your turn', { body: 'Played e4' });
    expect(construct).not.toHaveBeenCalled();
    jest.runAllTimers();

    expect(construct).toHaveBeenCalledWith('Your turn', { body: 'Played e4' });
    instance.onclick!();
    expect(focus).toHaveBeenCalledTimes(1);
});

test('an unsupported notification constructor cannot interrupt the caller or delivery timer', () => {
    const { construct } = installNotification();
    construct.mockImplementation(() => {
        throw new TypeError('Illegal constructor');
    });

    expect(() => notify('Your turn', undefined)).not.toThrow();
    expect(() => jest.runAllTimers()).not.toThrow();
    expect(construct).toHaveBeenCalledTimes(1);
});

test('default permission can be granted before delivery', async () => {
    const { construct, requestPermission } = installNotification('default');
    requestPermission.mockResolvedValue('granted');

    notify('Your turn', undefined);
    await jest.runAllTimersAsync();

    expect(requestPermission).toHaveBeenCalledTimes(1);
    expect(construct).toHaveBeenCalledWith('Your turn', undefined);
});

test.each(['denied', 'default'] as const)('a permission response of %s does not deliver', async permission => {
    const { construct, requestPermission } = installNotification('default');
    requestPermission.mockResolvedValue(permission);

    notify('Your turn', undefined);
    await jest.runAllTimersAsync();

    expect(construct).not.toHaveBeenCalled();
});

test.each(['throw', 'reject'] as const)('permission requests that %s do not escape', async failure => {
    const { construct, requestPermission } = installNotification('default');
    requestPermission.mockImplementation(() => {
        if (failure === 'throw') throw new Error('Permission request unavailable');
        return Promise.reject(new Error('Permission request rejected'));
    });

    notify('Your turn', undefined);
    await expect(jest.runAllTimersAsync()).resolves.toBeUndefined();

    expect(construct).not.toHaveBeenCalled();
});

test('constructor failures after granting permission are also handled', async () => {
    const { construct, requestPermission } = installNotification('default');
    requestPermission.mockResolvedValue('granted');
    construct.mockImplementation(() => {
        throw new TypeError('Illegal constructor');
    });

    notify('Your turn', undefined);
    await expect(jest.runAllTimersAsync()).resolves.toBeUndefined();
});

test('denied permission does not prompt again', async () => {
    const { construct, requestPermission } = installNotification('denied');

    notify('Your turn', undefined);
    await jest.runAllTimersAsync();

    expect(requestPermission).not.toHaveBeenCalled();
    expect(construct).not.toHaveBeenCalled();
});

test('browser opt-out suppresses correspondence moves without prompting, but leaves live alerts enabled', async () => {
    const { construct, requestPermission } = installNotification('default');
    requestPermission.mockResolvedValue('granted');
    setCorrBrowserEnabled(false);

    notify('Your turn', { body: 'Correspondence move' }, true);
    await jest.runAllTimersAsync();
    expect(requestPermission).not.toHaveBeenCalled();
    expect(construct).not.toHaveBeenCalled();

    notify('Your turn', { body: 'Live move' });
    await jest.runAllTimersAsync();
    expect(construct).toHaveBeenCalledWith('Your turn', { body: 'Live move' });
});

test('correspondence browser alerts are enabled by default and independent of push opt-out', () => {
    const { construct } = installNotification();
    document.getElementById('pychess-variants')!.setAttribute('data-corr-push-enabled', 'False');

    notify('Your turn', undefined, true);
    jest.runAllTimers();
    expect(construct).toHaveBeenCalledTimes(1);
});

test('a later opt-out prevents an already scheduled correspondence alert', () => {
    const { construct } = installNotification();
    notify('Your turn', undefined, true);
    setCorrBrowserEnabled(false);
    jest.runAllTimers();
    expect(construct).not.toHaveBeenCalled();
});

test('other tabs synchronize this account browser preference but ignore other accounts', () => {
    const { construct } = installNotification();
    document.body.insertAdjacentHTML('beforeend', '<input id="corr-browser-enabled" type="checkbox" checked>');
    const input = document.getElementById('corr-browser-enabled') as HTMLInputElement;
    const updateFromTab = (username: string, enabled: boolean) => window.dispatchEvent(new StorageEvent('storage', {
        key: `corr-browser:${username}`, newValue: enabled ? 'True' : 'False',
    }));

    updateFromTab('Alice', false);
    expect(input.checked).toBe(false);
    notify('Your turn', undefined, true);
    jest.runAllTimers();
    expect(construct).not.toHaveBeenCalled();

    updateFromTab('Bob', true);
    expect(input.checked).toBe(false);
    updateFromTab('Alice', true);
    expect(input.checked).toBe(true);
    notify('Your turn', undefined, true);
    jest.runAllTimers();
    expect(construct).toHaveBeenCalledTimes(1);
});
