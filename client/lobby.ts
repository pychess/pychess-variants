import { WebsocketHeartbeatJs } from './socket/socket';

import { h, VNode } from 'snabbdom';

import { Api } from 'chessgroundx/api';
import { Chessground } from 'chessgroundx';

import { JSONObject } from './types';
import { _, ngettext, languageSettings } from './i18n';
import { patch } from './document';
import { boardSettings } from './boardSettings';
import {
    canRateStart,
    CATALOGUED_VARIANT_ICON,
    devVariants,
    disabledVariantsForCreateMode,
    enabledVariants,
    isCataloguedVariant,
    unsupportedAiVariants,
    VARIANTS,
    selectVariant,
    splitVariantKey,
    Variant,
    variantGroups,
    variantKey,
} from './variants';
import { timeControlStr, changeTabs, setAriaTabClick } from './view';
import { notify } from './notification';
import { PyChessModel } from './types';
import { model } from './main';
import { MsgBoard } from './messages';
import { variantPanels } from './lobby/layer1';
import { shouldShowRatingRange } from './lobby/ratingRange';
import {
    Post,
    Stream,
    Spotlight,
    MsgInviteCreated,
    MsgDirectChallengeCreated,
    MsgHostCreated,
    MsgGetSeeks,
    MsgNewGame,
    MsgGameInProgress,
    MsgUserConnected,
    MsgPing,
    MsgError,
    MsgShutdown,
    MsgCounter,
    MsgStreams,
    MsgSpotlights,
    Seek,
    CreateMode,
    TvGame,
    TcMode,
    MsgLeaderboard,
    MsgTournamentWinners,
    LeaderboardEntry,
    TournamentWinnerEntry,
} from './lobbyType';
import { validFen, uci2LastMove } from './chess';
import { seekViewBughouse, switchEnablingLobbyControls } from './two-board/lobby';
import { handleOngoingGameEvents, Game, gameViewPlaying, compareGames } from './nowPlaying';
import { sizeMiniBoardHost } from './miniBoard';
import { createWebsocket } from '@/socket/webSocketUtils';
import { displayUsername, isAnonUsername } from './user';
import { confirmDialog } from './confirmDialog';
import { alertDialog } from './alertDialog';
import { fetchTimeline, LiveTimelinePanel, timelineEntriesFromModel, timelinePanel } from './timeline';

const autoPairingTCs: [number, number, number][] = [
    [1, 0, 0],
    [3, 0, 0],
    [3, 2, 0],
    [5, 5, 0],
    [15, 10, 0],
    [2, 15, 1],
    [10, 30, 1],
];

function allowedVariantsForCategory(gameCategory: string): Set<string> | null {
    if (gameCategory === 'all') return null;
    const group = variantGroups[gameCategory];
    if (!group) return null;
    return new Set(group.variants);
}

function matchesGameCategory(category: string | string[] | undefined, gameCategory: string): boolean {
    if (gameCategory === 'all') return true;
    const normalized = category ?? 'all';
    const categories = Array.isArray(normalized) ? normalized : [normalized];
    return categories.includes('all') || categories.includes(gameCategory);
}

export function createModeStr(mode: CreateMode) {
    switch (mode) {
        case 'playAI':
            return _('Play with AI');
        case 'playBOT':
            return _('Play with a BOT');
        case 'playFriend':
            return _('Play with a friend');
        case 'createHost':
            return _('Host a game for others');
        case 'createGame':
            return _('Create a game');
        default:
            return '';
    }
}

export function disableCorr(disable: boolean) {
    document.querySelectorAll('#tc option').forEach((opt: HTMLInputElement) => {
        if (opt.value == 'corr') {
            opt.disabled = disable;
        }
    });
}

export class LobbyController {
    sock: WebsocketHeartbeatJs;
    home: string;
    assetURL: string;
    // player;
    // logged_in;
    username: string;
    profileid: string;
    anon: boolean;
    title: string;
    tournamentDirector: boolean;
    gameCategory: string;
    allowedVariants: Set<string> | null;
    botSupportedVariants: Set<string> | null;
    fen: string;
    createMode: CreateMode;
    tcMode: TcMode;
    validGameData: boolean;
    readyState: number;
    seeks: Seek[];
    streams: VNode | HTMLElement;
    spotlights: VNode | HTMLElement;
    timeline: LiveTimelinePanel | null;
    leaders: VNode | HTMLElement;
    winners: VNode | HTMLElement;
    dialogHeaderEl: VNode | HTMLElement;
    autoPairingActions: VNode | HTMLElement | null;
    tvGame: TvGame;
    tvGameId: string;
    tvGameChessground: Api;
    minutesValues = [
        0,
        1 / 4,
        1 / 2,
        3 / 4,
        1,
        3 / 2,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
        16,
        17,
        18,
        19,
        20,
        25,
        30,
        35,
        40,
        45,
        60,
        75,
        90,
    ];
    incrementValues = [
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 25, 30, 35, 40, 45, 60, 90,
    ];
    minutesStrings = ['0', '¼', '½', '¾'];
    daysValues = [1, 2, 3, 5, 7, 10, 14];

    constructor(el: HTMLElement, model: PyChessModel) {
        console.log('LobbyController constructor', el, model);

        this.home = model['home'];
        this.assetURL = model['assetURL'];
        this.username = model['username'];
        this.anon = model['anon'] === 'True';
        this.title = model['title'];
        this.tournamentDirector = model['tournamentDirector'];
        this.gameCategory = model['gameCategory'] ?? 'all';
        this.allowedVariants = allowedVariantsForCategory(this.gameCategory);
        this.botSupportedVariants = model.botSupportedVariants === null ? null : new Set(model.botSupportedVariants);
        this.fen = model['fen'];
        this.profileid = model['profileid'];
        this.createMode = 'createGame';
        this.tcMode = 'real';
        this.validGameData = false;
        this.seeks = [];

        const onOpen = () => {
            console.log('onOpen()');
        };

        this.sock = createWebsocket(
            'wsl',
            onOpen,
            () => {},
            () => {},
            (e: MessageEvent) => this.onMessage(e),
        );

        patch(document.querySelector('.seekbuttons') as HTMLElement, h('div.seekbuttons', this.renderSeekButtons()));
        patch(document.querySelector('.seekdialog') as HTMLElement, this.renderSeekDialog());

        const id01modal = document.getElementById('id01') as HTMLElement;
        document.addEventListener('click', event => {
            if ((event.target as HTMLElement) == id01modal) this.closeSeekDialog();
        });
        id01modal.addEventListener('cancel', this.closeSeekDialog);

        patch(document.getElementById('variants-catalog') as HTMLElement, variantPanels(this));

        this.streams = document.getElementById('streams') as HTMLElement;

        this.spotlights = document.getElementById('spotlights') as HTMLElement;
        const timelineElement = document.getElementById('timeline');
        this.timeline = timelineElement === null ? null : new LiveTimelinePanel(timelineElement);
        this.leaders = document.getElementById('leaders') as HTMLElement;
        this.winners = document.getElementById('winners') as HTMLElement;

        this.dialogHeaderEl = document.getElementById('header-block') as HTMLElement;

        // challenge (or CREATE GAME from the main menu)
        if (this.profileid !== '') {
            if (this.title === 'BOT') {
                this.createMode = this.profileid === 'Fairy-Stockfish' ? 'playAI' : 'playBOT';
                this.renderVariantsDropDown(model.variant, this.disabledVariants());
            } else if (this.profileid === 'Invite-friend') this.createMode = 'playFriend';
            document.getElementById('game-mode')!.style.display =
                this.anon || this.title === 'BOT' ? 'none' : 'inline-flex';
            this.updateRatingRangeVisibility();
            this.renderDialogHeader(_('Challenge %1 to a game', this.profileid));
            document.getElementById('ailevel')!.style.display = this.createMode === 'playAI' ? 'block' : 'none';
            document.getElementById('rmplay-block')!.style.display = this.createMode === 'playAI' ? 'block' : 'none';
            (document.getElementById('id01') as HTMLDialogElement).showModal();
            document.getElementById('color-button-group')!.style.display = 'block';
            document.getElementById('create-button')!.style.display = 'none';

            // CREATE GAME from the main menu
            if (this.profileid === 'any#') {
                this.profileid = '';
                this.createGame(model.variant);
            }
        }

        // Seek from Editor with custom start position
        if (this.fen !== '' && this.profileid === '') {
            this.createGame(model.variant);
        }

        setAriaTabClick('lobby_tab');

        const tabId = localStorage.lobby_tab ?? 'tab-1';
        let initialEl = document.getElementById(tabId) as HTMLElement;
        if (initialEl === null) initialEl = document.getElementById('tab-1') as HTMLElement;
        initialEl.setAttribute('aria-selected', 'true');
        (
            initialEl!.parentNode!.parentNode!.querySelector(
                `#${initialEl.getAttribute('aria-controls')}`,
            )! as HTMLElement
        ).style.display = 'block';

        const e = document.getElementById('fen') as HTMLInputElement;
        if (this.fen !== '') {
            e.value = this.fen;
            this.setFen();
        }

        if (!this.anon) {
            this.renderAutoPairingTable();
            this.autoPairingActions = document.querySelector('div.auto-pairing-actions') as HTMLElement | null;
        }

        boardSettings.assetURL = this.assetURL;
    }

    doSend(message: JSONObject) {
        // console.log("---> lobby doSend():", message);
        this.sock.send(JSON.stringify(message));
    }

    createSeekMsg(
        variant: string,
        color: string,
        fen: string,
        minutes: number,
        increment: number,
        byoyomiPeriod: number,
        day: number,
        chess960: boolean,
        rated: boolean,
        rrMin: number,
        rrMax: number,
    ) {
        this.doSend({
            type: 'create_seek',
            user: this.username,
            target: this.profileid,
            variant: variant,
            fen: fen,
            minutes: minutes,
            increment: increment,
            byoyomiPeriod: byoyomiPeriod,
            day: day,
            rated: rated,
            rrmin: rrMin,
            rrmax: rrMax,
            chess960: chess960,
            color: color,
        });
    }

