import { h, VNode } from 'snabbdom';

import { _ } from './i18n';
import { StringSettings } from './settings';
import { radioList } from './view';
import { patch } from './document';

const zenModeOptions = {
    off: _('Off'),
    on: _('On'),
};

class ZenModeSettings extends StringSettings {
    constructor() {
        super('zen', 'off');
    }

    update(): void {
        document.documentElement.setAttribute('data-zen', this.value);
    }

    view(): VNode {
        return h(
            'div#zen-selector',
            radioList(this, 'zen', zenModeOptions, (_, key) => (this.value = key)),
        );
    }
}

export const zenModeSettings = new ZenModeSettings();

function deactivateZenMode() {
    zenModeSettings.value = 'off';
    zenModeSettings.update();

    const zenSettings = document.getElementById('zen-selector') as HTMLElement;
    zenSettings.innerHTML = '';
    patch(zenSettings, zenModeSettings.view());
}

export function zenButtonView() {
    return h(
        'a#zen-button',
        {
            attrs: { href: '#' },
            on: {
                click: (e: Event) => {
                    e.preventDefault();
                    deactivateZenMode();
                },
            },
        },
        [h('div.icon.icon-check', _('ZEN MODE'))],
    );
}
