import { sanitizeURL } from './url';
import { installCsrfProtection } from './csrf';
import { h, VNode } from 'snabbdom';
import './securitySignals';

import ffishModule, { FairyStockfish } from 'ffish-es6';

import ffishAliceModule from 'ffish-alice-es6';

import { _, i18n } from './i18n';
import { aboutView } from './about';
import { settingsView, hideSettings } from './settingsView';
import { challengeView, hideChallenge } from './challengeView';
import { notifyView, hideNotify } from './notifyView';
import { lobbyView } from './lobby';
import { inboxView } from './inbox';
import { forumView } from './forum';
import { roundView } from './round';
import { inviteView } from './invite';
import { botChallengeView } from './botChallenge';
import { directChallengeView } from './directChallenge';
import { renderGames } from './games';
import { editorView } from '@/editor/editor';
import { analysisView, embedView } from './analysis';
import { studyEmbedView, studyView } from './study/studyView';
import { initStudyIndex } from './study/studyIndex';
import { initPracticeIndex } from './practice';
import { puzzleView } from './puzzle';
import { profileView } from './profile';
import { tournamentView } from './tournament';
import { tournamentRRView } from './tournamentRR';
import { simulView } from './simul/simul';
import { initSimulForm } from './simul/simulForm';
import { calendarView } from './calendar';
import { pasteView, recordImportFfishError } from './paste';
import { myVariantsView } from './myVariants';
import { initAnalysisEngine } from './fairyStockfish';
import { statsView } from './stats';
import { volumeSettings, soundThemeSettings } from './sound';
import { notifyChessgroundResize, patch } from './document';
import { renderTimeago } from './datetime';
import { zenButtonView, zenModeSettings } from './zen';
import { PyChessModel } from './types';
import { roundView as bugRoundView } from './two-board/round/round';
import { analysisView as bugAnalysisView } from './two-board/analysis/analysis';
import {
    allVariantsIni,
    variantConfigIni,
    devVariants,
    loadCataloguedVariantsFromJson,
    splitVariantKey,
    variantGroups,
    VARIANTS,
} from './variants';
import { variantsIni } from './variantsIni';
import { showUsernameDialog } from './usernameDialog';
import { maybeShowGameCategoryIntro } from './gameCategoryIntro';
import { initTournamentForm } from './tournamentForm';
import { initUserMiniWidget } from './userMiniWidget';
import { initUblogLike } from './ublogLike';
import { initTopNavDisclosures } from './topNav';
import { initUblogMarkdown } from './ublogMarkdown';
import { initUblogEditor } from './ublogEditor';
import { initPushSubscription } from './push';
import { initCommunityVariantFavorites } from './communityVariants';
import { gameSearchView, initGameSearch } from './gameSearch';
import { initProfileActionOverflow } from './profileActionOverflow';
import { initVariantAuthors } from './variantAuthors';
import { initSearchBarDismissal } from './searchBar';
import { timelinePageView } from './timeline';
import { initAdminSystemMessages } from './adminSystemMessages';
import { hydrateHeaderPanel } from './headerPanel';

// redirect to correct URL except Heroku preview/dev apps
if (
    window.location.href.includes('heroku') &&
    !window.location.href.includes('-pr-') &&
    !window.location.href.includes('-dev-')
) {
    window.location.assign('https://www.pychess.org/');
}