    createInviteFriendMsg(
        variant: string,
        color: string,
        fen: string,
        minutes: number,
        increment: number,
        byoyomiPeriod: number,
        day: number,
        chess960: boolean,
        rated: boolean,
    ) {
        this.doSend({
            type: 'create_invite',
            user: this.username,
            target: 'Invite-friend',
            variant: variant,
            fen: fen,
            minutes: minutes,
            increment: increment,
            byoyomiPeriod: byoyomiPeriod,
            day: day,
            rated: rated,
            chess960: chess960,
            color: color,
        });
    }

    createBOTChallengeMsg(
        variant: string,
        color: string,
        fen: string,
        minutes: number,
        increment: number,
        byoyomiPeriod: number,
        chess960: boolean,
        rated: boolean,
    ) {
        this.doSend({
            type: 'create_bot_challenge',
            user: this.username,
            target: 'BOT_challenge',
            variant: variant,
            fen: fen,
            minutes: minutes,
            increment: increment,
            byoyomiPeriod: byoyomiPeriod,
            rated: rated,
            chess960: chess960,
            color: color,
            profileid: this.profileid,
        });
    }

    createAIChallengeMsg(
        variant: string,
        color: string,
        fen: string,
        minutes: number,
        increment: number,
        byoyomiPeriod: number,
        level: number,
        rm: boolean,
        chess960: boolean,
        rated: boolean,
    ) {
        this.doSend({
            type: 'create_ai_challenge',
            rm: rm,
            user: this.username,
            variant: variant,
            fen: fen,
            minutes: minutes,
            increment: increment,
            byoyomiPeriod: byoyomiPeriod,
            rated: rated,
            level: level,
            chess960: chess960,
            color: color,
            profileid: this.profileid === '' ? 'Fairy-Stockfish' : this.profileid,
        });
    }

    createHostMsg(
        variant: string,
        color: string,
        fen: string,
        minutes: number,
        increment: number,
        byoyomiPeriod: number,
        chess960: boolean,
        rated: boolean,
    ) {
        this.doSend({
            type: 'create_host',
            user: this.username,
            target: 'Invite-friend',
            variant: variant,
            fen: fen,
            minutes: minutes,
            increment: increment,
            byoyomiPeriod: byoyomiPeriod,
            rated: rated,
            chess960: chess960,
            color: color,
        });
    }

    isNewSeek(
        variant: string,
        color: string,
        fen: string,
        minutes: number,
        increment: number,
        byoyomiPeriod: number,
        day: number,
        chess960: boolean,
        rated: boolean,
    ) {
        // console.log("isNewSeek()?", variant, color, fen, minutes, increment, byoyomiPeriod, chess960, rated);
        // console.log(this.seeks);
        return !this.seeks.some(
            seek =>
                seek.user === this.username &&
                seek.variant === variant &&
                seek.fen === fen &&
                seek.color === color &&
                seek.base === minutes &&
                seek.inc === increment &&
                seek.byoyomi === byoyomiPeriod &&
                seek.day === day &&
                seek.chess960 === chess960 &&
                seek.rated === rated,
        );
    }

    closeSeekDialog() {
        (document.getElementById('id01') as HTMLDialogElement).close();
        (document.activeElement as HTMLElement).blur();
    }

    createSeek(color: string) {
        this.closeSeekDialog();
        if (!this.validGameData) return;

        let e;
        e = document.getElementById('variant') as HTMLSelectElement;
        const variant = VARIANTS[e.options[e.selectedIndex].value];
        const catalogued = isCataloguedVariant(variant.name);
        localStorage.seek_variant = variant.name;

        // TODO Standardize seek color
        let seekColor;
        if (variant.name.endsWith('shogi') && color !== 'r') seekColor = color === 'w' ? 'b' : 'w';
        else seekColor = color;

        e = document.getElementById('fen') as HTMLInputElement;
        let fen = e.value;
        // Prevent to create 'custom' games with standard startFen
        if (!['ataxx', 'paradigm'].includes(variant.name) && fen.trim() === variant.startFen) fen = '';

        e = document.getElementById('min') as HTMLInputElement;
        const minutes = this.minutesValues[Number(e.value)];
        localStorage.seek_min = e.value;

        e = document.getElementById('inc') as HTMLInputElement;
        const increment = this.incrementValues[Number(e.value)];
        localStorage.seek_inc = e.value;

        e = document.getElementById('byo') as HTMLInputElement;
        const byoyomi = variant.rules.defaultTimeControl === 'byoyomi';
        const byoyomiPeriod = byoyomi && increment > 0 ? Number(e.value) : 0;
        localStorage.seek_byo = e.value;

        let day = 0;
        if (this.tcMode === 'corr') {
            e = document.getElementById('day') as HTMLInputElement;
            day = this.daysValues[Number(e.value)];
            localStorage.seek_day = e.value;
            const corrTab = document.getElementById('tab-2') as HTMLInputElement;
            changeTabs('lobby_tab', corrTab);
            // TODO: use meaningful names!!!
        }
        e = document.querySelector('input[name="mode"]:checked') as HTMLInputElement;
        let rated: boolean;
        if (
            this.createMode === 'playAI' ||
            this.anon ||
            this.title === 'BOT' ||
            !canRateStart(variant, fen) ||
            (minutes < 1 && increment === 0) ||
            (minutes === 0 && increment === 1) ||
            catalogued
        )
            rated = false;
        else rated = e.value === '1';
        localStorage.seek_rated = e.value;

        e = document.getElementById('rating-min') as HTMLInputElement;
        const rrMin = Number(e.value);
        localStorage.seek_rating_min = e.value;

        e = document.getElementById('rating-max') as HTMLInputElement;
        const rrMax = Number(e.value);
        localStorage.seek_rating_max = e.value;

        e = document.getElementById('chess960') as HTMLInputElement;
        const chess960 = fen.trim() === '' && (catalogued ? variant.randomStart : variant.chess960 && e.checked);
        localStorage.seek_chess960 = e.checked;

        // console.log("CREATE SEEK variant, color, fen, minutes, increment, hide, chess960", variant, color, fen, minutes, increment, chess960, rated, rrMin, rrMax);

        switch (this.createMode) {
            case 'playAI':
                e = document.querySelector('input[name="level"]:checked') as HTMLInputElement;
                const level = Number(e.value);
                localStorage.seek_level = e.value;
                // console.log(level, e.value, localStorage.getItem("seek_level"));
                e = document.getElementById('rmplay') as HTMLInputElement;
                if (!'alice, fogofwar'.includes(variant.name)) {
                    localStorage.seek_rmplay = e.checked;
                }
                const rm = e.checked;
                this.createAIChallengeMsg(
                    variant.name,
                    seekColor,
                    fen,
                    minutes,
                    increment,
                    byoyomiPeriod,
                    level,
                    rm,
                    chess960,
                    rated,
                );
                break;
            case 'playBOT':
                this.createBOTChallengeMsg(
                    variant.name,
                    seekColor,
                    fen,
                    minutes,
                    increment,
                    byoyomiPeriod,
                    chess960,
                    rated,
                );
                break;
            case 'playFriend':
                this.createInviteFriendMsg(
                    variant.name,
                    seekColor,
                    fen,
                    minutes,
                    increment,
                    byoyomiPeriod,
                    day,
                    chess960,
                    rated,
                );
                break;
            case 'createHost':
                this.createHostMsg(variant.name, seekColor, fen, minutes, increment, byoyomiPeriod, chess960, rated);
                break;
            default:
                if (
                    this.isNewSeek(
                        variant.name,
                        seekColor,
                        fen,
                        minutes,
                        increment,
                        byoyomiPeriod,
                        day,
                        chess960,
                        rated,
                    )
                )
                    this.createSeekMsg(
                        variant.name,
                        seekColor,
                        fen,
                        minutes,
                        increment,
                        byoyomiPeriod,
                        day,
                        chess960,
                        rated,
                        rrMin,
                        rrMax,
                    );
        }
        // prevent to create challenges continuously
        this.profileid = '';
        window.history.replaceState({}, this.title, '/');

        // We need to ask the user for permission
        notify(null, undefined);
    }

    setTcMode(tcMode: TcMode) {
        if (tcMode !== this.tcMode) {
            this.tcMode = tcMode;
            document.getElementById('real')!.style.display = this.tcMode === 'real' ? 'block' : 'none';
            document.getElementById('corr')!.style.display = this.tcMode === 'corr' ? 'block' : 'none';
        }
    }

    renderDialogHeader(header: string) {
        this.dialogHeaderEl = patch(this.dialogHeaderEl, h('div#header-block', [h('h2', header)]));
    }

    private disabledVariants(): string[] {
        return disabledVariantsForCreateMode(this.createMode, this.profileid, this.anon, this.botSupportedVariants);
    }

    renderSeekButtons() {
        return [
            h('button.lobby-button', { on: { click: () => this.createGame() } }, createModeStr('createGame')),
            h('button.lobby-button', { on: { click: () => this.playFriend() } }, createModeStr('playFriend')),
            h('button.lobby-button', { on: { click: () => this.playAI() } }, createModeStr('playAI')),
            h(
                'button.lobby-button',
                {
                    on: { click: () => this.createHost() },
                    style: { display: this.tournamentDirector ? 'block' : 'none' },
                },
                createModeStr('createHost'),
            ),
        ];
    }

