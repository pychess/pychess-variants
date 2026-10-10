import { _ } from './i18n';
import { alertDialog } from './alertDialog';
import { confirmDialog } from './confirmDialog';
import { splitVariantKey, VARIANTS } from './variants';

function tournamentFormErrorMessage(message: string): string {
    switch (message) {
        case 'Only public user-defined variants can be used in tournaments.':
            return _('Only public user-defined variants can be used in tournaments.');
        case 'Unknown tournament variant.': return _('Unknown tournament variant.');
        case 'Two-board variants are not supported in tournaments.':
            return _('Two-board variants are not supported in tournaments.');
        case 'Byoyomi is not supported for this tournament variant.':
            return _('Byoyomi is not supported for this tournament variant.');
        case 'Invalid tournament time control.': return _('Invalid tournament time control.');
        case 'Tournament team not found.': return _('Tournament team not found.');
        case 'You need the tournament permission in this team to create this tournament.':
            return _('You need the tournament permission in this team to create this tournament.');
        case 'Round-Robin and Swiss tournaments must belong to a team.':
            return _('Round-Robin and Swiss tournaments must belong to a team.');
        case 'You need the tournament permission in this team to manage this tournament.':
            return _('You need the tournament permission in this team to manage this tournament.');
        case 'Invalid Swiss round count.': return _('Invalid Swiss round count.');
        case 'Invalid tournament start date.': return _('Invalid tournament start date.');
        case 'Invalid tournament end date.': return _('Invalid tournament end date.');
        case 'Tournament start date must be in the future.': return _('Tournament start date must be in the future.');
        case 'Invalid tournament duration or start delay.': return _('Invalid tournament duration or start delay.');
        case 'Tournament end date must be after the start date.':
            return _('Tournament end date must be after the start date.');
        case 'Tournament name must be between 2 and 30 characters.':
            return _('Tournament name must be between 2 and 30 characters.');
        case 'Tournament description is limited to 1000 characters.':
            return _('Tournament description is limited to 1000 characters.');
        case 'Tournament password is limited to 30 characters.':
            return _('Tournament password is limited to 30 characters.');
        case 'Tournament starting position is too long.': return _('Tournament starting position is too long.');
        case 'This tournament cannot be edited by its creator.':
            return _('This tournament cannot be edited by its creator.');
        case 'Tournament creation requires a registered account.':
            return _('Tournament creation requires a registered account.');
        case 'Invalid Arena start delay.': return _('Invalid Arena start delay.');
        case 'Community Arenas can be scheduled at most 24 hours in advance.':
            return _('Community Arenas can be scheduled at most 24 hours in advance.');
        case 'Variant cannot be changed after the tournament has started.':
            return _('Variant cannot be changed after the tournament has started.');
        case 'Time control cannot be changed after the tournament has started.':
            return _('Time control cannot be changed after the tournament has started.');
        case 'Start date cannot be changed after the tournament has started.':
            return _('Start date cannot be changed after the tournament has started.');
        case 'Starting position cannot be changed after the tournament has started.':
            return _('Starting position cannot be changed after the tournament has started.');
    }

    let match = message.match(/^Swiss tournaments must have (\d+) to (\d+) rounds\.$/);
    if (match) return _('Swiss tournaments must have %1 to %2 rounds.', match[1], match[2]);
    match = message.match(/^Swiss round count cannot be lower than the current round \((\d+)\)\.$/);
    if (match) return _('Swiss round count cannot be lower than the current round (%1).', match[1]);
    match = message.match(/^Swiss forbidden pairings are limited to (\d+) lines\.$/);
    if (match) return _('Swiss forbidden pairings are limited to %1 lines.', match[1]);
    match = message.match(/^Swiss manual pairings are limited to (\d+) lines\.$/);
    if (match) return _('Swiss manual pairings are limited to %1 lines.', match[1]);
    match = message.match(/^Invalid Swiss manual pairing on line (\d+)\.$/);
    if (match) return _('Invalid Swiss manual pairing on line %1.', match[1]);
    match = message.match(/^Invalid Swiss manual pairing on line (\d+): a player cannot play themself\.$/);
    if (match) return _('Invalid Swiss manual pairing on line %1: a player cannot play themself.', match[1]);
    match = message.match(/^Invalid Swiss manual pairing on line (\d+): (.+) is used more than once\.$/);
    if (match) return _('Invalid Swiss manual pairing on line %1: %2 is used more than once.', match[1], match[2]);
    match = message.match(/^User-created Arenas must last between (\d+) and (\d+) minutes\.$/);
    if (match) return _('User-created Arenas must last between %1 and %2 minutes.', match[1], match[2]);

    if (message.startsWith('Community Arena schedule conflicts with the protected system tournament')) {
        return _('Community Arena schedule conflicts with a protected system tournament.');
    }
    return message;
}