function initModel(el: HTMLElement) {
    loadCataloguedVariantsFromJson(el.getAttribute('data-catalogued-variants'));

    // Remove twoBoards variants from variants on prod site until they stabilize
    if (el.getAttribute('data-dev') !== 'True') {
        Object.keys(variantGroups).forEach(g => {
            const group = variantGroups[g];
            devVariants.forEach(v => {
                const idx = group.variants.indexOf(v);
                if (idx > -1) group.variants.splice(idx, 1);
            });
        });
    }

    let ct = el.getAttribute('data-ct') ?? '';
    if (ct) ct = JSON.parse(ct);
    let board = el.getAttribute('data-board') ?? '';
    if (board) board = JSON.parse(board);
    return {
        ffish: {} as FairyStockfish,
        home: sanitizeURL(el.getAttribute('data-home')) ?? '',
        anon: el.getAttribute('data-anon') ?? '',
        profileid: el.getAttribute('data-profile') ?? '',
        profileRestricted: el.getAttribute('data-profile-restricted') === 'True',
        title: el.getAttribute('data-title') ?? '',
        variant: el.getAttribute('data-variant') ?? '',
        chess960: el.getAttribute('data-chess960') ?? '',
        rated: el.getAttribute('data-rated') ?? '',
        corr: el.getAttribute('data-corr') ?? '',
        level: parseInt('' + el.getAttribute('data-level')),
        username: el.getAttribute('data-username') ?? '',
        admin: el.getAttribute('data-admin') === 'True',
        gameId: el.getAttribute('data-gameid') ?? '',
        gameCategory: el.getAttribute('data-game-category') ?? 'all',
        tournamentId: el.getAttribute('data-tournamentid') ?? '',
        tournamentname: el.getAttribute('data-tournamentname') ?? '',
        simulId: el.getAttribute('data-simulid') ?? '',
        simulname: el.getAttribute('data-simulname') ?? '',
        tournamentcreator: el.getAttribute('data-tournamentcreator') ?? '',
        tournamentmanager: el.getAttribute('data-tournamentmanager') === 'True',
        tournamentteamid: el.getAttribute('data-tournamentteamid') ?? '',
        tournamentteamname: el.getAttribute('data-tournamentteamname') ?? '',
        inviter: el.getAttribute('data-inviter') ?? '',
        botChallengeStatus: el.getAttribute('data-bot-challenge-status') ?? '',
        botChallengeDeclineReason: el.getAttribute('data-bot-challenge-decline-reason') ?? '',
        botChallengeOpponent: el.getAttribute('data-bot-challenge-opponent') ?? '',
        botSupportedVariants: JSON.parse(el.getAttribute('data-bot-supported-variants') || 'null') as
            | string[]
            | null,
        challengeId: el.getAttribute('data-challengeid') ?? '',
        ply: parseInt('' + el.getAttribute('data-ply')),
        initialFen: el.getAttribute('data-initialfen') ?? '',
        ct: ct,
        board: board,

        wplayer: el.getAttribute('data-wplayer') ?? '',
        wtitle: el.getAttribute('data-wtitle') ?? '',
        wpatron: el.getAttribute('data-wpatron') === 'True',
        wrating: el.getAttribute('data-wrating') ?? '',
        wrdiff: parseInt('' + el.getAttribute('data-wrdiff')),
        wberserk: el.getAttribute('data-wberserk') ?? '',

        bplayer: el.getAttribute('data-bplayer') ?? '',
        btitle: el.getAttribute('data-btitle') ?? '',
        bpatron: el.getAttribute('data-bpatron') === 'True',
        brating: el.getAttribute('data-brating') ?? '',
        brdiff: parseInt('' + el.getAttribute('data-brdiff')),
        bberserk: el.getAttribute('data-bberserk') ?? '',

        wplayerB: el.getAttribute('data-wplayer-b') ?? '',
        wtitleB: el.getAttribute('data-wtitle-b') ?? '',
        wpatronB: el.getAttribute('data-wpatron-b') === 'True',
        wratingB: el.getAttribute('data-wrating-b') ?? '',

        bplayerB: el.getAttribute('data-bplayer-b') ?? '',
        btitleB: el.getAttribute('data-btitle-b') ?? '',
        bpatronB: el.getAttribute('data-bpatron-b') === 'True',
        bratingB: el.getAttribute('data-brating-b') ?? '',

        fen: el.getAttribute('data-fen') ?? '',
        posnum: parseInt('' + el.getAttribute('data-posnum')),
        base: parseFloat('' + el.getAttribute('data-base')),
        inc: parseInt('' + el.getAttribute('data-inc')),
        byo: parseInt('' + el.getAttribute('data-byo')),
        result: el.getAttribute('data-result') ?? '',
        status: parseInt('' + el.getAttribute('data-status')),
        tsystem: parseInt(el.getAttribute('data-tsystem') ?? '0') || 0,
        rounds: parseInt(el.getAttribute('data-rounds') ?? '0') || 0,
        date: el.getAttribute('data-date') ?? '',
        tv: el.getAttribute('data-view') === 'tv',
        embed: el.getAttribute('data-view') === 'embed',
        seekEmpty: el.getAttribute('data-seekempty') === 'True',
        tournamentDirector: el.getAttribute('data-tournamentdirector') === 'True',
        assetURL: el.getAttribute('data-asset-url') ?? '',
        nnueDownloadRoot: el.getAttribute('data-nnue-download-root') ?? '',
        puzzle: el.getAttribute('data-puzzle') ?? '',
        study: JSON.parse(el.getAttribute('data-study') || 'null'),
        blogs: el.getAttribute('data-blogs') ?? '',
        timeline: el.getAttribute('data-timeline') ?? '[]',
        corrGames: el.getAttribute('data-corrgames') ?? '',
        simulGames: el.getAttribute('data-simulgames') ?? '',
        simulHost: el.getAttribute('data-simulhost') === 'True',
        oauthUsernameSelection: el.getAttribute('data-oauth-id')
            ? {
                  oauth_id: el.getAttribute('data-oauth-id')!,
                  oauth_provider: el.getAttribute('data-oauth-provider')!,
                  oauth_username: el.getAttribute('data-oauth-username')!,
              }
            : null,
        pushVapidKey: el.getAttribute('data-vapid') ?? '',
        pushEnabled:
            el.getAttribute('data-corr-push-enabled') !== 'False' ||
            el.getAttribute('data-rr-push-enabled') === 'True',
    };
}