    renderSeekDialog() {
        let vVariant = localStorage.seek_variant || 'chess';
        if (!VARIANTS[vVariant]) vVariant = 'chess';
        const disabledVariants = this.disabledVariants();
        const twoBoards = VARIANTS[vVariant].twoBoards;
        const catalogued = isCataloguedVariant(vVariant);
        // 5+3 default TC needs vMin 9 because of the partial numbers at the beginning of minutesValues
        const vMin = localStorage.seek_min ?? '9';
        const vInc = localStorage.seek_inc ?? '3';
        const vByoIdx = (localStorage.seek_byo ?? 1) - 1;
        const vDay = localStorage.seek_day ?? '1';
        const vRated =
            twoBoards || catalogued || !VARIANTS[vVariant].ratingEnabled ? '0' : (localStorage.seek_rated ?? '0');
        const vRatingMin = localStorage.seek_rating_min ?? -1000;
        const vRatingMax = localStorage.seek_rating_max ?? 1000;
        const vLevel = Number(localStorage.seek_level ?? '1');
        const vChess960 = localStorage.seek_chess960 ?? 'false';
        const vRMplay = localStorage.seek_rmplay ?? 'false';
        return h('dialog#id01.modal', [
            h('form.modal-content', [
                h('span#closecontainer', [
                    h('button.close', {
                        on: { click: this.closeSeekDialog },
                        attrs: { type: 'button', 'data-icon': 'j', 'aria-label': _('Cancel') },
                        props: { title: _('Cancel') },
                    }),
                ]),
                h('div.container', [
                    h('div', [
                        h('div#header-block'),
                        h('div', [
                            h('label', { attrs: { for: 'variant' } }, _('Variant')),
                            selectVariant(
                                'variant',
                                disabledVariants.includes(vVariant) ? null : vVariant,
                                () => this.setVariant(),
                                () => this.setVariant(),
                                disabledVariants,
                                model.gameCategory,
                            ),
                        ]),
                        h('input#fen', {
                            props: {
                                name: 'fen',
                                placeholder:
                                    _('Paste the FEN text here') + (this.anon ? _(' (must be signed in)') : ''),
                                autocomplete: 'off',
                            },
                            on: { input: () => this.setFen() },
                        }),
                        h('div#alternate-start-block'),
                        h('div#chess960-block', [
                            h('label', { attrs: { for: 'chess960' } }, 'Chess960'),
                            h('input#chess960', {
                                props: {
                                    name: 'chess960',
                                    type: 'checkbox',
                                },
                                attrs: {
                                    checked: vChess960 === 'true',
                                },
                            }),
                        ]),
                        h('div.tc-block', [
                            h('div', [
                                h('label', { attrs: { for: 'tc' } }, _('Time control')),
                                h(
                                    'select#tc',
                                    {
                                        props: { name: 'tc' },
                                        on: {
                                            change: (e: Event) =>
                                                this.setTcMode((e.target as HTMLSelectElement).value as TcMode),
                                        },
                                    },
                                    [
                                        h('option', { attrs: { value: 'real' } }, _('Real time')),
                                        h(
                                            'option',
                                            { attrs: { value: 'corr', disabled: this.anon || twoBoards } },
                                            _('Correspondence'),
                                        ),
                                    ],
                                ),
                            ]),
                            h('div#tc_settings', [
                                h('div#real', [
                                    h('label', { attrs: { for: 'min' } }, _('Minutes per side:')),
                                    h('span#minutes'),
                                    h('input#min.slider', {
                                        props: {
                                            name: 'min',
                                            type: 'range',
                                            min: 0,
                                            max: this.minutesValues.length - 1,
                                            value: vMin,
                                        },
                                        on: {
                                            input: e => this.setMinutes(parseInt((e.target as HTMLInputElement).value)),
                                        },
                                        hook: {
                                            insert: vnode =>
                                                this.setMinutes(parseInt((vnode.elm as HTMLInputElement).value)),
                                        },
                                    }),
                                    h('label#incrementlabel', { attrs: { for: 'inc' } }, ''),
                                    h('span#increment'),
                                    h('input#inc.slider', {
                                        props: {
                                            name: 'inc',
                                            type: 'range',
                                            min: 0,
                                            max: this.incrementValues.length - 1,
                                            value: twoBoards ? 0 : vInc,
                                        },
                                        attrs: { disabled: twoBoards },
                                        on: {
                                            input: e =>
                                                this.setIncrement(
                                                    this.incrementValues[
                                                        parseInt((e.target as HTMLInputElement).value)
                                                    ],
                                                ),
                                        },
                                        hook: {
                                            insert: vnode =>
                                                this.setIncrement(
                                                    this.incrementValues[
                                                        parseInt((vnode.elm as HTMLInputElement).value)
                                                    ],
                                                ),
                                        },
                                    }),
                                    h('div#byoyomi-period', [
                                        h('label#byoyomiLabel', { attrs: { for: 'byo' } }, _('Periods')),
                                        h(
                                            'select#byo',
                                            {
                                                props: { name: 'byo' },
                                            },
                                            [1, 2, 3].map((n, idx) =>
                                                h(
                                                    'option',
                                                    { props: { value: n }, attrs: { selected: idx === vByoIdx } },
                                                    n,
                                                ),
                                            ),
                                        ),
                                    ]),
                                ]),
                                h('div#corr', [
                                    h('label', { attrs: { for: 'day' } }, _('Days per turn:')),
                                    h('span#days'),
                                    h('input#day.slider', {
                                        props: {
                                            name: 'day',
                                            type: 'range',
                                            min: 0,
                                            max: this.daysValues.length - 1,
                                            value: vDay,
                                        },
                                        on: {
                                            input: e => this.setDays(parseInt((e.target as HTMLInputElement).value)),
                                        },
                                        hook: {
                                            insert: vnode =>
                                                this.setDays(parseInt((vnode.elm as HTMLInputElement).value)),
                                        },
                                    }),
                                ]),
                            ]),
                        ]),
                        h('form#game-mode', [
                            h('div.radio-group', [
                                h('input#casual', {
                                    props: { type: 'radio', name: 'mode', value: '0' },
                                    attrs: { checked: vRated === '0' },
                                    on: { input: e => this.setCasual((e.target as HTMLInputElement).value) },
                                    hook: { insert: vnode => this.setCasual((vnode.elm as HTMLInputElement).value) },
                                }),
                                h('label', { attrs: { for: 'casual' } }, _('Casual')),
                                h('input#rated', {
                                    props: { type: 'radio', name: 'mode', value: '1' },
                                    attrs: {
                                        checked: vRated === '1',
                                        disabled: this.anon || twoBoards || catalogued,
                                    } /*dont support rated bughouse/catalogued atm*/,
                                    on: { input: e => this.setRated((e.target as HTMLInputElement).value) },
                                    hook: { insert: vnode => this.setRated((vnode.elm as HTMLInputElement).value) },
                                }),
                                h('label', { attrs: { for: 'rated' } }, _('Rated')),
                            ]),
                        ]),
                        h('div#rating-range-setting', [
                            _('Rating range'),
                            h('div.rating-range', [
                                h('input#rating-min.slider', {
                                    props: {
                                        name: 'rating-min',
                                        type: 'range',
                                        min: -1000,
                                        max: 0,
                                        step: 50,
                                        value: vRatingMin,
                                    },
                                    on: {
                                        input: e => this.setRatingMin(parseInt((e.target as HTMLInputElement).value)),
                                    },
                                    hook: {
                                        insert: vnode =>
                                            this.setRatingMin(parseInt((vnode.elm as HTMLInputElement).value)),
                                    },
                                }),
                                h('div.rating-min', '-1000'),
                                h('span', '/'),
                                h('div.rating-max', '+1000'),
                                h('input#rating-max.slider', {
                                    props: {
                                        name: 'rating-max',
                                        type: 'range',
                                        min: 0,
                                        max: 1000,
                                        step: 50,
                                        value: vRatingMax,
                                    },
                                    on: {
                                        input: e => this.setRatingMax(parseInt((e.target as HTMLInputElement).value)),
                                    },
                                    hook: {
                                        insert: vnode =>
                                            this.setRatingMax(parseInt((vnode.elm as HTMLInputElement).value)),
                                    },
                                }),
                            ]),
                        ]),
                        // if play with the machine
                        h('div#rmplay-block', [
                            h('label', { attrs: { for: 'rmplay' } }, 'Random-Mover'),
                            h('input#rmplay', {
                                props: {
                                    name: 'rmplay',
                                    type: 'checkbox',
                                    title: _('Practice with Random-Mover'),
                                },
                                attrs: {
                                    checked: vRMplay === 'true',
                                },
                                on: { click: () => this.setRM() },
                            }),
                        ]),
                        // A.I.Level (1-8 buttons)
                        h('form#ailevel', [
                            h('h4', _('A.I. Level')),
                            h(
                                'div.radio-group',
                                [0, 1, 2, 3, 4, 5, 6, 7, 8]
                                    .map(level => [
                                        h('input#ai' + level, {
                                            props: { type: 'radio', name: 'level', value: level },
                                            attrs: { checked: vLevel === level },
                                        }),
                                        h('label.level-ai.ai' + level, { attrs: { for: 'ai' + level } }, level),
                                    ])
                                    .reduce((arr, v) => (arr.push(...v), arr), []), // flatmap
                            ),
                        ]),
                        h('div#color-button-group', [
                            h('button.icon.icon-black', {
                                props: { type: 'button', title: _('Black') },
                                on: { click: () => this.createSeek('b') },
                            }),
                            h('button.icon.icon-adjust', {
                                props: { type: 'button', title: _('Random') },
                                on: { click: () => this.createSeek('r') },
                            }),
                            h('button.icon.icon-white', {
                                props: { type: 'button', title: _('White') },
                                on: { click: () => this.createSeek('w') },
                            }),
                        ]),
                        h('div#create-button', [
                            h(
                                'button',
                                { props: { type: 'button' }, on: { click: () => this.createSeek('w') } },
                                _('Create'),
                            ),
                        ]),
                    ]),
                ]),
            ]),
        ]);
    }

    autoPairingSelectAll() {
        document.querySelectorAll('input[name^="va_"]').forEach((inp: HTMLInputElement) => {
            inp.checked = true;
        });
        document.querySelectorAll('input[name^="tc_"]').forEach((inp: HTMLInputElement) => {
            inp.checked = true;
        });
    }

    autoPairingReset() {
        document.querySelectorAll('input[name^="va_"]').forEach((inp: HTMLInputElement) => {
            inp.checked = false;
        });
        document.querySelectorAll('input[name^="tc_"]').forEach((inp: HTMLInputElement) => {
            inp.checked = false;
        });
    }

    autoPairingCancel() {
        this.doSend({ type: 'cancel_auto_pairing' });
    }

