import { getDocumentData } from './document';

function corrBrowserStorageKey(): string | null {
    const username = getDocumentData('username');
    return username && getDocumentData('anon') === 'False' ? `corr-browser:${username}` : null;
}

function applyCorrBrowserEnabled(enabled: boolean): void {
    document.getElementById('pychess-variants')?.setAttribute('data-corr-browser-enabled', enabled ? 'True' : 'False');
    const input = document.getElementById('corr-browser-enabled') as HTMLInputElement | null;
    if (input) input.checked = enabled;
}

export function setCorrBrowserEnabled(enabled: boolean): void {
    applyCorrBrowserEnabled(enabled);
    const key = corrBrowserStorageKey();
    if (key) {
        try {
            localStorage.setItem(key, enabled ? 'True' : 'False');
        } catch {
            // The saved account preference still works when browser storage is unavailable.
        }
    }
}

window.addEventListener('storage', event => {
    const key = corrBrowserStorageKey();
    if (key && event.key === key && (event.newValue === 'True' || event.newValue === 'False')) {
        applyCorrBrowserEnabled(event.newValue === 'True');
    }
});

export function notify(title: string | null, options: NotificationOptions | undefined, correspondenceMove = false) {
    const enabled = () => !correspondenceMove || getDocumentData('corr-browser-enabled') !== 'False';
    if (!title || !('Notification' in window) || !enabled()) return;

    // Like lila's ui/lib/src/notification.ts, keep delivery outside move processing.
    setTimeout(() => {
        if (!enabled()) return;
        const show = () => {
            if (!enabled()) return;
            const notification = new Notification(title, options);
            notification.onclick = () => window.focus();
        };

        try {
            if (Notification.permission === 'granted') {
                show();
            } else if (Notification.permission === 'default') {
                void Notification.requestPermission()
                    .then(permission => {
                        if (permission === 'granted') show();
                    })
                    .catch(() => {});
            }
        } catch {
            // Some browsers expose the API but reject permission requests or construction.
        }
    }, 0);
}