type FlatpickrOptions = {
    enableTime: boolean;
    time_24hr: boolean;
    dateFormat: string;
    altInput: boolean;
    altFormat: string;
    minDate: string | Date;
    maxDate: Date;
    monthSelectorType: string;
    disableMobile: boolean;
};

type FlatpickrFunction = (element: HTMLElement, options: FlatpickrOptions) => void;

type FlatpickrInstance = {
    setDate: (date: Date | string, triggerChange?: boolean) => void;
};

type FlatpickrElement = HTMLInputElement & {
    _flatpickr?: FlatpickrInstance;
};

function flatpickrFunction(): FlatpickrFunction | undefined {
    return (window as Window & { flatpickr?: FlatpickrFunction }).flatpickr;
}

const SYSTEM_ARENA = '0';
const SYSTEM_RR = '1';
const SYSTEM_SWISS = '2';

type VariantPickerKind = 'favorite' | 'site' | 'community';

type VariantPickerEntry = {
    option: HTMLOptionElement;
    value: string;
    label: string;
    kind: VariantPickerKind;
    searchText: string;
};

const VARIANT_PICKER_FAVORITE_LIMIT = 12;
const VARIANT_PICKER_SEARCH_LIMIT = 80;

function normalizeSearchText(value: string): string {
    return value.trim().toLocaleLowerCase();
}