export function view(el: HTMLElement, model: PyChessModel): VNode {
    const { base: variant } = splitVariantKey(model.variant);
    const twoBoards = variant ? VARIANTS[variant].twoBoards : false;
    switch (el.getAttribute('data-view')) {
        case 'about':
            return h('div#main-wrap', aboutView(model));
        case 'level8win':
        case 'profile':
            return h('div#profile', profileView(model));
        case 'tv':
        case 'round':
            if (twoBoards) {
                return h('main#main-wrap.bug', bugRoundView(model));
            } else {
                return h('div#main-wrap', [h('main.round', roundView(model))]);
            }
        case 'embed':
            return h('div', model.study ? studyEmbedView(model) : embedView(model));
        case 'analysis':
            if (twoBoards) {
                return h('main#main-wrap.bug', bugAnalysisView(model));
            } else {
                return h('div#main-wrap', analysisView(model));
            }
        case 'study':
            return h('div#main-wrap', studyView(model));
        case 'puzzle':
            return h('div#main-wrap', puzzleView(model));
        case 'invite':
            return h('div#main-wrap', inviteView(model));
        case 'bot_challenge':
            return h('div#main-wrap', botChallengeView(model));
        case 'challenge':
            return h('div#main-wrap', directChallengeView(model));
        case 'editor':
            return h('div#main-wrap', editorView(model));
        case 'tournament':
            return h('div#main-wrap', [
                h('main.tour', model.tsystem === 1 ? tournamentRRView(model) : tournamentView(model)),
            ]);
        case 'simul':
            return h('div#main-wrap', [h('main.simul', simulView(model))]);
        case 'calendar':
            return h('div#calendar', calendarView());
        case 'games':
            return h('div', renderGames(model));
        case 'game-search':
            return h('div', gameSearchView(model));
        case 'paste':
            return h('div#main-wrap', pasteView(model));
        case 'my-variants':
            return h('div#main-wrap', myVariantsView(model));
        case 'stats':
            return h('div#stats', statsView());
        case 'inbox':
            return h('div#main-wrap', [inboxView(model)]);
        case 'forum':
            return h('div#main-wrap', [forumView(model)]);
        case 'timeline':
            return h('div#main-wrap', [timelinePageView(model)]);
        case 'thanks':
            return h('div#main-wrap', h('h2', _('Thank you for your support!')));
        default:
            return h('div#main-wrap', [h('main.lobby', lobbyView(model))]);
    }
}

function ffishModuleOptions(printErr?: (text: string) => void) {
    // Keep the generated WASM binary in lockstep with the cache-busted JS bundle.
    const script = document.querySelector<HTMLScriptElement>('script[src*="/static/pychess-variants.js"]');
    const version = script ? new URL(script.src, window.location.href).search : '';

    return {
        ...(printErr ? { printErr } : {}),
        locateFile: (path: string, prefix: string) =>
            path.endsWith('.wasm') ? `/static/${path}${version}` : prefix + path,
    };
}