    autoPairingSubmit() {
        const variants: [string, boolean][] = [];
        document.querySelectorAll('input[name^="va_"]').forEach((inp: HTMLInputElement) => {
            localStorage[inp.name] = inp.checked;
            if (inp.checked) {
                const chess960 = inp.name.endsWith('960');
                const name = chess960 ? inp.name.slice(3, -3) : inp.name.slice(3);
                variants.push([name, chess960]);
            }
        });

        const tcs: [number, number, number][] = [];
        document.querySelectorAll('input[name^="tc_"]').forEach((inp: HTMLInputElement, index: number) => {
            localStorage[inp.name] = inp.checked;
            if (inp.checked) tcs.push(autoPairingTCs[index]);
        });

        const minEle = document.getElementById('auto-rating-min') as HTMLInputElement;
        const rrMin = Number(minEle.value);
        localStorage.auto_rating_min = minEle.value;

        const maxEle = document.getElementById('auto-rating-max') as HTMLInputElement;
        const rrMax = Number(maxEle.value);
        localStorage.auto_rating_max = maxEle.value;

        this.doSend({ type: 'create_auto_pairing', variants: variants, tcs: tcs, rrmin: rrMin, rrmax: rrMax });
    }

    preSelectVariant(variantName: string, chess960: boolean = false) {
        const select = document.getElementById('variant') as HTMLSelectElement;
        if (!select) return;
        const options = Array.from(select.options);
        const enabledOptions = options.filter(option => !option.disabled);
        if (!enabledOptions.length) {
            select.selectedIndex = -1;
            return;
        }

        if (variantName !== '') {
            const option = options.find(candidate => candidate.value === variantName && !candidate.disabled);
            if (option === undefined) {
                delete localStorage.seek_variant;
                delete localStorage.seek_chess960;
            }
            select.selectedIndex = option === undefined ? options.indexOf(enabledOptions[0]) : options.indexOf(option);
        } else if (select.selectedIndex < 0 || select.options[select.selectedIndex].disabled) {
            select.selectedIndex = options.indexOf(enabledOptions[0]);
        }

        const check = document.getElementById('chess960') as HTMLInputElement;
        if (check) check.checked = chess960;
        this.setVariant();
    }

    renderVariantsDropDown(variantName: string = '', disabled: string[]) {
        // variantName and chess960 are set when this was called from the variant catalog (layer3.ts)
        let vVariant = variantName || localStorage.seek_variant || 'chess';
        if (!VARIANTS[vVariant] || disabled.includes(vVariant)) vVariant = '';
        const vChess960 = localStorage.seek_chess960 === 'true' || false;
        const e = document.getElementById('variant');
        e!.replaceChildren();
        patch(
            e!,
            selectVariant(
                'variant',
                vVariant || null,
                () => this.setVariant(),
                () => this.setVariant(),
                disabled,
                model.gameCategory,
            ),
        );
        this.preSelectVariant(vVariant, vChess960);
    }

    createGame(variantName: string = '') {
        const selectedVariant = variantName || localStorage.seek_variant || 'chess';
        this.createMode = 'createGame';
        this.renderVariantsDropDown(variantName, this.disabledVariants());
        this.renderDialogHeader(createModeStr(this.createMode));
        document.getElementById('game-mode')!.style.display = this.anon ? 'none' : 'inline-flex';
        const selectedElement = document.getElementById('variant') as HTMLSelectElement;
        const selectedVariantAfterRender = selectedElement?.value || selectedVariant;
        const selectedTwoBoards = !!VARIANTS[selectedVariantAfterRender]?.twoBoards;
        this.updateRatingRangeVisibility(selectedVariantAfterRender);
        document.getElementById('ailevel')!.style.display = 'none';
        document.getElementById('rmplay-block')!.style.display = 'none';
        (document.getElementById('id01') as HTMLDialogElement).showModal();
        document.getElementById('color-button-group')!.style.display = 'block';
        document.getElementById('create-button')!.style.display = 'none';
        disableCorr(this.anon || selectedTwoBoards);
    }

    playFriend(variantName: string = '') {
        this.createMode = 'playFriend';
        this.renderVariantsDropDown(variantName, this.disabledVariants());
        this.renderDialogHeader(createModeStr(this.createMode));
        document.getElementById('game-mode')!.style.display = this.anon ? 'none' : 'inline-flex';
        this.updateRatingRangeVisibility();
        document.getElementById('ailevel')!.style.display = 'none';
        document.getElementById('rmplay-block')!.style.display = 'none';
        (document.getElementById('id01') as HTMLDialogElement).showModal();
        document.getElementById('color-button-group')!.style.display = 'block';
        document.getElementById('create-button')!.style.display = 'none';
        disableCorr(false);
    }

    playAI(variantName: string = '') {
        this.createMode = 'playAI';
        this.renderVariantsDropDown(variantName, this.disabledVariants());
        this.renderDialogHeader(createModeStr(this.createMode));
        document.getElementById('game-mode')!.style.display = 'none';
        this.updateRatingRangeVisibility();
        const e = document.getElementById('rmplay') as HTMLInputElement;
        document.getElementById('ailevel')!.style.display = e.checked ? 'none' : 'inline-block';
        document.getElementById('rmplay-block')!.style.display = 'block';
        (document.getElementById('id01') as HTMLDialogElement).showModal();
        document.getElementById('color-button-group')!.style.display = 'block';
        document.getElementById('create-button')!.style.display = 'none';
        disableCorr(true);
    }

    createHost(variantName: string = '') {
        this.createMode = 'createHost';
        this.renderVariantsDropDown(variantName, this.disabledVariants());
        this.renderDialogHeader(createModeStr(this.createMode));
        document.getElementById('game-mode')!.style.display = this.anon ? 'none' : 'inline-flex';
        this.updateRatingRangeVisibility();
        document.getElementById('ailevel')!.style.display = 'none';
        document.getElementById('rmplay-block')!.style.display = 'none';
        (document.getElementById('id01') as HTMLDialogElement).showModal();
        document.getElementById('color-button-group')!.style.display = 'none';
        document.getElementById('create-button')!.style.display = 'block';
        disableCorr(true);
    }

    private updateRatingRangeVisibility(variantName?: string) {
        const selectedVariant = variantName ?? (document.getElementById('variant') as HTMLSelectElement | null)?.value;
        const visible = shouldShowRatingRange(
            this.createMode,
            this.profileid !== '',
            isCataloguedVariant(selectedVariant),
        );
        document.getElementById('rating-range-setting')!.style.display = visible ? 'block' : 'none';
    }

    private setVariant() {
        let e;
        e = document.getElementById('variant') as HTMLSelectElement;
        if (!e || e.selectedIndex < 0 || e.options.length === 0) return;
        const variant = VARIANTS[e.options[e.selectedIndex].value];
        if (!variant) return;
        const byoyomi = variant.rules.defaultTimeControl === 'byoyomi';
        const catalogued = isCataloguedVariant(variant.name);
        this.updateRatingRangeVisibility(variant.name);
        if (variant.twoBoards) {
            const select = document.getElementById('tc') as HTMLSelectElement;
            select.selectedIndex = 0;
            this.tcMode = 'real';
        }
        const inc = document.getElementById('inc') as HTMLInputElement;
        if (inc) {
            inc.disabled = variant.twoBoards;
            if (variant.twoBoards) {
                inc.value = '0';
                this.setIncrement(0);
            }
        }
        const rated = document.getElementById('rated') as HTMLInputElement;
        const casual = document.getElementById('casual') as HTMLInputElement;
        if (rated && casual) {
            rated.disabled = this.anon || variant.twoBoards || catalogued || !variant.ratingEnabled;
            if (rated.disabled) {
                casual.checked = true;
                rated.checked = false;
            }
        }
        // TODO use toggle class instead of setting style directly
        document.getElementById('chess960-block')!.style.display = variant.chess960 ? 'block' : 'none';
        document.getElementById('byoyomi-period')!.style.display = byoyomi ? 'block' : 'none';
        document.getElementById('corr')!.style.display = this.tcMode === 'corr' ? 'block' : 'none';
        e = document.getElementById('fen') as HTMLInputElement;
        e.value = '';
        this.updateRatedAvailability(variant, e.value);
        e = document.getElementById('incrementlabel') as HTMLSelectElement;
        patch(
            e,
            h(
                'label#incrementlabel',
                { attrs: { for: 'inc' } },
                byoyomi ? _('Byoyomi in seconds:') : _('Increment in seconds:'),
            ),
        );
        e = document.getElementById('alternate-start-block') as HTMLElement;
        e.innerHTML = '';
        if (variant.alternateStart) {
            patch(
                e,
                h('div#alternate-start-block', [
                    h('label', { attrs: { for: 'alternate-start' } }, _('Alternate Start')),
                    h(
                        'select#alternate-start',
                        {
                            props: { name: 'alternate-start' },
                            on: { input: () => this.setAlternateStart(variant) },
                            hook: { insert: () => this.setAlternateStart(variant) },
                        },
                        Object.keys(variant.alternateStart).map(alt => h('option', { props: { value: alt } }, _(alt))),
                    ),
                ]),
            );
        }
        this.applyBotVariantCapabilities(variant);
        // Select Random-Mover but disable FSF play for "unsupported by FSF" variants
        if (this.createMode === 'playAI') {
            e = document.getElementById('rmplay') as HTMLInputElement;
            if (unsupportedAiVariants.includes(variant.name) || variant.aiDisabled) {
                e.checked = true;
                e.disabled = true;
                document.getElementById('ailevel')!.style.display = 'none';
            } else {
                e.disabled = false;
                const vRMplay = localStorage.seek_rmplay ?? 'false';
                e.checked = vRMplay === 'true';
                document.getElementById('ailevel')!.style.display = e.checked ? 'none' : 'inline-block';
            }
        }
        switchEnablingLobbyControls(this.createMode, variant, this.anon);
        this.setStartButtons();
    }

    private applyBotVariantCapabilities(variant: Variant) {
        if (this.createMode !== 'playBOT' || this.botSupportedVariants === null) return;

        const supportsNormal = this.botSupportedVariants.has(variant.name);
        const supports960 = variant.chess960 && this.botSupportedVariants.has(`${variant.name}960`);
        const chess960 = document.getElementById('chess960') as HTMLInputElement;
        if (!supports960) chess960.checked = false;
        else if (!supportsNormal) chess960.checked = true;

        const alternateStart = document.getElementById('alternate-start') as HTMLSelectElement | null;
        const alternateStartSelected = alternateStart !== null && alternateStart.value !== '';
        chess960.disabled = !supportsNormal || !supports960 || alternateStartSelected;

        const fen = document.getElementById('fen') as HTMLInputElement;
        fen.disabled = !supportsNormal;
        if (!supportsNormal) fen.value = '';
        if (alternateStart !== null) alternateStart.disabled = !supportsNormal;
    }