function initializeVariantPicker(variantSelect: HTMLSelectElement): void {
    const picker = document.getElementById('form3-variant-picker');
    const search = document.getElementById('form3-variant-search');
    const results = document.getElementById('form3-variant-results');
    if (
        !(picker instanceof HTMLElement) ||
        !(search instanceof HTMLInputElement) ||
        !(results instanceof HTMLElement)
    ) {
        return;
    }

    const entries: VariantPickerEntry[] = Array.from(variantSelect.options).map(option => {
        const rawKind = option.dataset.kind ?? option.parentElement?.getAttribute('data-kind') ?? 'site';
        const kind: VariantPickerKind =
            rawKind === 'favorite' || rawKind === 'community' ? rawKind : 'site';
        const label = option.textContent?.trim() || option.value;
        return {
            option,
            value: option.value,
            label,
            kind,
            searchText: normalizeSearchText(`${label} ${option.value}`),
        };
    });

    if (entries.length === 0) return;

    let visibleEntries: VariantPickerEntry[] = [];
    let activeIndex = -1;

    const selectedEntry = (): VariantPickerEntry =>
        entries.find(entry => entry.value === variantSelect.value) ?? entries[0];

    const syncSearchToSelection = (): void => {
        search.value = selectedEntry().label;
    };

    const setExpanded = (expanded: boolean): void => {
        search.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        results.hidden = !expanded;
        if (!expanded) {
            activeIndex = -1;
            search.removeAttribute('aria-activedescendant');
        }
    };

    const setActive = (index: number): void => {
        if (visibleEntries.length === 0) {
            activeIndex = -1;
            search.removeAttribute('aria-activedescendant');
            return;
        }
        activeIndex = Math.max(0, Math.min(index, visibleEntries.length - 1));
        results.querySelectorAll<HTMLElement>('.variant-picker-option').forEach((element, optionIndex) => {
            element.classList.toggle('is-active', optionIndex === activeIndex);
        });
        const active = results.querySelector<HTMLElement>(`#form3-variant-option-${activeIndex}`);
        if (active) {
            search.setAttribute('aria-activedescendant', active.id);
            if (typeof active.scrollIntoView === 'function') {
                active.scrollIntoView({ block: 'nearest' });
            }
        }
    };

    const chooseEntry = (entry: VariantPickerEntry): void => {
        variantSelect.value = entry.value;
        syncSearchToSelection();
        variantSelect.dispatchEvent(new Event('change', { bubbles: true }));
        setExpanded(false);
    };

    const appendGroup = (label: string, groupEntries: VariantPickerEntry[]): void => {
        if (groupEntries.length === 0) return;
        const heading = document.createElement('div');
        heading.className = 'variant-picker-group';
        heading.textContent = label;
        heading.setAttribute('role', 'presentation');
        results.append(heading);

        groupEntries.forEach(entry => {
            const index = visibleEntries.length;
            visibleEntries.push(entry);
            const row = document.createElement('button');
            row.type = 'button';
            row.id = `form3-variant-option-${index}`;
            row.className = 'variant-picker-option';
            row.setAttribute('role', 'option');
            row.setAttribute('aria-selected', entry.value === variantSelect.value ? 'true' : 'false');
            row.tabIndex = -1;

            const name = document.createElement('span');
            name.className = 'variant-picker-option-name';
            name.textContent = entry.label;
            row.append(name);

            if (entry.kind !== 'site' && normalizeSearchText(entry.value) !== normalizeSearchText(entry.label)) {
                const key = document.createElement('small');
                key.className = 'variant-picker-option-key';
                key.textContent = entry.value;
                row.append(key);
            }

            row.addEventListener('pointermove', () => setActive(index));
            row.addEventListener('click', () => chooseEntry(entry));
            results.append(row);
        });
    };

    const appendHint = (text: string): void => {
        const hint = document.createElement('div');
        hint.className = 'variant-picker-hint';
        hint.textContent = text;
        hint.setAttribute('role', 'presentation');
        results.append(hint);
    };

    const renderResults = (): void => {
        results.replaceChildren();
        visibleEntries = [];
        activeIndex = -1;
        search.removeAttribute('aria-activedescendant');

        const query = normalizeSearchText(search.value);
        const selected = selectedEntry();
        if (query === '' || query === normalizeSearchText(selected.label)) {
            const favoriteEntries = entries.filter(entry => entry.kind === 'favorite');
            const favorites =
                selected.kind === 'favorite'
                    ? [selected, ...favoriteEntries.filter(entry => entry.value !== selected.value)]
                    : favoriteEntries;
            const site = entries.filter(entry => entry.kind === 'site');
            if (selected.kind === 'community') appendGroup(_('Selected'), [selected]);
            appendGroup(_('Favorites'), favorites.slice(0, VARIANT_PICKER_FAVORITE_LIMIT));
            appendGroup(_('Site variants'), site);
            if (entries.some(entry => entry.kind === 'community')) {
                appendHint(_('Type to search all public community variants.'));
            }
        } else {
            const tokens = query.split(/\s+/).filter(Boolean);
            const matches = entries.filter(entry => tokens.every(token => entry.searchText.includes(token)));
            const limited = matches.slice(0, VARIANT_PICKER_SEARCH_LIMIT);
            appendGroup(_('Favorites'), limited.filter(entry => entry.kind === 'favorite'));
            appendGroup(_('Site variants'), limited.filter(entry => entry.kind === 'site'));
            appendGroup(_('Community variants'), limited.filter(entry => entry.kind === 'community'));
            if (matches.length === 0) {
                appendHint(_('No matching variants.'));
            } else if (matches.length > limited.length) {
                appendHint(_('Showing the first %1 matches. Refine your search.', VARIANT_PICKER_SEARCH_LIMIT));
            }
        }

        setExpanded(true);
        if (visibleEntries.length > 0) {
            const selectedIndex = visibleEntries.findIndex(entry => entry.value === variantSelect.value);
            setActive(selectedIndex >= 0 ? selectedIndex : 0);
        }
    };

    search.addEventListener('focus', () => {
        search.select();
        renderResults();
    });
    search.addEventListener('input', renderResults);
    search.addEventListener('keydown', event => {
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            if (results.hidden) renderResults();
            const delta = event.key === 'ArrowDown' ? 1 : -1;
            const startIndex = activeIndex < 0 ? (delta > 0 ? -1 : visibleEntries.length) : activeIndex;
            setActive(startIndex + delta);
        } else if (event.key === 'Enter' && !results.hidden && activeIndex >= 0) {
            event.preventDefault();
            chooseEntry(visibleEntries[activeIndex]);
        } else if (event.key === 'Escape') {
            event.preventDefault();
            syncSearchToSelection();
            setExpanded(false);
        }
    });

    variantSelect.addEventListener('change', syncSearchToSelection);
    document.addEventListener('pointerdown', event => {
        if (!(event.target instanceof Node) || picker.contains(event.target)) return;
        syncSearchToSelection();
        setExpanded(false);
    });

    syncSearchToSelection();
}

