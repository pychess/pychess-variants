import { afterEach, beforeEach, describe, expect, jest, test } from '@jest/globals';

import { initTournamentForm } from '../client/tournamentForm';

jest.useFakeTimers();

function setupTournamentForm(): void {
    document.body.innerHTML = `
        <form id="tournament-form" method="post" action="/tournaments/new">
            <select id="form3-system"><option value="0">Arena</option><option value="1">Round-Robin</option></select>
            <div id="form3-team-wrap">
                <select id="form3-team" data-team-optional="false">
                    <option value="">No team restriction</option>
                    <option value="variant-fans" selected>Variant Fans</option>
                </select>
                <span id="form3-team-help"></span>
            </div>
            <input id="form3-rated" type="checkbox" checked>
            <div id="form3-variant-picker">
                <input id="form3-variant-search" type="search" aria-controls="form3-variant-results" aria-expanded="false">
                <select id="form3-variant">
                    <optgroup label="Favorites" data-kind="favorite">
                        <option value="community-favorite" data-kind="favorite">Favorite Community</option>
                    </optgroup>
                    <optgroup label="Site variants" data-kind="site">
                        <option value="chess" data-kind="site" selected>Chess</option>
                        <option value="atomic" data-kind="site">Atomic</option>
                        <option value="shogi" data-kind="site">Shogi</option>
                        <option value="racingkings" data-kind="site">Racing Kings</option>
                    </optgroup>
                    <optgroup label="Community variants" data-kind="community">
                        <option value="community-alpha" data-kind="community">Community Alpha</option>
                        <option value="custom-snails" data-kind="community">Simple Snails</option>
                    </optgroup>
                </select>
                <div id="form3-variant-results" role="listbox" hidden></div>
            </div>
            <span id="form3-system-help"></span>
            <div id="form3-rounds-wrap"></div>
            <span id="form3-rounds-label"></span>
            <select id="form3-rounds"><option value="0">0</option><option value="5">5</option></select>
            <span id="form3-rounds-help"></span>
            <div id="form3-rrMaxPlayers-wrap"></div>
            <select id="form3-rrMaxPlayers"><option value="0">0</option><option value="10">10</option></select>
            <span id="form3-rrMaxPlayers-help"></span>
            <div id="form3-rrApproval-wrap"></div>
            <div id="form3-roundInterval-wrap"></div>
            <select id="form3-roundInterval"><option value="auto">Automatic</option></select>
            <span id="form3-roundInterval-help"></span>
            <span id="form3-minutes-label"></span>
            <span id="form3-minutes-help"></span>
            <select id="form3-minutes"><option value="45">45</option><option value="90">90</option></select>
            <select id="form3-waitMinutes"><option value="5">5</option></select>
            <select id="form3-byoyomiPeriod"><option value="0">0</option><option value="1">1</option><option value="2">2</option><option value="3">3</option></select>
            <input id="startDate">
            <div id="form3-endDate-wrap"><input id="endDate"></div>
            <div id="form3-entry-wrap-a"></div>
            <div id="form3-entry-wrap-b"></div>
            <div id="form3-entry-wrap-c"></div>
            <div id="form3-swiss-pairings-wrap-a"></div>
            <select id="form3-entryMinRatedGames"><option value="0">0</option></select>
            <select id="form3-entryMinRating"><option value="0">0</option></select>
            <select id="form3-entryMaxRating"><option value="0">0</option></select>
            <select id="form3-entryMinAccountAgeDays"><option value="0">0</option></select>
            <textarea id="form3-forbiddenPairings"></textarea>
            <textarea id="form3-manualPairings"></textarea>
            <div id="tour-faq-arena"></div>
            <div id="tour-faq-rr"></div>
            <div id="tour-faq-swiss"></div>
        </form>
    `;
}

function changeValue(element: HTMLInputElement | HTMLSelectElement, value: string): void {
    element.value = value;
    element.dispatchEvent(new Event('change'));
}

beforeEach(() => {
    jest.setSystemTime(new Date('2026-08-06T10:00:00.000Z'));
    setupTournamentForm();
});

afterEach(() => {
    document.body.innerHTML = '';
});

test('cancel submits to its POST action instead of saving tournament settings', async () => {
    const form = document.getElementById('tournament-form') as HTMLFormElement;
    form.action = '/tournaments/abcd1234/edit';
    const cancel = document.createElement('button');
    cancel.type = 'submit';
    cancel.setAttribute('formaction', '/tournament/abcd1234/cancel');
    cancel.setAttribute('formmethod', 'post');
    cancel.formNoValidate = true;
    form.appendChild(cancel);
    const fetchMock = jest.fn(() => new Promise<Response>(() => {}));
    Object.defineProperty(window, 'fetch', { configurable: true, writable: true, value: fetchMock });
    initTournamentForm();

    form.dispatchEvent(new SubmitEvent('submit', { bubbles: true, cancelable: true, submitter: cancel }));

    expect(fetchMock).toHaveBeenCalledWith('/tournament/abcd1234/cancel', expect.objectContaining({ method: 'post' }));
});