    private setAlternateStart(variant: Variant) {
        let e: HTMLSelectElement;
        e = document.getElementById('alternate-start') as HTMLSelectElement;
        const alt = e.options[e.selectedIndex].value;
        e = document.getElementById('fen') as HTMLSelectElement;
        e.value = variant.alternateStart![alt].fen;
        (document.getElementById('chess960') as HTMLInputElement).disabled = alt !== '';
        this.applyBotVariantCapabilities(variant);
        this.setFen();
    }
    private setMinutes(val: number) {
        const minutes = val < this.minutesStrings.length ? this.minutesStrings[val] : String(this.minutesValues[val]);
        document.getElementById('minutes')!.innerHTML = minutes;
        this.setStartButtons();
    }
    private setIncrement(increment: number) {
        document.getElementById('increment')!.innerHTML = '' + increment;
        this.setStartButtons();
    }
    private setDays(val: number) {
        const days = this.daysValues[val];
        document.getElementById('days')!.innerHTML = String(days);
        this.setStartButtons();
    }
    private setRatingMin(val: number) {
        document.querySelector('div.rating-min')!.innerHTML = '-' + String(Math.abs(val));
    }
    private setRatingMax(val: number) {
        document.querySelector('div.rating-max')!.innerHTML = '+' + String(val);
    }
    private setAutoRatingMin(val: number) {
        document.querySelector('div.auto-rating-min')!.innerHTML = '-' + String(Math.abs(val));
    }
    private setAutoRatingMax(val: number) {
        document.querySelector('div.auto-rating-max')!.innerHTML = '+' + String(val);
    }
    private setFen() {
        const e = document.getElementById('fen') as HTMLInputElement;
        e.setCustomValidity(this.validateFen() ? '' : _('Invalid FEN'));
        const variantSelect = document.getElementById('variant') as HTMLSelectElement;
        const variant = VARIANTS[variantSelect.options[variantSelect.selectedIndex].value];
        this.updateRatedAvailability(variant, e.value);
        this.setStartButtons();
    }
    private updateRatedAvailability(variant: Variant, fen: string) {
        const rated = document.getElementById('rated') as HTMLInputElement;
        const casual = document.getElementById('casual') as HTMLInputElement;
        if (!rated || !casual) return;
        rated.disabled =
            this.anon || variant.twoBoards || isCataloguedVariant(variant.name) || !canRateStart(variant, fen);
        if (rated.disabled && rated.checked) {
            rated.checked = false;
            casual.checked = true;
        }
    }
    private setCasual(casual: string) {
        console.log('setCasual', casual);
        this.setStartButtons();
    }
    private setRated(rated: string) {
        console.log('setRated', rated);
        this.setStartButtons();
    }
    private setRM() {
        const e = document.getElementById('rmplay') as HTMLInputElement;
        if (e.disabled) e.checked = true;
        document.getElementById('ailevel')!.style.display = e.checked ? 'none' : 'block';
    }
    private setStartButtons() {
        this.validGameData = this.validateTimeControl() && this.validateFen();
        const e = document.getElementById('color-button-group') as HTMLElement;
        e.classList.toggle('disabled', !this.validGameData);
    }
    private validateTimeControl() {
        const min = Number((document.getElementById('min') as HTMLInputElement).value);
        const inc = Number((document.getElementById('inc') as HTMLInputElement).value);
        const minutes = this.minutesValues[min];

        const e = document.querySelector('input[name="mode"]:checked') as HTMLInputElement;
        const rated = e.value === '1';

        const atLeast = this.createMode === 'playAI' ? (min > 0 && inc > 0) || (min >= 1 && inc === 0) : min + inc > 0;
        const tooFast = (minutes < 1 && inc === 0) || (minutes === 0 && inc === 1);

        return atLeast && !(tooFast && rated);
    }
    private validateFen() {
        const e = document.getElementById('variant') as HTMLSelectElement;
        const variant = e.options[e.selectedIndex].value;
        const fen = (document.getElementById('fen') as HTMLInputElement).value;
        return fen === '' || validFen(VARIANTS[variant], fen);
    }

    renderSeeks(seeks: Seek[]) {
        seeks.sort((a, b) => (a.bot && !b.bot ? 1 : -1));
        const rows = seeks.flatMap(seek => this.seekView(seek));
        return [seekHeader(), h('tbody', rows)];
    }

    private seekViewRegular(seek: Seek): VNode[] {
        const variant = VARIANTS[seek.variant];
        const chess960 = seek.chess960;
        const catalogued = isCataloguedVariant(seek.variant);
        const displayName = variant.displayName(chess960);
        const icon = variant.icon(chess960);
        const row = h(
            'tr',
            {
                class: { 'catalogued-seek-main': catalogued },
                on: { click: () => this.onClickSeek(seek) },
            },
            [
                h('td', [this.seekAction(seek, displayName)]),
                h('td', [this.challengeIcon(seek), this.seekTitle(seek), this.user(seek)]),
                h('td', seek.rating),
                h('td', timeControlStr(seek.base, seek.inc, seek.byoyomi, seek.day)),
                h('td.icon', { attrs: { 'data-icon': icon } }, [h('variant-name', ' ' + displayName)]),
                h('td', { class: { tooltip: seek.fen !== '' } }, [this.tooltip(seek, variant), this.mode(seek)]),
            ],
        );

        if (!catalogued) return [row];

        return [
            row,
            h('tr.catalogued-seek-name', { on: { click: () => this.onClickSeek(seek) } }, [
                h('td', { attrs: { colspan: '6' } }, [
                    h('span.mobile-catalogued-variant', { attrs: { title: displayName } }, displayName),
                ]),
            ]),
        ];
    }

    private seekViewUnknown(seek: Seek) {
        return h('tr.disabled', { attrs: { title: _('This user-defined variant is not available to you.') } }, [
            h('td', [this.colorIcon(seek.color)]),
            h('td', [this.challengeIcon(seek), this.seekTitle(seek), this.user(seek)]),
            h('td', seek.rating),
            h('td', timeControlStr(seek.base, seek.inc, seek.byoyomi, seek.day)),
            h('td.icon', { attrs: { 'data-icon': CATALOGUED_VARIANT_ICON } }, [h('variant-name', ` ${seek.variant}`)]),
            h('td', this.mode(seek)),
        ]);
    }

    private seekView(seek: Seek): VNode[] {
        if (this.hide(seek)) return [];
        const variant = VARIANTS[seek.variant];
        if (!variant) return [this.seekViewUnknown(seek)];
        return variant.twoBoards ? [seekViewBughouse(this, seek)] : this.seekViewRegular(seek);
    }

    private onClickSeek(seek: Seek) {
        if (seek['user'] === this.username) {
            this.doSend({ type: 'delete_seek', seekID: seek['seekID'], player: this.username });
        } else {
            if (this.anon && seek.day !== 0) {
                void alertDialog({ text: _('You need an account to do that.') });
                return;
            }
            this.doSend({ type: 'accept_seek', seekID: seek['seekID'], player: this.username });
        }
    }

    // The row's keyboard control. It has no handler: Enter or Space clicks it, and the click reaches
    // the row's own, so mouse and keyboard take one path.
    private seekAction(seek: Seek, displayName: string): VNode {
        const time = timeControlStr(seek.base, seek.inc, seek.byoyomi, seek.day);
        const label =
            seek.user === this.username
                ? `${_('Cancel')}: ${time}, ${displayName}`
                : `${_('Join')}: ${displayUsername(seek.user)}, ${time}, ${displayName}`;
        return h('button.seek-action', { attrs: { type: 'button', 'aria-label': label } }, [
            this.colorIcon(seek.color),
        ]);
    }

    private colorIcon(color: string) {
        return h('i-side.icon', {
            class: {
                'icon-adjust': color === 'r',
                'icon-white': color === 'w',
                'icon-black': color === 'b',
            },
        });
    }

    public challengeIcon(seek: Seek) {
        const swords = seek['user'] === this.username ? 'vs-swords.icon' : 'vs-swords.opp.icon';
        return seek['target'] === '' ? null : h(swords, { attrs: { 'data-icon': '"' } });
    }
    public seekTitle(seek: Seek) {
        return seek['target'] === '' ? h('player-title', ' ' + seek['title'] + ' ') : null;
    }
    private seekUserLink(username: string): VNode | string {
        const display = displayUsername(username);
        if (isAnonUsername(username)) return display;
        return h(
            'span.user-link.ulpt',
            {
                attrs: { 'data-href': `/@/${encodeURIComponent(username)}` },
            },
            display,
        );
    }
    private user(seek: Seek) {
        if (seek['target'] === '' || seek['target'] === this.username) return this.seekUserLink(seek['user']);
        else return this.seekUserLink(seek['target']);
    }
    private hide(seek: Seek) {
        const variant = VARIANTS[seek.variant];
        return (
            ((this.anon || this.title === 'BOT') && seek['rated']) ||
            (this.anon && !!variant?.twoBoards) ||
            (seek['target'] !== '' && this.username !== seek['user'] && this.username !== seek['target'])
        );
    }
    public tooltip(seek: Seek, variant: Variant) {
        let tooltipImage;
        if (seek.fen) {
            tooltipImage = h('minigame.' + variant.boardFamily + '.' + variant.pieceFamily, [
                h('div.cg-wrap.' + variant.board.cg + '.minitooltip', {
                    hook: {
                        insert: vnode => {
                            boardSettings.updateScopedBoardStyle(variant, vnode.elm as Element);
                            boardSettings.updateScopedPieceStyle(variant, vnode.elm as Element);
                            Chessground(vnode.elm as HTMLElement, {
                                coordinates: false,
                                fen: seek.fen,
                                dimensions: variant.board.dimensions,
                                viewOnly: true,
                            });
                        },
                    },
                }),
            ]);
        } else {
            tooltipImage = '';
        }
        return h('span.tooltiptext', [tooltipImage]);
    }