function start() {
    const placeholder = document.getElementById('placeholder');
    if (placeholder && el) {
        const dataView = el.getAttribute('data-view') ?? '';
        // Check if we need to show username selection dialog
        if (model.oauthUsernameSelection && model.oauthUsernameSelection.oauth_id) {
            try {
                showUsernameDialog(model.oauthUsernameSelection);
                return; // Don't render the main app until username is selected
            } catch (error) {
                console.error('Error showing username dialog:', error);
                // Continue with normal app rendering if dialog fails
            }
        }

        const renderView = () => {
            patch(placeholder, view(el, model));
            // The controller must be mounted before the engine emits its startup handshake.
            if (['analysis', 'puzzle', 'study'].includes(dataView)) {
                void initAnalysisEngine().catch(error => console.warn(error));
            }
        };

        if (['round', 'analysis', 'study', 'puzzle', 'editor', 'tv', 'embed', 'paste'].includes(dataView)) {
            console.time('load ffish');
            const variantIni =
                dataView === 'paste'
                    ? allVariantsIni(variantsIni)
                    : variantConfigIni(variantsIni, model.variant);
            if (model['variant'] === 'alice') {
                const loadModule = ffishAliceModule(
                    dataView === 'paste' ? ffishModuleOptions(recordImportFfishError) : ffishModuleOptions(),
                );
                loadModule.then((loadedModule: any) => {
                    console.timeEnd('load ffish_alice');
                    loadedModule.loadVariantConfig(variantIni);
                    model.ffish = loadedModule;
                    renderView();
                });
            } else {
                const loadModule = ffishModule(
                    dataView === 'paste' ? ffishModuleOptions(recordImportFfishError) : ffishModuleOptions(),
                );
                loadModule.then((loadedModule: any) => {
                    console.timeEnd('load ffish');
                    loadedModule.loadVariantConfig(variantIni);
                    model.ffish = loadedModule;
                    renderView();
                });
            }
        } else {
            renderView();
            if (dataView === 'profile' || dataView === 'level8win') initProfileActionOverflow();
            if (dataView === 'game-search') initGameSearch(model);
        }
    }

    if (model['embed']) return;

    initUserMiniWidget(model.assetURL, model.username, model.anon);
    if (model.pushEnabled) void initPushSubscription(model.anon, model.pushVapidKey);
    initUblogLike();
    initUblogMarkdown();
    initUblogEditor();

    (document.querySelector('.hamburger') as HTMLElement).addEventListener('click', () => {
        document.querySelectorAll('.topnav a').forEach(nav => nav.classList.toggle('navbar-show'));
        (document.querySelector('.hamburger') as HTMLElement).classList.toggle('is-active');
    });

    renderTimeago();
    initTournamentForm();
    initSimulForm();
    initAdminSystemMessages();

    // searchbar
    const searchIcon = document.querySelector('.search-icon') as HTMLElement;
    const searchBar = document.querySelector('.search-bar') as HTMLElement;
    const searchInput = document.querySelector('#search-input') as HTMLInputElement;

    searchIcon.onclick = function () {
        searchBar.classList.toggle('active');
        if (searchBar.classList.contains('active'))
            // Add some delay so that the input won't eat the icon during the transition animation
            setTimeout(() => searchInput.focus(), 200);
    };

    initSearchBarDismissal(searchBar);

    function showResults(val: string) {
        const acResult = document.getElementById('ac-result') as HTMLElement;
        if (val.length < 4) {
            acResult.innerHTML = '';
            return;
        }
        const params = new URLSearchParams({ p: val.toString() });
        fetch('/api/names?' + params.toString())
            .then(res => res.json())
            .then((data: [username: string, title: string][]) => {
                // console.log(data);
                const list = data.map(([username, playerTitle]) => {
                    const title = playerTitle ? `<player-title>${playerTitle} </player-title>` : '';
                    return `<li><a class="user-link" href="${model['home']}/@/${username}">${title}${username}</a></li>`;
                });
                // console.log(list);
                acResult.innerHTML = '<ul class="box">' + list.join('') + '</ul>';
            })
            .catch(err => {
                console.warn('Something went wrong.', err);
            });
    }

    searchInput.addEventListener('keyup', function (e) {
        showResults(searchInput.value);
        if (e.keyCode === 13) {
            window.location.href = `${model['home']}/@/${encodeURIComponent(searchInput.value)}`;
        }
    });

    // Clicking outside settings panel closes it
    const settingsPanel = hydrateHeaderPanel(
        document.getElementById('settings-panel') as HTMLElement,
        settingsView(model['variant']),
    );
    var challengePanel = document.getElementById('challenge-panel') as HTMLElement;
    var notifyPanel = document.getElementById('notify-panel') as HTMLElement;
    if (model['anon'] !== 'True') {
        challengePanel = hydrateHeaderPanel(challengePanel, challengeView());
        notifyPanel = hydrateHeaderPanel(notifyPanel, notifyView());
    }

    document.addEventListener('click', function (event) {
        if (!settingsPanel.contains(event.target as Node)) hideSettings();
        if (model['anon'] !== 'True') {
            if (!challengePanel.contains(event.target as Node)) hideChallenge();
            if (!notifyPanel.contains(event.target as Node)) hideNotify();
        }
    });

    maybeShowGameCategoryIntro();
    initCommunityVariantFavorites(model.assetURL);
    initVariantAuthors();
    initStudyIndex();
    initPracticeIndex();

    patch(document.getElementById('zen-button') as HTMLElement, zenButtonView());
}