describe('tournament schedule form', () => {
    test('keeps an Arena duration when the start date is chosen afterward', () => {
        initTournamentForm();

        const minutes = document.querySelector('#form3-minutes') as HTMLSelectElement;
        changeValue(minutes, '90');

        const startDate = document.querySelector('#startDate') as HTMLInputElement;
        changeValue(startDate, '2026-08-06T12:00:00.000Z');

        expect(minutes.value).toBe('90');
        expect((document.querySelector('#endDate') as HTMLInputElement).value).toBe('');
    });

    test('allows byoyomi periods only for variants with byoyomi clocks', () => {
        initTournamentForm();

        const variant = document.querySelector('#form3-variant') as HTMLSelectElement;
        const byoyomi = document.querySelector('#form3-byoyomiPeriod') as HTMLSelectElement;

        expect(byoyomi.value).toBe('0');
        expect(byoyomi.options[1].disabled).toBe(true);

        changeValue(variant, 'shogi');
        expect(byoyomi.options[1].disabled).toBe(false);
        changeValue(byoyomi, '3');

        changeValue(variant, 'racingkings');
        expect(byoyomi.value).toBe('0');
        expect(byoyomi.options[3].disabled).toBe(true);
    });
});

describe('team tournament form', () => {
    test('keeps an optional team restriction when switching Arena and fixed-round systems', () => {
        initTournamentForm();

        const system = document.querySelector('#form3-system') as HTMLSelectElement;
        const teamWrap = document.querySelector('#form3-team-wrap') as HTMLElement;
        const team = document.querySelector('#form3-team') as HTMLSelectElement;
        const help = document.querySelector('#form3-team-help') as HTMLElement;

        expect(teamWrap.style.display).toBe('');
        expect(team.disabled).toBe(false);
        expect(team.required).toBe(false);
        expect(team.value).toBe('variant-fans');
        expect(help.textContent).toContain('Optional');

        changeValue(system, '1');
        expect(team.required).toBe(true);
        expect(team.value).toBe('variant-fans');
        expect(help.textContent).toContain('Required');

        changeValue(system, '0');
        expect(team.required).toBe(false);
        expect(team.value).toBe('variant-fans');
    });
});

describe('tournament variant picker', () => {
    test('shows favorites and site variants before searching community variants', () => {
        initTournamentForm();

        const search = document.querySelector('#form3-variant-search') as HTMLInputElement;
        search.dispatchEvent(new Event('focus'));

        const results = document.querySelector('#form3-variant-results') as HTMLElement;
        expect(search.value).toBe('Chess');
        expect(results.hidden).toBe(false);
        expect(results.textContent).toContain('Favorites');
        expect(results.textContent).toContain('Favorite Community');
        expect(results.textContent).toContain('Site variants');
        expect(results.textContent).toContain('Atomic');
        expect(results.textContent).not.toContain('Community Alpha');
        expect(results.textContent).toContain('Type to search all public community variants.');
    });

    test('searches the full community catalogue by display name or internal key', () => {
        initTournamentForm();

        const search = document.querySelector('#form3-variant-search') as HTMLInputElement;
        search.value = 'alpha';
        search.dispatchEvent(new Event('input'));

        const results = document.querySelector('#form3-variant-results') as HTMLElement;
        expect(results.textContent).toContain('Community variants');
        expect(results.textContent).toContain('Community Alpha');

        search.value = 'custom-snails';
        search.dispatchEvent(new Event('input'));
        expect(results.textContent).toContain('Simple Snails');
    });

    test('selects a searched community variant with the keyboard', () => {
        initTournamentForm();

        const search = document.querySelector('#form3-variant-search') as HTMLInputElement;
        const select = document.querySelector('#form3-variant') as HTMLSelectElement;
        search.value = 'community alpha';
        search.dispatchEvent(new Event('input'));
        search.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));

        expect(select.value).toBe('community-alpha');
        expect(search.value).toBe('Community Alpha');
        expect(search.getAttribute('aria-expanded')).toBe('false');
    });

    test('keeps the visible picker in sync with programmatic select changes', () => {
        initTournamentForm();

        const search = document.querySelector('#form3-variant-search') as HTMLInputElement;
        const select = document.querySelector('#form3-variant') as HTMLSelectElement;
        changeValue(select, 'atomic');

        expect(search.value).toBe('Atomic');
    });
});