    public mode(seek: Seek) {
        if (seek.rated) return _('Rated');
        else if (seek.fen) return _('Custom');
        else return _('Casual');
    }

    private streamView(stream: Stream) {
        const url = stream.site === 'twitch' ? 'https://www.twitch.tv/' : 'https://www.youtube.com/channel/';
        const tail = stream.site === 'youtube' ? '/live' : '';
        return h(
            'a.stream',
            { attrs: { href: url + stream.streamer + tail, rel: 'noopener nofollow', target: '_blank' } },
            [h('strong.text', { class: { icon: true, 'icon-mic': true } }, stream.username), stream.title],
        );
    }

    private spotlightView(spotlight: Spotlight) {
        if (spotlight.kind === 'simul') {
            const name = spotlight.name.toLowerCase().endsWith(' simul')
                ? spotlight.name
                : spotlight.name + ' simul';
            return h('a.tour-spotlight.little.simul-spotlight', { attrs: { href: '/simul/' + spotlight.sid } }, [
                h('i.icon.icon-fire'),
                h('span.content', [
                    h('span.name', name),
                    h('span.more', ngettext('%1 player', '%1 players', spotlight.nbPlayers) + ' • ' + _('Join')),
                ]),
            ]);
        }

        const variant = VARIANTS[spotlight.variant];
        const chess960 = spotlight.chess960;
        const dataIcon = variant.icon(chess960);
        const lang = languageSettings.value;
        const name = spotlight.names[lang] ?? spotlight.names['en'];

        return h('a.tour-spotlight', { attrs: { href: '/tournament/' + spotlight.tid } }, [
            h('i.icon', { attrs: { 'data-icon': dataIcon } }),
            h('span.content', [
                h('span.name', name),
                h('span.more', [
                    h('nb', ngettext('%1 player', '%1 players', spotlight.nbPlayers) + ' • '),
                    h('info-date', { attrs: { timestamp: spotlight.startsAt } }),
                ]),
            ]),
        ]);
    }

    private spotlightAllowed(spotlight: Spotlight): boolean {
        if (!this.allowedVariants) return true;
        if (spotlight.kind === 'simul') {
            return spotlight.variants.some(variantKey => this.allowedVariants!.has(splitVariantKey(variantKey).base));
        }
        return this.allowedVariants.has(spotlight.variant);
    }

    private userWithTitle(username: string, title: string): (VNode | string)[] {
        const userNodes: (VNode | string)[] = [];
        if (title) userNodes.push(h('player-title', `${title} `));
        userNodes.push(this.seekUserLink(username));
        return userNodes;
    }

    private leadersView(msg: MsgLeaderboard): VNode {
        const filtered = msg.items.filter((entry: LeaderboardEntry) =>
            this.isVariantAllowed(variantKey(entry.variant, entry.chess960)),
        );
        const rows = filtered
            .map((entry: LeaderboardEntry) => {
                const variant = VARIANTS[entry.variant];
                if (!variant) return null;
                const variantName = variant.displayName(entry.chess960);
                return h('tr', [
                    h('td', this.userWithTitle(entry.username, entry.title)),
                    h('td.icon', { attrs: { 'data-icon': variant.icon(entry.chess960), title: variantName } }),
                    h('td', String(entry.rating)),
                ]);
            })
            .filter((row): row is VNode => row !== null);

        return h('div#leaders.lobby-ranking', [
            h('a.lobby-ranking-top', { attrs: { href: '/players' } }, [
                h('strong', _('Leaderboard')),
                h('span.more', _('More') + ' »'),
            ]),
            h('div.lobby-ranking-content', [h('table', [h('tbody', rows)])]),
        ]);
    }

    private winnersView(msg: MsgTournamentWinners): VNode {
        const filtered = msg.items.filter((entry: TournamentWinnerEntry) =>
            this.isVariantAllowed(variantKey(entry.variant, entry.chess960)),
        );
        const rows = filtered
            .map((entry: TournamentWinnerEntry) => {
                const variant = VARIANTS[entry.variant];
                if (!variant) return null;
                const variantName = variant.displayName(entry.chess960);
                return h('tr', [
                    h('td', this.userWithTitle(entry.username, entry.title)),
                    h('td.icon', { attrs: { 'data-icon': variant.icon(entry.chess960), title: variantName } }),
                    h('td', [
                        h(
                            'a.tourname',
                            { attrs: { href: `/tournament/${entry.tid}`, title: entry.tournament } },
                            entry.tournament,
                        ),
                    ]),
                ]);
            })
            .filter((row): row is VNode => row !== null);

        return h('div#winners.lobby-ranking', [
            h('a.lobby-ranking-top', { attrs: { href: '/tournaments/winners' } }, [
                h('strong', _('Tournament winners')),
                h('span.more', _('More') + ' »'),
            ]),
            h('div.lobby-ranking-content', [h('table', [h('tbody', rows)])]),
        ]);
    }

    renderEmptyTvGame() {
        patch(document.getElementById('tv-game') as HTMLElement, h('a#tv-game.empty'));
    }

    renderTvGame() {
        if (this.tvGame === undefined) return;

        const game = this.tvGame;
        const variant = VARIANTS[game.variant];
        const elements = [
            h(
                `div#mainboard.${variant.boardFamily}.${variant.pieceFamily}.${variant.ui.boardMark}`,
                {
                    class: { 'with-pockets': !!variant.pocket },
                    style: { '--ranks': variant.pocket ? String(variant.board.dimensions.height) : 'undefined' },
                    on: { click: () => window.location.assign('/' + game.gameId) },
                },
                [
                    h(`div.cg-wrap.${variant.board.cg}.mini`, {
                        hook: {
                            insert: vnode => {
                                const boardWrap = vnode.elm as HTMLElement;
                                const boardHost = sizeMiniBoardHost(boardWrap);
                                boardSettings.updateScopedBoardStyle(variant, vnode.elm as Element);
                                boardSettings.updateScopedPieceStyle(variant, vnode.elm as Element);
                                const cg = Chessground(boardWrap, {
                                    fen: game.fen,
                                    lastMove: uci2LastMove(game.lastMove),
                                    dimensions: variant.board.dimensions,
                                    coordinates: false,
                                    viewOnly: true,
                                    addDimensionsCssVarsTo: boardHost ?? document.body,
                                    pocketRoles: variant.pocket?.roles,
                                });
                                this.tvGameChessground = cg;
                                this.tvGameId = game.gameId;
                            },
                        },
                    }),
                ],
            ),
            h('span.vstext', [
                h('div.player', [
                    h('tv-user', [
                        h('player-title', game.bt),
                        ' ' + displayUsername(game.b) + ' ',
                        h('rating', game.br),
                    ]),
                ]),
                h('div.player', [
                    h('tv-user', [
                        h('player-title', game.wt),
                        ' ' + displayUsername(game.w) + ' ',
                        h('rating', game.wr),
                    ]),
                ]),
            ]),
        ];

        patch(document.getElementById('tv-game') as HTMLElement, h('a#tv-game', elements));

        boardSettings.assetURL = this.assetURL;
    }

    renderAutoPairingActions(autoPairingIsOn: boolean) {
        const eRange = document.querySelector('div.auto-rating-range') as Element;
        const eTimeControls = document.querySelector('div.timecontrols') as Element;
        const eVariants = document.querySelector('div.variants') as Element;
        if (autoPairingIsOn) {
            if (this.autoPairingActions) {
                this.autoPairingActions = patch(
                    this.autoPairingActions,
                    h('div.auto-pairing-actions', [
                        h('span.standingby', _('Standing by for auto pairing...')),
                        h('button.cancel', { on: { click: () => this.autoPairingCancel() } }, [
                            h('div.icon.icon-ban', _('CANCEL')),
                        ]),
                    ]),
                );
            }
            eRange.classList.toggle('disabled', true);
            eTimeControls.classList.toggle('disabled', true);
            eVariants.classList.toggle('disabled', true);
        } else {
            if (this.autoPairingActions) {
                this.autoPairingActions = patch(
                    this.autoPairingActions,
                    h('div.auto-pairing-actions', [
                        h('button.selectall', { on: { click: () => this.autoPairingSelectAll() } }, [
                            h('div.icon.icon-check', _('SELECT ALL')),
                        ]),
                        h('button.reset', { on: { click: () => this.autoPairingReset() } }, [
                            h('div.icon.icon-trash-o', _('CLEAR ALL')),
                        ]),
                        h('button.submit', { on: { click: () => this.autoPairingSubmit() } }, [
                            h('div.icon.icon-check', _('SUBMIT')),
                        ]),
                    ]),
                );
            }
            eRange.classList.toggle('disabled', false);
            eTimeControls.classList.toggle('disabled', false);
            eVariants.classList.toggle('disabled', false);
        }
    }

