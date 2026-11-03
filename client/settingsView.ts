import { h } from 'snabbdom';

import { backgroundSettings } from './background';
import { gameCategorySettings } from './gameCategory';
import { boardSettings } from './boardSettings';
import { selectVariant } from './variants';
import { patch, getDocumentData } from './document';
import { _, translatedGameCategory, translatedLanguage, languageSettings } from './i18n';
import { volumeSettings, soundThemeSettings } from './sound';
import { zenModeSettings } from './zen';
import { confirmDialog } from './confirmDialog';
import { disablePushSubscription, initPushSubscription } from './push';
import { setCorrBrowserEnabled } from './notification';
import { setHeaderPanelExpanded } from './headerPanel';

export function settingsView(modelVariant: string) {
    const anon = getDocumentData('anon') === 'True';
    return h('div#settings-panel', [
        settingsButton(),
        h('div#settings', [
            h('div#settings-main', [mainMenu(anon)]),
            h('div#settings-sub', [
                langSettingsView(),
                soundSettingsView(),
                backgroundSettingsView(),
                gameCategorySettingsView(),
                boardSettingsView(modelVariant),
                zenModeSettingsView(),
                privacySettingsView(),
                notificationSettingsView(),
            ]),
        ]),
    ]);
}

function settingsButton() {
    return h('button#btn-settings', { on: { click: toggleSettings }, attrs: { 'aria-label': _('Settings'), 'aria-expanded': 'false', 'aria-controls': 'settings' } }, [
        h('div.icon.icon-cog'),
    ]);
}

function toggleSettings() {
    if ((document.getElementById('settings') as HTMLElement).style.display === 'flex') {
        hideSettings();
    } else {
        showMainSettings();
    }
}

export function hideSettings() {
    setHeaderPanelExpanded('btn-settings', false);
    (document.getElementById('settings') as HTMLElement).style.display = 'none';
}

export function showMainSettings() {
    setHeaderPanelExpanded('btn-settings', true);
    (document.getElementById('settings') as HTMLElement).style.display = 'flex';
    (document.getElementById('settings-main') as HTMLElement).style.display = 'flex';
    (document.getElementById('settings-sub') as HTMLElement).style.display = 'none';
}

function mainMenu(anon: boolean) {
    const buttons = [
        h('button#btn-lang', { on: { click: showSubsettings } }, translatedLanguage),
        h('button#btn-sound', { on: { click: showSubsettings } }, _('Sound')),
        h('button#btn-background', { on: { click: showSubsettings } }, _('Background')),
        h('button#btn-game-category', { on: { click: showSubsettings } }, translatedGameCategory),
        h('button#btn-board', { on: { click: showSubsettings } }, _('Board Settings')),
        h('button#btn-zen', { on: { click: showSubsettings } }, _('Zen Mode')),
    ];

    if (!anon) {
        buttons.push(
            h('div.settings-menu-separator', { attrs: { role: 'separator' } }),
            h('button#btn-inbox-menu', { on: { click: gotoInbox } }, _('Inbox')),
            h('button#btn-privacy', { on: { click: showSubsettings } }, _('Privacy')),
            h('button#btn-notifications', { on: { click: showSubsettings } }, _('Notifications')),
            h('button#btn-account', { on: { click: gotoAccount } }, _('Account')),
            h('button#btn-logout', { on: { click: logoutDialog } }, _('Log out')),
        );
    }

    return h(anon ? 'div#settings-buttons.anon' : 'div#settings-buttons.logged-in', buttons);
}

function gotoInbox() {
    window.location.href = '/inbox';
}

function gotoAccount() {
    window.location.href = '/account';
}

async function logoutDialog() {
    const confirmed = await confirmDialog({
        text: _('Are you sure you want to log out?'),
        confirmText: _('Log out'),
        cancelText: _('Cancel'),
    });
    if (!confirmed) return;
    const response = await window.fetch('/logout', { method: 'POST' });
    if (response.ok) window.location.href = '/';
}

function showSubsettings(evt: MouseEvent) {
    const mainSettings = document.getElementById('settings-main') as HTMLElement;
    const subSettings = document.getElementById('settings-sub') as HTMLElement;

    Array.from(subSettings.children).forEach((sub: HTMLElement) => (sub.style.display = 'none'));

    const settingsName = (<HTMLButtonElement>evt.target).id.slice(4);
    const targetSettings = document.getElementById('settings-' + settingsName) as HTMLElement;
    targetSettings.style.display = 'flex';

    mainSettings.style.display = 'none';
    subSettings.style.display = 'flex';
}

function backButton(text: string) {
    return h('button.back', { on: { click: showMainSettings } }, [h('back.icon.icon-left', text)]);
}

function langSettingsView() {
    return h('div#settings-lang', [backButton(translatedLanguage), languageSettings.view()]);
}

function soundSettingsView() {
    return h('div#settings-sound', [
        backButton(_('Sound')),
        h('div', [volumeSettings.view(), soundThemeSettings.view()]),
    ]);
}

function backgroundSettingsView() {
    return h('div#settings-background', [backButton(_('Background')), backgroundSettings.view()]);
}

function gameCategorySettingsView() {
    return h('div#settings-game-category', [backButton(translatedGameCategory), gameCategorySettings.view()]);
}

function zenModeSettingsView() {
    return h('div#settings-zen', [backButton(_('Zen Mode')), zenModeSettings.view()]);
}