window.addEventListener('resize', notifyChessgroundResize);
window.addEventListener('pageshow', notifyChessgroundResize);

zenModeSettings.update();

function initLoginDropdown() {
    // Use event delegation for better reliability
    document.addEventListener('click', e => {
        const target = e.target as HTMLElement;

        // Handle login button clicks
        if (target.closest('.login-btn')) {
            e.preventDefault();
            e.stopPropagation();

            const loginDropdown = target.closest('.login-dropdown') as HTMLElement;
            if (loginDropdown) {
                const isOpen = loginDropdown.classList.contains('open');
                loginDropdown.classList.toggle('open');

                const loginBtn = loginDropdown.querySelector('.login-btn') as HTMLButtonElement;
                if (loginBtn) {
                    loginBtn.setAttribute('aria-expanded', (!isOpen).toString());
                }
            }
            return;
        }

        // Close dropdown when clicking outside
        const loginDropdown = document.querySelector('.login-dropdown.open') as HTMLElement;
        if (loginDropdown && !loginDropdown.contains(target)) {
            loginDropdown.classList.remove('open');
            const loginBtn = loginDropdown.querySelector('.login-btn') as HTMLButtonElement;
            if (loginBtn) {
                loginBtn.setAttribute('aria-expanded', 'false');
            }
        }
    });

    // Handle escape key
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            const loginDropdown = document.querySelector('.login-dropdown.open') as HTMLElement;
            if (loginDropdown) {
                loginDropdown.classList.remove('open');
                const loginBtn = loginDropdown.querySelector('.login-btn') as HTMLButtonElement;
                if (loginBtn) {
                    loginBtn.setAttribute('aria-expanded', 'false');
                    loginBtn.focus();
                }
            }
        }
    });

    // Provider-neutral /login redirects here so all callers can use the same chooser.
    if (window.location.hash === '#login') {
        const loginDropdown = document.querySelector('.login-dropdown') as HTMLElement;
        if (loginDropdown) {
            loginDropdown.classList.add('open');
            const loginBtn = loginDropdown.querySelector('.login-btn') as HTMLButtonElement;
            if (loginBtn) {
                loginBtn.setAttribute('aria-expanded', 'true');
                loginBtn.focus();
            }
        }

        window.history.replaceState(null, '', window.location.pathname + window.location.search);
    }
}

const el = document.getElementById('pychess-variants');
installCsrfProtection(el);
export const model: PyChessModel = el ? initModel(el) : initModel(new HTMLElement());

if (el instanceof Element) {
    // Always update sound theme before volume
    // Updating sound theme requires reloading sound files,
    // while updating volume does not
    soundThemeSettings.assetURL = model.assetURL;
    soundThemeSettings.update();
    volumeSettings.update();

    const lang = el.getAttribute('data-lang') ?? 'en';

    async function loadTranslations(): Promise<void> {
        try {
            const response = await fetch(model.assetURL + '/lang/' + lang + '/LC_MESSAGES/client.json');
            if (!response.ok) {
                throw new Error(`Translation request failed with status ${response.status}`);
            }
            const translation = await response.json();
            i18n.loadJSON(translation, 'messages');
            i18n.setLocale(lang);
            // console.log('Loaded translations for lang', lang);
        } catch (error) {
            console.error('Could not load translations for lang', lang);
            console.error(error);
            i18n.setLocale('');
        }
    }

    /* THE HEADER NAV IS WIRED BEFORE THE TRANSLATION FETCH, unlike everything below it. Its labels
       come from the server-rendered template, so it has no i18n dependency -- and `start()` only
       runs after an awaited `fetch` of client.json, which would leave the six menus dead for a
       round trip after first paint, exactly when a screen reader is building its buffer. */
    initTopNavDisclosures();

    void loadTranslations()
        .then(() => {
            start();
            initLoginDropdown();
        })
        .catch(error => {
            console.error('Could not start the client');
            console.error(error);
        });
}