    renderAutoPairingTable() {
        const variantList: VNode[] = [];
        enabledVariants.forEach(v => {
            if (!this.isVariantAllowed(v)) return;
            if (devVariants.includes(v) || isCataloguedVariant(v)) return;
            const variant = VARIANTS[v];
            let variantName = variant.name;
            let checked = localStorage[`va_${variantName}`] ?? 'false';
            if (!variant.twoBoards) {
                variantList.push(
                    h('label', [
                        h('input', {
                            props: { name: `va_${variantName}`, type: 'checkbox' },
                            attrs: { checked: checked === 'true' },
                        }),
                        variantName,
                    ]),
                );
                if (variant.chess960) {
                    variantName = variantName + '960';
                    checked = localStorage[`va_${variantName}`] ?? 'false';
                    variantList.push(
                        h('label', [
                            h('input', {
                                props: { name: `va_${variantName}`, type: 'checkbox' },
                                attrs: { checked: checked === 'true' },
                            }),
                            variantName,
                        ]),
                    );
                }
            }
        });
        patch(document.querySelector('div.variants') as Element, h('div.variants', variantList));

        const tcList: VNode[] = [];
        autoPairingTCs.forEach(v => {
            const tcName = timeControlStr(v[0], v[1], v[2]);
            const checked = localStorage[`tc_${tcName}`] ?? 'false';
            tcList.push(
                h('label', [
                    h('input', {
                        props: { name: `tc_${tcName}`, type: 'checkbox' },
                        attrs: { checked: checked === 'true' },
                    }),
                    tcName,
                ]),
            );
        });

        patch(document.querySelector('div.timecontrols') as Element, h('div.timecontrols', tcList));

        const aRatingMin = localStorage.auto_rating_min ?? -1000;
        const aRatingMax = localStorage.auto_rating_max ?? 1000;
        const aRatingRange = [
            _('Rating range'),
            h('div.rating-range', [
                h('input#auto-rating-min.slider', {
                    props: { name: 'rating-min', type: 'range', min: -1000, max: 0, step: 50, value: aRatingMin },
                    on: { input: e => this.setAutoRatingMin(parseInt((e.target as HTMLInputElement).value)) },
                    hook: { insert: vnode => this.setAutoRatingMin(parseInt((vnode.elm as HTMLInputElement).value)) },
                }),
                h('div.auto-rating-min', '-1000'),
                h('span', '/'),
                h('div.auto-rating-max', '+1000'),
                h('input#auto-rating-max.slider', {
                    props: { name: 'rating-max', type: 'range', min: 0, max: 1000, step: 50, value: aRatingMax },
                    on: { input: e => this.setAutoRatingMax(parseInt((e.target as HTMLInputElement).value)) },
                    hook: { insert: vnode => this.setAutoRatingMax(parseInt((vnode.elm as HTMLInputElement).value)) },
                }),
            ]),
        ];

        patch(document.querySelector('div.auto-rating-range') as Element, h('div.auto-rating-range', aRatingRange));
    }

    private isVariantAllowed(variant: string): boolean {
        return this.allowedVariants ? this.allowedVariants.has(variant) : true;
    }

    onMessage(evt: MessageEvent) {
        // console.log("<+++ lobby onMessage():", evt.data);
        if (evt.data === '/n') return;
        const msg = JSON.parse(evt.data);
        switch (msg.type) {
            case 'get_seeks':
                this.onMsgGetSeeks(msg);
                break;
            case 'new_game':
                this.onMsgNewGame(msg);
                break;
            case 'game_in_progress':
                this.onMsgGameInProgress(msg);
                break;
            case 'lobby_user_connected':
                this.onMsgUserConnected(msg);
                break;
            case 'reload_timeline':
                void this.reloadTimeline();
                break;
            case 'leaderboard':
                this.onMsgLeaderboard(msg);
                break;
            case 'tournament_winners':
                this.onMsgTournamentWinners(msg);
                break;
            case 'ping':
                this.onMsgPing(msg);
                break;
            case 'tv_game':
                this.onMsgTvGame(msg);
                break;
            case 'board':
                this.onMsgBoard(msg);
                break;
            case 'g_cnt':
                this.onMsgGameCounter(msg);
                break;
            case 'u_cnt':
                this.onMsgUserCounter(msg);
                break;
            case 'ap_cnt':
                this.onMsgAutoPairingCounter(msg);
                break;
            case 'streams':
                this.onMsgStreams(msg);
                break;
            case 'spotlights':
                this.onMsgSpotlights(msg);
                break;
            case 'invite_created':
                this.onMsgInviteCreated(msg);
                break;
            case 'direct_challenge_created':
                this.onMsgDirectChallengeCreated(msg);
                break;
            case 'bot_challenge_created':
                this.onMsgBOTChallengeCreated(msg);
                break;
            case 'host_created':
                this.onMsgHostCreated(msg);
                break;
            case 'auto_pairing_on':
                this.onMsgAutoPairingOn();
                break;
            case 'auto_pairing_off':
                this.onMsgAutoPairingOff();
                break;
            case 'shutdown':
                this.onMsgShutdown(msg);
                break;
            case 'error':
                this.onMsgError(msg);
                break;
            case 'logout':
                this.doSend({ type: 'logout' });
                break;
        }
    }

    private onMsgBOTChallengeCreated(msg: MsgInviteCreated) {
        window.location.assign('/bot-challenge/' + msg.gameId);
    }

    private onMsgInviteCreated(msg: MsgInviteCreated) {
        window.location.assign('/invite/' + msg.gameId);
    }

    private onMsgDirectChallengeCreated(msg: MsgDirectChallengeCreated) {
        window.location.assign('/challenge/' + msg.seekId);
    }

    private onMsgHostCreated(msg: MsgHostCreated) {
        window.location.assign('/invite/' + msg.gameId);
    }

    private onMsgAutoPairingOn() {
        if (!this.anon) this.renderAutoPairingActions(true);
    }

    private onMsgAutoPairingOff() {
        if (!this.anon) this.renderAutoPairingActions(false);
    }

    private onMsgGetSeeks(msg: MsgGetSeeks) {
        this.seeks = msg.seeks;
        // console.log("!!!! got get_seeks msg:", msg);
        const visibleSeeks = msg.seeks.filter(seek => this.isVariantAllowed(seek.variant));

        const oldSeeks = document.querySelector('.seek-container table.seeks') as Element;
        oldSeeks.innerHTML = '';
        patch(oldSeeks, h('table.seeks', this.renderSeeks(visibleSeeks.filter(seek => seek.day === 0))));

        const oldCorrs = document.querySelector('.corr-container table.seeks') as Element;
        oldCorrs.innerHTML = '';
        patch(oldCorrs, h('table.seeks', this.renderSeeks(visibleSeeks.filter(seek => seek.day !== 0))));
    }

    private onMsgNewGame(msg: MsgNewGame) {
        window.location.assign('/' + msg.gameId);
    }

    private async onMsgGameInProgress(msg: MsgGameInProgress) {
        const response = await confirmDialog({
            text: _('You have an unfinished game!\nPress OK to continue.'),
            confirmText: _('OK'),
            cancelText: _('Cancel'),
        });
        if (response) window.location.assign('/' + msg.gameId);
    }

    private onMsgUserConnected(msg: MsgUserConnected) {
        this.username = msg.username;
    }

    private async reloadTimeline() {
        if (this.timeline === null || this.anon) return;
        try {
            const entries = await fetchTimeline();
            this.timeline.update(entries);
        } catch {
            // Keep the current timeline visible when a transient refresh fails.
        }
    }

    private onMsgPing(msg: MsgPing) {
        this.doSend({ type: 'pong', timestamp: msg.timestamp });
    }

    private onMsgError(msg: MsgError) {
        void alertDialog({ text: msg.message });
    }

    private onMsgShutdown(msg: MsgShutdown) {
        void alertDialog({ text: msg.message });
    }

    private onMsgGameCounter(msg: MsgCounter) {
        // console.log("Gcnt=", msg.cnt);
        const gameCount = document.getElementById('g_cnt') as HTMLElement;
        patch(gameCount, h('counter#g_cnt', ngettext('%1 game in play', '%1 games in play', msg.cnt)));
    }

    private onMsgUserCounter(msg: MsgCounter) {
        // console.log("Ucnt=", msg.cnt);
        const userCount = document.getElementById('u_cnt') as HTMLElement;
        patch(userCount as HTMLElement, h('counter#u_cnt', ngettext('%1 player', '%1 players', msg.cnt)));
    }

    private onMsgAutoPairingCounter(msg: MsgCounter) {
        // console.log("APcnt=", msg.cnt);
        const gameCount = document.getElementById('ap_cnt') as HTMLElement;
        patch(gameCount, h('counter#ap_cnt', ngettext('%1 auto pairing', '%1 auto pairings', msg.cnt)));
    }

    private onMsgStreams(msg: MsgStreams) {
        const items = this.allowedVariants ? [] : msg.items;
        this.streams = patch(
            this.streams,
            h(
                'div#streams',
                items.map(stream => this.streamView(stream)),
            ),
        );
    }

    private onMsgLeaderboard(msg: MsgLeaderboard) {
        this.leaders = patch(this.leaders, this.leadersView(msg));
    }

    private onMsgTournamentWinners(msg: MsgTournamentWinners) {
        this.winners = patch(this.winners, this.winnersView(msg));
    }

    private onMsgSpotlights(msg: MsgSpotlights) {
        const items = msg.items.filter(spotlight => this.spotlightAllowed(spotlight));
        this.spotlights = patch(
            this.spotlights,
            h('div#spotlights', [
                h(
                    'div',
                    items.map(spotlight => this.spotlightView(spotlight)),
                ),
                h('a.cont-link', { attrs: { href: '/calendar' } }, _('Tournament calendar') + ' »'),
            ]),
        );
    }

    private onMsgTvGame(msg: TvGame) {
        if (!this.isVariantAllowed(msg.variant)) {
            this.tvGameId = '';
            this.renderEmptyTvGame();
            return;
        }
        this.tvGame = msg;
        this.renderEmptyTvGame();
        this.renderTvGame();
    }

    private onMsgBoard = (msg: MsgBoard) => {
        if (this.tvGameChessground === undefined || this.tvGameId !== msg.gameId) {
            return;
        }

        this.tvGameChessground.set({
            fen: msg.fen,
            turnColor: msg.fen.split(' ')[1] === 'w' ? 'white' : 'black',
            check: msg.check,
            lastMove: uci2LastMove(msg.lastMove),
        });
    };
}

function seekHeader() {
    return h('thead', [
        h('tr', [
            h('th', [h('div#santa')]),
            h('th', _('Player')),
            h('th', _('Rating')),
            h('th', _('Time')),
            h('th', _('Variant')),
            h('th', _('Mode')),
        ]),
    ]);
}

function runSeeks(vnode: VNode, model: PyChessModel) {
    const el = vnode.elm as HTMLElement;
    new LobbyController(el, model);
    // console.log("lobbyView() -> runSeeks()", el, model, ctrl);
}