function privacySettingsView() {
    const pmFriendsOnly = getDocumentData('pm-friends-only') === 'True';
    return h('div#settings-privacy', [
        backButton(_('Privacy')),
        h('div', [
            h('div.privacy-toggle', [
                h('input#pm-friends-only', {
                    attrs: { type: 'checkbox', checked: pmFriendsOnly },
                    on: {
                        change: (evt: Event) => {
                            const next = (evt.target as HTMLInputElement).checked;
                            setPmFriendsOnly(next);
                        },
                    },
                }),
                h('label', { attrs: { for: 'pm-friends-only' } }, _('Only friends can message me')),
            ]),
        ]),
    ]);
}

function notificationSettingsView() {
    return h('div#settings-notifications', [
        backButton(_('Notifications')),
        h('div', [
            notificationToggle(
                'corr-browser-enabled',
                getDocumentData('corr-browser-enabled') !== 'False',
                _('Correspondence move browser notifications'),
                _('Show a device notification when a game tab is open in the background.'),
                input => void saveCorrBrowserEnabled(input),
            ),
            notificationToggle(
                'corr-push-enabled',
                getDocumentData('corr-push-enabled') !== 'False',
                _('Correspondence move push notifications'),
                _('Receive background notifications even when no Pychess tab is open.'),
                input => setCorrPushEnabled(input.checked),
            ),
            notificationToggle(
                'rr-push-enabled',
                getDocumentData('rr-push-enabled') === 'True',
                _('Round-robin appointment push notifications'),
                _('Receive background notifications about round-robin game appointments.'),
                input => setRrPushEnabled(input.checked),
            ),
            h('p#notification-setting-error', { attrs: { role: 'alert', hidden: true } }, _('Failed to save notification setting. Please try again.')),
        ]),
    ]);
}

function notificationToggle(
    id: string,
    enabled: boolean,
    label: string,
    description: string,
    change: (input: HTMLInputElement) => void,
) {
    return h('div.notification-toggle', [
        h(`input#${id}`, {
            attrs: { type: 'checkbox', checked: enabled, 'aria-describedby': `${id}-description` },
            on: { change: (evt: Event) => change(evt.target as HTMLInputElement) },
        }),
        h('div', [
            h('label', { attrs: { for: id } }, label),
            h(`small#${id}-description`, description),
        ]),
    ]);
}

async function saveCorrBrowserEnabled(input: HTMLInputElement): Promise<void> {
    const value = input.checked;
    const previous = getDocumentData('corr-browser-enabled') !== 'False';
    const errorMessage = document.getElementById('notification-setting-error');
    input.disabled = true;
    if (errorMessage) errorMessage.hidden = true;
    // Request permission during the user's gesture; browser alerts need no push subscription.
    if (value && 'Notification' in window && Notification.permission === 'default') {
        try {
            void Notification.requestPermission().catch(() => {});
        } catch {
            // The account preference can still be saved when permission requests are unavailable.
        }
    }
    try {
        const payload = new URLSearchParams({ corr_browser: value ? 'true' : 'false' });
        const response = await fetch('/pref/corr-browser', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
            body: payload.toString(),
        });
        if (!response.ok) throw new Error(`notification pref failed: ${response.status}`);
        setCorrBrowserEnabled(value);
    } catch (error) {
        input.checked = previous;
        if (errorMessage) errorMessage.hidden = false;
        console.warn('Failed to update browser notification setting.', error);
    } finally {
        input.disabled = false;
    }
}

function setPmFriendsOnly(value: boolean) {
    const payload = new URLSearchParams({ pm_friends_only: value ? 'true' : 'false' });
    fetch('/pref/pm-friends-only', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
        body: payload.toString(),
    }).catch(error => {
        console.warn('Failed to update PM privacy setting.', error);
    });
}

function setCorrPushEnabled(value: boolean) {
    void setPushPreference('/pref/corr-push', 'corr_push', value);
}

function setRrPushEnabled(value: boolean) {
    void setPushPreference('/pref/rr-push', 'rr_push', value);
}

async function setPushPreference(url: string, field: string, value: boolean): Promise<void> {
    const payload = new URLSearchParams({ [field]: value ? 'true' : 'false' });
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
            body: payload.toString(),
        });
        if (!response.ok) throw new Error(`push pref failed: ${response.status}`);
        await syncPushSubscription();
    } catch (error) {
        console.warn('Failed to update push notification setting.', error);
    }
}

async function syncPushSubscription(): Promise<void> {
    const corrEnabled = (document.getElementById('corr-push-enabled') as HTMLInputElement | null)?.checked ?? false;
    const rrEnabled = (document.getElementById('rr-push-enabled') as HTMLInputElement | null)?.checked ?? false;

    if (!corrEnabled && !rrEnabled) {
        await disablePushSubscription();
        return;
    }

    if ('Notification' in window && Notification.permission === 'default') {
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') return;
    }

    const anon = getDocumentData('anon') ?? 'True';
    const vapidPublicKey = getDocumentData('vapid') ?? '';
    await initPushSubscription(anon, vapidPublicKey);
}

function boardSettingsView(modelVariant: string) {
    const variant = getDocumentData('variant') || 'chess';
    return h('div#settings-board', [
        backButton(_('Board Settings')),
        h('div', [
            h('div.labelled', [
                h('label', { attrs: { for: 'settings-variant' } }, _('Variant')),
                selectVariant(
                    'settings-variant',
                    variant,
                    () => showVariantBoardSettings(modelVariant),
                    () => showVariantBoardSettings(modelVariant),
                    [],
                    getDocumentData('game-category') || undefined,
                ),
            ]),
            h('div#board-settings'),
        ]),
    ]);
}

function showVariantBoardSettings(modelVariant: string) {
    const e = document.getElementById('settings-variant') as HTMLSelectElement;
    const selectedVariant = e.options[e.selectedIndex].value;
    const settings = document.getElementById('board-settings') as HTMLElement;
    settings.innerHTML = '';
    patch(settings, boardSettings.view(selectedVariant, modelVariant));
}