function nextAllowedDate(): Date {
    const date = new Date(Date.now() + 60_000);
    date.setSeconds(0, 0);
    return date;
}

function initializeFlatpickr(): void {
    const flatpickr = flatpickrFunction();
    if (typeof flatpickr !== 'function') return;
    const minDate = nextAllowedDate();

    document.querySelectorAll<HTMLElement>('.flatpickr').forEach(element => {
        flatpickr(element, {
            enableTime: true,
            time_24hr: true,
            dateFormat: 'Z',
            altInput: true,
            altFormat: 'Y-m-d h:i K',
            minDate,
            maxDate: new Date(Date.now() + 1000 * 3600 * 24 * 31 * 6),
            monthSelectorType: 'static',
            disableMobile: true,
        });
    });
}

function setVisible(element: HTMLElement | null, visible: boolean): void {
    if (element) {
        element.style.display = visible ? '' : 'none';
    }
}

function setDisabled(
    elements: Array<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement | null>,
    disabled: boolean,
): void {
    elements.forEach(element => {
        if (element) {
            element.disabled = disabled;
        }
    });
}

function readDateValue(element: HTMLInputElement | null): Date | null {
    if (!element || element.value.trim() === '') return null;
    const date = new Date(element.value);
    return Number.isNaN(date.getTime()) ? null : date;
}

function writeDateValue(element: FlatpickrElement | null, date: Date): void {
    if (!element) return;
    if (element._flatpickr) {
        element._flatpickr.setDate(date, false);
        return;
    }
    element.value = date.toISOString();
}

function setMinutesValue(minutesSelect: HTMLSelectElement, minutes: number): void {
    const normalized = `${Math.max(1, minutes)}`;
    const existing = Array.from(minutesSelect.options).find(option => option.value === normalized);
    const previousCustom = minutesSelect.querySelector("option[data-custom='true']");
    if (!existing) {
        if (previousCustom) previousCustom.remove();
        const option = document.createElement('option');
        option.value = normalized;
        option.textContent = `${normalized} minutes (custom)`;
        option.dataset.custom = 'true';
        minutesSelect.append(option);
    }
    minutesSelect.value = normalized;
}