export function lobbyView(model: PyChessModel): VNode[] {
    boardSettings.assetURL = model.assetURL;
    const puzzle = JSON.parse(model.puzzle);
    const gameCategory = model.gameCategory ?? 'all';
    const blogsRaw = JSON.parse(model.blogs);
    const blogs = blogsRaw.filter((post: Post) => matchesGameCategory(post.category, gameCategory));
    const username = model.username;
    const anonUser = model['anon'] === 'True';
    const timelineEntries = timelineEntriesFromModel(model);
    const allowedVariants = allowedVariantsForCategory(gameCategory);
    const allCorrGames = JSON.parse(model.corrGames);
    const corrGames = (
        allowedVariants ? allCorrGames.filter((game: Game) => allowedVariants.has(game.variant)) : allCorrGames
    ).sort(compareGames(username));
    const gpCounter = corrGames.length;

    const myTurnGameCounter = (sum: number, game: Game) => sum + (game.tp === username ? 1 : 0);
    const count = corrGames.reduce(myTurnGameCounter, 0);

    const showPuzzle = !allowedVariants || allowedVariants.has(puzzle.v);
    let dailyPuzzle: VNode[] = [];
    if (showPuzzle) {
        const variant = VARIANTS[puzzle.v];
        const turnColor = puzzle.f.split(' ')[1] === 'w' ? 'white' : 'black';
        const first = _(variant.colors.first);
        const second = _(variant.colors.second);

        dailyPuzzle = [
            h('span.vstext', [
                h('span.text', _('Puzzle of the day')),
                h('span.text', _('%1 to play', turnColor === 'white' ? first : second)),
            ]),
            h(
                `div#mainboard.${variant.boardFamily}.${variant.pieceFamily}.${variant.ui.boardMark}`,
                {
                    class: { 'with-pockets': !!variant.pocket },
                    style: { '--ranks': variant.pocket ? String(variant.board.dimensions.height) : 'undefined' },
                },
                [
                    h(`div.cg-wrap.${variant.board.cg}.mini`, {
                        hook: {
                            insert: vnode => {
                                const boardWrap = vnode.elm as HTMLElement;
                                const boardHost = sizeMiniBoardHost(boardWrap);
                                boardSettings.updateScopedBoardStyle(variant, vnode.elm as Element);
                                boardSettings.updateScopedPieceStyle(variant, vnode.elm as Element);
                                Chessground(boardWrap, {
                                    orientation: variant.name === 'racingkings' ? 'white' : turnColor,
                                    fen: puzzle.f,
                                    dimensions: variant.board.dimensions,
                                    coordinates: false,
                                    viewOnly: true,
                                    addDimensionsCssVarsTo: boardHost ?? document.body,
                                    pocketRoles: variant.pocket?.roles,
                                });
                            },
                        },
                    }),
                ],
            ),
        ];
    }

    let tabs = [];
    tabs.push(
        h(
            'button.site-tab',
            { attrs: { role: 'tab', 'aria-selected': false, 'aria-controls': 'panel-1', id: 'tab-1', type: 'button' } },
            _('Lobby'),
        ),
    );
    tabs.push(
        h(
            'button.site-tab',
            { attrs: { role: 'tab', 'aria-selected': false, 'aria-controls': 'panel-2', id: 'tab-2', type: 'button' } },
            _('Correspondence'),
        ),
    );
    if (corrGames.length > 0) {
        tabs.push(
            h(
                'button.site-tab',
                {
                    attrs: {
                        role: 'tab',
                        'aria-selected': false,
                        'aria-controls': 'panel-3',
                        id: 'tab-3',
                        type: 'button',
                    },
                },
                [
                    ngettext('%1 game in play', '%1 games in play', gpCounter),
                    h('span.noread.data-count', { attrs: { 'data-count': count } }),
                ],
            ),
        );
    }
    if (!anonUser) {
        tabs.push(
            h(
                'button.site-tab',
                {
                    attrs: {
                        role: 'tab',
                        'aria-selected': false,
                        'aria-controls': 'panel-4',
                        id: 'tab-4',
                        type: 'button',
                    },
                },
                _('Auto pairing'),
            ),
        );
    }

    let containers = [];
    containers.push(h('div', { attrs: { role: 'tablist' } }, tabs));
    containers.push(
        h(
            'div.seek-container',
            { attrs: { id: 'panel-1', role: 'tabpanel', tabindex: '-1', 'aria-labelledby': 'tab-1' } },
            [
                h('div.seeks-table', [
                    h('div.seeks-wrapper', h('table.seeks', { hook: { insert: vnode => runSeeks(vnode, model) } })),
                ]),
            ],
        ),
    );
    containers.push(
        h(
            'div.corr-container',
            { attrs: { id: 'panel-2', role: 'tabpanel', tabindex: '-1', 'aria-labelledby': 'tab-2' } },
            [h('div.seeks-table', [h('div.seeks-wrapper', h('table.seeks'))])],
        ),
    );
    if (corrGames.length > 0) {
        const cgMap: { [gameId: string]: [Api, string] } = {};
        handleOngoingGameEvents(username, cgMap);

        containers.push(
            h(
                'div.games-container',
                { attrs: { id: 'panel-3', role: 'tabpanel', tabindex: '-1', 'aria-labelledby': 'tab-3' } },
                [
                    h('div.seeks-table', [
                        h('div.seeks-wrapper', [
                            h(
                                'games-grid#games',
                                corrGames.map((game: Game) => gameViewPlaying(cgMap, game, username)),
                            ),
                        ]),
                    ]),
                ],
            ),
        );
    }

    if (!anonUser) {
        containers.push(
            h(
                'div.auto-container',
                { attrs: { id: 'panel-4', role: 'tabpanel', tabindex: '-1', 'aria-labelledby': 'tab-4' } },
                [
                    h('div.seeks-table', [
                        h('div.seeks-wrapper', [
                            h('div.auto-pairing', [
                                h('div.auto-pairing-actions'),
                                h('div.auto-rating-range'),
                                h('div.timecontrols'),
                                h('div.variants'),
                            ]),
                        ]),
                    ]),
                ],
            ),
        );
    }

    return [
        /* NAMED, BECAUSE THE LOBBY HAS TWO OF THESE. `<aside>` carries the `complementary` landmark
           implicitly, and an unnamed one is announced as just "complementary" -- so a landmark list
           on this page read "complementary, complementary" and neither could be told from the
           other. The name is also spoken every time a reader passes it, which is the argument for
           keeping it short.

           IT COVERS THREE THINGS, not only the one that happens to be populated: streams,
           tournament spotlights and the timeline. Naming it for the tournaments would go stale the
           moment a stream is live. */
        h('aside.sidebar-first', { attrs: { 'aria-label': _("What's up") } }, [
            h('div#streams'),
            h('div#spotlights'),
            timelinePanel(timelineEntries, anonUser),
        ]),
        h('div.seeks', containers),
        h('div#variants-catalog'),
        // The buttons that start a game, plus the online counters. "New game" is what the region is
        // FOR; the counters are incidental to it.
        h('aside.sidebar-second', { attrs: { 'aria-label': _('Create a game') } }, [
            h('div.seekbuttons'),
            h('div.lobby-count', [
                h('a', { attrs: { href: '/players' } }, [h('counter#u_cnt')]),
                h('a', { attrs: { href: '/games' } }, [h('counter#g_cnt')]),
                h('counter#ap_cnt'),
            ]),
            h('div.seekdialog'),
        ]),
        h('div.tv', [
            h('a.lobby-support-link', { attrs: { href: '/patron' } }, [
                h(
                    'span.lobby-support-link__icon.icon-patron-wing',
                    { attrs: { 'aria-hidden': 'true' } },
                ),
                h('span.lobby-support-link__text', [
                    h('strong', _('Donate')),
                    h('span', _('Become a PyChess Patron')),
                ]),
            ]),
            h('a#tv-game', { attrs: { href: '/tv' } }),
        ]),
        h('under-lobby', [
            h(
                'posts',
                blogs.map((post: Post) =>
                    h('a.post', { attrs: { href: post['url'] || `/blogs/${post['_id']}` } }, [
                        h('span.post-media', [
                            h('img', {
                                attrs: {
                                    src:
                                        (post['image'] || '').startsWith('http://') ||
                                        (post['image'] || '').startsWith('https://')
                                            ? `${post['image']}`
                                            : model.assetURL + `${post['image']}`,
                                    alt: `${post['imageAlt'] || post['alt'] || ''}`,
                                },
                            }),
                            h('time', `${post['date']}`),
                            h('span.author', [
                                h('player-title', `${post['author_title'] || post['atitle'] || ''} `),
                                `${post['author']}`,
                            ]),
                        ]),
                        h('span.text', [
                            h('strong', `${post['title']}`),
                            h('span', `${post['intro'] || post['subtitle'] || ''}`),
                        ]),
                    ]),
                ),
            ),
            h('div.lobby-ranking-panels', [h('div#leaders.lobby-ranking'), h('div#winners.lobby-ranking')]),
            h('div.lobby-links-block', [
                h(
                    'a.reflist',
                    { attrs: { href: 'https://discord.gg/aPs8RKr', rel: 'noopener', target: '_blank' } },
                    'Discord',
                ),
                h(
                    'a.reflist',
                    {
                        attrs: {
                            href: 'https://github.com/pychess/pychess-variants',
                            rel: 'noopener',
                            target: '_blank',
                        },
                    },
                    'Github',
                ),
                h(
                    'a.reflist',
                    {
                        attrs: {
                            href: 'https://www.youtube.com/channel/UCj_r_FSVXQFLgZLwSeFBE8g',
                            rel: 'noopener',
                            target: '_blank',
                        },
                    },
                    'YouTube',
                ),
                h('div.internalLinks', [
                    h('a.reflist', { attrs: { href: '/faq' } }, _('FAQ')),
                    h('a.reflist', { attrs: { href: '/stats' } }, _('Stats')),
                    h('a.reflist', { attrs: { href: '/about' } }, _('About')),
                    h('a.reflist', { attrs: { href: '/friendly-sites' } }, _('Friendly sites')),
                    h('a.reflist', { attrs: { href: '/contact' } }, _('Contact')),
                    h('a.reflist', { attrs: { href: '/terms' } }, _('Terms')),
                    h('a.reflist', { attrs: { href: '/privacy' } }, _('Privacy')),
                ]),
            ]),
        ]),
        h('div.puzzle', showPuzzle ? [h('a#daily-puzzle', { attrs: { href: '/puzzle/daily' } }, dailyPuzzle)] : []),
    ];
}
