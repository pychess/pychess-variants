import { h, VNode } from 'snabbdom';

import { _ } from './i18n';
import { getDocumentData, patch } from './document';
import { showMainSettings } from './settingsView';

let dialogVNode: VNode | null = null;

function shouldShowIntro(): boolean {
    if (getDocumentData('view') === 'my-variants') return false;
    return getDocumentData('game-category-intro') === 'True';
}

async function setGameCategoryAll(): Promise<void> {
    const body = new URLSearchParams({ game_category: 'all' });
    try {
        await fetch('/pref/game-category', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body,
        });
    } catch (error) {
        console.error('Error setting game category to all:', error);
    }
}

function showGameCategorySettings(): void {
    /* THE SETTINGS PANEL HAS ONE OPENER NOW. This re-implemented `showMainSettings()` line for
       line, which is how it came to be a second place that had to learn about every new thing the
       panel's button carries -- `aria-expanded` would have gone stale here the day it was added. */
    showMainSettings();
    const gameCategoryButton = document.getElementById('btn-game-category') as HTMLButtonElement | null;
    if (gameCategoryButton) {
        gameCategoryButton.click();
    }
}

function hideIntro(): void {
    const dialogElement = document.getElementById('game-category-intro');
    if (dialogElement) {
        dialogElement.style.display = 'none';
    }
    dialogVNode = null;
}

function renderIntro(): void {
    const dialogElement = document.getElementById('game-category-intro');
    if (!dialogElement) return;

    const vnode = h('div.game-category-dialog-content', [
        h('h2', _('Game category filter')),
        h(
            'p',
            _(
                'Pychess supports more than 60 variants across many chess families, so the lobby, puzzles, tournaments, and menus can feel very broad.',
            ),
        ),
        h(
            'p',
            _(
                'If you mostly play a regional chess, you can focus the whole site to that family: Shogi (Japanese), Xiangqi/Janggi (Chinese/Korean), or Makruk/Ouk Chaktrang (Thai/Cambodian).',
            ),
        ),
        h(
            'p',
            _(
                'This trims the variant lists, keeps recommendations and events in your area of interest, and makes the site feel like a dedicated hub rather than a huge catalog. Think of it as creating a lishogi.org-style experience inside Pychess.',
            ),
        ),
        h(
            'p',
            _(
                'You can switch anytime in Preferences (gear icon). If you want everything, choose "All" and nothing is filtered.',
            ),
        ),
        h('div.game-category-dialog-actions', [
            h(
                'button.secondary-btn',
                {
                    props: { type: 'button' },
                    on: {
                        click: event => {
                            event.preventDefault();
                            event.stopPropagation();
                            void setGameCategoryAll();
                            hideIntro();
                        },
                    },
                },
                _('Keep all variants'),
            ),
            h(
                'button.confirm-btn',
                {
                    props: { type: 'button' },
                    on: {
                        click: event => {
                            event.preventDefault();
                            event.stopPropagation();
                            void setGameCategoryAll();
                            hideIntro();
                            showGameCategorySettings();
                        },
                    },
                },
                _('Open preferences'),
            ),
        ]),
    ]);

    if (dialogVNode === null) {
        dialogElement.innerHTML = '';
        const placeholder = document.createElement('div');
        dialogElement.appendChild(placeholder);
        dialogVNode = patch(placeholder, vnode);
    } else {
        dialogVNode = patch(dialogVNode, vnode);
    }
}

export function maybeShowGameCategoryIntro(): void {
    if (!shouldShowIntro()) return;

    let dialogElement = document.getElementById('game-category-intro');
    if (!dialogElement) {
        dialogElement = document.createElement('div');
        dialogElement.id = 'game-category-intro';
        dialogElement.className = 'modal-overlay modal-overlay-fullscreen';
        document.body.appendChild(dialogElement);
    } else {
        dialogElement.classList.add('modal-overlay-fullscreen');
    }

    dialogElement.style.display = 'flex';
    renderIntro();
}