export function initTournamentForm(): void {
    initializeFlatpickr();

    const form = document.getElementById('tournament-form');
    if (!(form instanceof HTMLFormElement)) return;

    const abortButton = document.getElementById('tournament-abort');
    if (abortButton instanceof HTMLButtonElement) {
        abortButton.addEventListener('click', async () => {
            const confirmed = await confirmDialog({
                title: _('Abort tournament'),
                text: _('This will end the tournament immediately. This action cannot be undone.'),
                confirmText: _('Abort tournament'),
                danger: true,
            });
            if (!confirmed) return;

            const action = abortButton.dataset.action;
            const returnUrl = abortButton.dataset.returnUrl;
            if (!action || !returnUrl) return;

            abortButton.disabled = true;
            try {
                const response = await fetch(action, {
                    method: 'POST',
                    credentials: 'same-origin',
                });
                if (!response.ok) {
                    const message = (await response.text()).trim();
                    void alertDialog({ text: message || _('Tournament abort failed.') });
                    return;
                }
                window.location.assign(returnUrl);
            } catch {
                void alertDialog({ text: _('Tournament abort failed.') });
            } finally {
                abortButton.disabled = false;
            }
        });
    }

    const deleteButton = document.getElementById('tournament-delete');
    if (deleteButton instanceof HTMLButtonElement) {
        deleteButton.addEventListener('click', async () => {
            const confirmed = await confirmDialog({
                title: 'Delete tournament',
                text: 'Permanently delete this empty tournament, its registrations, and its chat?',
                confirmText: 'Delete tournament',
                danger: true,
            });
            if (!confirmed) return;

            const action = deleteButton.dataset.action;
            const returnUrl = deleteButton.dataset.returnUrl;
            if (!action || !returnUrl) return;

            deleteButton.disabled = true;
            try {
                const response = await fetch(action, {
                    method: 'POST',
                    credentials: 'same-origin',
                });
                if (!response.ok) {
                    const message = (await response.text()).trim();
                    void alertDialog({ text: message || 'Tournament deletion failed.' });
                    return;
                }
                window.location.assign(returnUrl);
            } catch {
                void alertDialog({ text: 'Tournament deletion failed.' });
            } finally {
                deleteButton.disabled = false;
            }
        });
    }

    const system = document.getElementById('form3-system');
    const teamWrap = document.getElementById('form3-team-wrap');
    const teamSelect = document.getElementById('form3-team');
    const teamHelp = document.getElementById('form3-team-help');
    const rated = document.getElementById('form3-rated');
    const variantSelect = document.getElementById('form3-variant');
    const byoyomiPeriod = document.getElementById('form3-byoyomiPeriod');
    const systemHelp = document.getElementById('form3-system-help');
    const roundsWrap = document.getElementById('form3-rounds-wrap');
    const roundsLabel = document.getElementById('form3-rounds-label');
    const rounds = document.getElementById('form3-rounds');
    const roundsHelp = document.getElementById('form3-rounds-help');
    const rrMaxPlayersWrap = document.getElementById('form3-rrMaxPlayers-wrap');
    const rrMaxPlayers = document.getElementById('form3-rrMaxPlayers');
    const rrMaxPlayersHelp = document.getElementById('form3-rrMaxPlayers-help');
    const rrApprovalWrap = document.getElementById('form3-rrApproval-wrap');
    const roundIntervalWrap = document.getElementById('form3-roundInterval-wrap');
    const roundInterval = document.getElementById('form3-roundInterval');
    const roundIntervalHelp = document.getElementById('form3-roundInterval-help');
    const minutesLabel = document.getElementById('form3-minutes-label');
    const minutesHelp = document.getElementById('form3-minutes-help');
    const minutesSelect = document.getElementById('form3-minutes');
    const waitMinutesSelect = document.getElementById('form3-waitMinutes');
    const startDateInput = document.getElementById('startDate');
    const endDateWrap = document.getElementById('form3-endDate-wrap');
    const endDateDisplayWrap = document.getElementById('form3-endDate-display-wrap');
    const endDateInput = document.getElementById('endDate');
    const entryWrapA = document.getElementById('form3-entry-wrap-a');
    const entryWrapB = document.getElementById('form3-entry-wrap-b');
    const entryWrapC = document.getElementById('form3-entry-wrap-c');
    const swissPairingsWrapA = document.getElementById('form3-swiss-pairings-wrap-a');
    const ratingEntryConditionInputs = [
        document.getElementById('form3-entryMinRatedGames'),
        document.getElementById('form3-entryMinRating'),
        document.getElementById('form3-entryMaxRating'),
    ];
    const entryConditionInputs = [
        ...ratingEntryConditionInputs,
        document.getElementById('form3-entryMinAccountAgeDays'),
    ];
    const swissPairingInputs = [
        document.getElementById('form3-forbiddenPairings'),
        document.getElementById('form3-manualPairings'),
    ];
    const arenaFaq = document.getElementById('tour-faq-arena');
    const rrFaq = document.getElementById('tour-faq-rr');
    const swissFaq = document.getElementById('tour-faq-swiss');
    const teamSelectInitiallyDisabled =
        teamSelect instanceof HTMLSelectElement && teamSelect.disabled;
    const teamSelectOptional =
        teamSelect instanceof HTMLSelectElement && teamSelect.dataset.teamOptional === 'true';

    if (
        !(system instanceof HTMLSelectElement) ||
        !(roundsWrap instanceof HTMLElement) ||
        !(rounds instanceof HTMLSelectElement) ||
        !(rrMaxPlayersWrap instanceof HTMLElement) ||
        !(rrMaxPlayers instanceof HTMLSelectElement) ||
        !(roundIntervalWrap instanceof HTMLElement) ||
        !(roundInterval instanceof HTMLSelectElement) ||
        !(minutesSelect instanceof HTMLSelectElement) ||
        !(waitMinutesSelect instanceof HTMLSelectElement)
    ) {
        return;
    }

    if (variantSelect instanceof HTMLSelectElement) {
        initializeVariantPicker(variantSelect);
    }

    const syncRatingPolicy = (): void => {
        if (!(rated instanceof HTMLInputElement) || !(variantSelect instanceof HTMLSelectElement)) return;
        const { base } = splitVariantKey(variantSelect.value);
        const ratingEnabled = VARIANTS[base]?.ratingEnabled ?? false;
        rated.disabled = !ratingEnabled;
        if (!ratingEnabled) rated.checked = false;
        ratingEntryConditionInputs.forEach(element => {
            if (element instanceof HTMLInputElement || element instanceof HTMLSelectElement) {
                element.disabled = !ratingEnabled;
                if (!ratingEnabled) element.value = '0';
            }
        });
    };

    const syncByoyomiPolicy = (): void => {
        if (!(variantSelect instanceof HTMLSelectElement) || !(byoyomiPeriod instanceof HTMLSelectElement)) return;
        const { base } = splitVariantKey(variantSelect.value);
        const supportsByoyomi = VARIANTS[base]?.rules.defaultTimeControl === 'byoyomi';
        Array.from(byoyomiPeriod.options).forEach(option => {
            option.disabled = !supportsByoyomi && option.value !== '0';
        });
        if (!supportsByoyomi) byoyomiPeriod.value = '0';
    };

    const effectiveStartDate = (): Date | null => {
        const customStart = readDateValue(startDateInput instanceof HTMLInputElement ? startDateInput : null);
        if (customStart) return customStart;
        const waitMinutes = parseInt(waitMinutesSelect.value || '0', 10);
        if (Number.isNaN(waitMinutes)) return null;
        return new Date(Date.now() + waitMinutes * 60_000);
    };

    const syncEndDateFromSchedule = (): void => {
        if (system.value !== SYSTEM_RR) return;
        if (!(endDateInput instanceof HTMLInputElement)) return;
        const startDate = effectiveStartDate();
        const minutes = parseInt(minutesSelect.value || '0', 10);
        if (!startDate || Number.isNaN(minutes) || minutes <= 0) return;
        writeDateValue(endDateInput as FlatpickrElement, new Date(startDate.getTime() + minutes * 60_000));
    };

    const syncMinutesFromEndDate = (): void => {
        if (system.value !== SYSTEM_RR) return;
        if (!(endDateInput instanceof HTMLInputElement)) return;
        const endDate = readDateValue(endDateInput);
        const startDate = effectiveStartDate();
        if (!endDate || !startDate) return;
        const minutes = Math.max(1, Math.ceil((endDate.getTime() - startDate.getTime()) / 60_000));
        setMinutesValue(minutesSelect, minutes);
    };

    const updateFormBySystem = (): void => {
        const systemValue = system.value;
        const isArena = systemValue === SYSTEM_ARENA;
        const isRR = systemValue === SYSTEM_RR;
        const isSwiss = systemValue === SYSTEM_SWISS;

        setVisible(roundsWrap, !isArena && !isRR);
        setVisible(rrMaxPlayersWrap, isRR);
        setVisible(rrApprovalWrap, isRR);
        setVisible(roundIntervalWrap, !isArena);
        rounds.disabled = isArena || isRR;
        rrMaxPlayers.disabled = !isRR;
        roundInterval.disabled = isArena;
        setVisible(teamWrap, true);
        if (teamSelect instanceof HTMLSelectElement) {
            teamSelect.disabled = teamSelectInitiallyDisabled;
            teamSelect.required = !isArena && !teamSelectInitiallyDisabled && !teamSelectOptional;
        }
        if (teamHelp) {
            teamHelp.textContent = isArena
                ? _('Optional. Select a team to restrict this Arena to current team members.')
                : _('Required for production Round-Robin and Swiss. Only current team members can join team tournaments.');
        }

        if (isArena) {
            rounds.value = '0';
            roundInterval.value = 'auto';
        } else if (isRR) {
            rounds.value = '0';
            if (rrMaxPlayers.value === '0') rrMaxPlayers.value = '10';
        } else if (rounds.value === '0') {
            rounds.value = '5';
        }

        if (systemHelp) {
            if (isArena) {
                systemHelp.textContent =
                    _('Arena runs continuously until the clock expires. Players rejoin from the lobby after each game.');
            } else if (isRR) {
                systemHelp.textContent =
                    _('Round-Robin is team-owned and uses a maximum player cap. The joined field is frozen at start, then the full single-cycle round count is derived automatically.');
            } else {
                systemHelp.textContent =
                    _('Swiss is team-owned and fixed-round. Players are paired by score with color balancing and bye handling when needed.');
            }
        }

        if (roundsLabel) {
            roundsLabel.textContent = _('Rounds (Swiss)');
        }

        if (roundsHelp) {
            roundsHelp.textContent = _('Choose how many rounds the Swiss tournament will play.');
        }

        if (rrMaxPlayersHelp) {
            rrMaxPlayersHelp.textContent =
                _('Choose the maximum Round-Robin field size. When the tournament starts, rounds are derived from the players who joined.');
        }

        if (roundIntervalHelp) {
            roundIntervalHelp.textContent = isArena
                ? _('Automatic is based on time control and clamped to 10s-1m.')
                : _('Automatic is based on time control and clamped to 10s-1m. With manual rounds, the organizer starts the next round from the tournament controls.');
        }

        if (minutesLabel) {
            minutesLabel.textContent = isArena ? _('Duration') : _('Estimated duration');
        }

        if (minutesHelp) {
            minutesHelp.textContent = isArena
                ? _('Arena uses this as a hard limit.')
                : _('Swiss and Round-Robin only use this as an estimate for scheduling and display. The event still finishes by rounds.');
        }

        setVisible(endDateWrap, isRR);
        setVisible(endDateDisplayWrap, isRR);
        setDisabled([endDateInput instanceof HTMLInputElement ? endDateInput : null], !isRR);

        setVisible(entryWrapA, true);
        setVisible(entryWrapB, true);
        setVisible(entryWrapC, true);
        setVisible(swissPairingsWrapA, isSwiss);
        setDisabled(
            entryConditionInputs.map(element =>
                element instanceof HTMLInputElement ||
                element instanceof HTMLTextAreaElement ||
                element instanceof HTMLSelectElement
                    ? element
                    : null,
            ),
            false,
        );
        setDisabled(
            swissPairingInputs.map(element =>
                element instanceof HTMLInputElement ||
                element instanceof HTMLTextAreaElement ||
                element instanceof HTMLSelectElement
                    ? element
                    : null,
            ),
            !isSwiss,
        );

        setVisible(arenaFaq, isArena);
        setVisible(rrFaq, isRR);
        setVisible(swissFaq, isSwiss);
        syncRatingPolicy();
        if (isRR) syncEndDateFromSchedule();
    };

    system.addEventListener('change', updateFormBySystem);
    if (variantSelect instanceof HTMLSelectElement) {
        variantSelect.addEventListener('change', syncRatingPolicy);
        variantSelect.addEventListener('change', syncByoyomiPolicy);
    }
    minutesSelect.addEventListener('change', syncEndDateFromSchedule);
    waitMinutesSelect.addEventListener('change', syncEndDateFromSchedule);
    if (startDateInput instanceof HTMLInputElement) {
        startDateInput.addEventListener('change', () => {
            if (readDateValue(endDateInput instanceof HTMLInputElement ? endDateInput : null)) {
                syncMinutesFromEndDate();
            } else {
                syncEndDateFromSchedule();
            }
        });
    }
    if (endDateInput instanceof HTMLInputElement) {
        endDateInput.addEventListener('change', syncMinutesFromEndDate);
    }
    form.addEventListener('submit', async event => {
        event.preventDefault();
        const submitter = event.submitter instanceof HTMLButtonElement ? event.submitter : null;
        if (submitter) submitter.disabled = true;
        try {
            const response = await fetch(submitter?.getAttribute('formaction') || form.action, {
                method: submitter?.getAttribute('formmethod') || form.method || 'POST',
                body: new FormData(form),
                credentials: 'same-origin',
            });
            if (!response.ok) {
                const message = (await response.text()).trim();
                void alertDialog({
                    text: message ? tournamentFormErrorMessage(message) : _('Tournament form submission failed.'),
                });
                return;
            }
            window.location.assign('/tournaments');
        } catch {
            void alertDialog({ text: _('Tournament form submission failed.') });
        } finally {
            if (submitter) submitter.disabled = false;
        }
    });
    updateFormBySystem();
    syncByoyomiPolicy();
}
