import { h, VNode } from 'snabbdom';

import { Chessground } from 'chessgroundx';
import { Api } from 'chessgroundx/api';

import { JSONObject, PyChessModel } from './types';
import { _ } from './i18n';
import { patch } from './document';
import { alertDialog } from './alertDialog';
import { chatMessage, chatView, ChatController, replayingChat } from './chat';
import { colorIcon } from './chess';
import { getLastMoveFen, VARIANTS, Variant, variantKey } from './variants';
import { timeControlStr } from './view';
import { initializeClock, localeOptions, syncTournamentStartAlerts } from './tournamentClock';
import { tournamentLifecycleView } from './tournamentLifecycle';
import { gameType } from './result';
import { boardSettings } from './boardSettings';
import { MsgBoard, MsgChat, MsgFullChat, MsgSpectators, MsgGameEnd, MsgNewGame } from './messages';
import {
    MsgUserStatus,
    MsgGetGames,
    TournamentGame,
    MsgTournamentStatus,
    MsgUserConnectedTournament,
    MsgGetPlayers,
    TournamentPlayer,
    MsgError,
    MsgPing,
    TopGame,
} from './tournamentType';
import { newWebsocket } from '@/socket/webSocketUtils';
import { faq, roundRobinFaq, swissFaq } from './tournamentFaq';
import { displayUsername, userLink } from './user';
import { sound } from './sound';
import { redirectFirst } from './tournamentAlerts';

interface Duel {
    id: string; // game id
    wp: string; // white username
    wt: string; // white title
    wr: string; // white reating
    wk: number; // white tournament rank
    bp: string;
    bt: string;
    br: string;
    bk: number;
}

interface MsgDuels {
    type: string;
    duels: Duel[];
}

const T_STATUS = {
    0: 'created',
    1: 'started',
    2: 'aborted',
    3: 'finished',
    4: 'archived',
};

const scoreTagNames = ['score', 'streak', 'double'];

const SCORE_SHIFT = 100000;
const RR_SYSTEM = 1;
const SWISS_SYSTEM = 2;
const VARIANTEND_STATUS = 12;

const SHIELD = 's';

export class TournamentController implements ChatController {
    sock;
    tournamentId: string;
    readyState: number; // seems unused
    buttons: VNode;
    lifecycleActions: VNode;
    system: number;
    rounds: number;
    currentRound: number;
    players: TournamentPlayer[]; // seems unused
    nbPlayers: number;
    page: number;
    tournamentStatus: string;
    userStatus: string;
    userRating: number; // seems unused
    action: VNode;
    clockdiv: VNode;
    topGame: TopGame;
    topGameId: string;
    topGameChessground: Api;
    vDuels: VNode | HTMLElement;
    spectatorsContainer: VNode | HTMLElement;
    playerGamesOn: boolean;
    variant: Variant;
    chess960: boolean;
    rated: string;
    startDate: string;
    visitedPlayer: string;
    secondsToStart: number;
    secondsToFinish: number;
    roundOngoingGames: number;
    secondsToNextRound: number;
    manualNextRoundPending: boolean;
    clockInterval: ReturnType<typeof setInterval> | null;
    username: string;
    anon: boolean;
    private: boolean;
    creatorCanManage: boolean;
    isTournamentDirector: boolean;

    constructor(el: HTMLElement, model: PyChessModel) {
        console.log('TournamentController constructor', el, model);
        this.tournamentId = model['tournamentId'];
        this.username = model['username'];
        this.creatorCanManage = model.tournamentmanager;
        this.isTournamentDirector = model['tournamentDirector'];
        this.nbPlayers = 0;
        this.page = 1;
        this.rounds = model['rounds'] || 0;
        this.currentRound = 0;
        this.system = model['tsystem'] || 0;
        this.tournamentStatus = T_STATUS[model['status'] as keyof typeof T_STATUS];
        this.visitedPlayer = '';
        this.startDate = model['date'];
        this.secondsToStart = 0;
        this.secondsToFinish = 0;
        this.roundOngoingGames = 0;
        this.secondsToNextRound = 0;
        this.manualNextRoundPending = false;
        this.clockInterval = null;
        this.private = false;

        const onOpen = () => {
            this.doSend({
                type: 'tournament_user_connected',
                username: model['username'],
                tournamentId: model['tournamentId'],
            });
            this.doSend({ type: 'get_players', tournamentId: model['tournamentId'], page: this.page });
        };

        this.sock = newWebsocket('wst');
        this.sock.onopen = () => onOpen();
        this.sock.onmessage = (e: MessageEvent) => this.onMessage(e);

        this.variant = VARIANTS[model['variant']];
        this.chess960 = model['chess960'] === 'True';
        this.rated = model['rated'];

        patch(document.getElementById('lobbychat') as HTMLElement, chatView(this, 'lobbychat'));
        this.lifecycleActions = patch(
            document.getElementById('tournament-lifecycle') as HTMLElement,
            this.renderLifecycleActions(),
        );
        this.buttons = patch(document.getElementById('page-controls') as HTMLElement, this.renderButtons());

        if (this.tournamentStatus === 'created') {
            const faqView =
                this.system === SWISS_SYSTEM
                    ? swissFaq(this.rated)
                    : this.system === RR_SYSTEM
                      ? roundRobinFaq(this.rated)
                      : faq(this.rated);
            patch(document.querySelector('div.tour-faq') as HTMLElement, faqView);
        } else {
            patch(document.querySelector('div.tour-faq') as HTMLElement, h('!'));
        }

        this.clockdiv = patch(document.getElementById('clockdiv') as HTMLElement, h('div#clockdiv'));
        this.playerGamesOn = false;

        this.vDuels = document.querySelector('div.duels') as HTMLElement;

        this.anon = model['anon'] === 'True';

        boardSettings.assetURL = model.assetURL;
    }

    doSend(message: JSONObject) {
        // console.log("---> tournament doSend():", message);
        this.sock.send(JSON.stringify(message));
    }

    goToPage(page: number) {
        let newPage = page;
        if (page < 1) {
            newPage = 1;
        } else {
            const x = Math.floor(this.nbPlayers / 10);
            const y = this.nbPlayers % 10;
            const lastPage = x + (y > 0 ? 1 : 0);
            newPage = page > lastPage ? lastPage : page;
        }
        if (newPage !== this.page) {
            this.page = newPage;
            this.doSend({ type: 'get_players', tournamentId: this.tournamentId, page: newPage });
        }
    }

    goToMyPage() {
        this.doSend({ type: 'my_page', tournamentId: this.tournamentId });
    }

    login() {
        window.location.assign('/login');
    }

    join() {
        if (this.private) {
            const password = prompt('This tournament is private. Please enter the password:');
            if (password !== null) {
                this.doSend({ type: 'join', tournamentId: this.tournamentId, password: password });
            }
        } else {
            this.doSend({ type: 'join', tournamentId: this.tournamentId });
        }
    }

    pause() {
        this.doSend({ type: 'pause', tournamentId: this.tournamentId });
    }

    withdraw() {
        this.doSend({ type: 'withdraw', tournamentId: this.tournamentId });
    }

    renderLifecycleActions() {
        return tournamentLifecycleView(
            {
                status: this.tournamentStatus,
                system: this.system,
                manualNextRoundPending: this.manualNextRoundPending,
                creatorCanManage: this.creatorCanManage,
                isDirector: this.isTournamentDirector,
            },
            () => this.doSend({ type: 'start_next_round', tournamentId: this.tournamentId }),
        );
    }

    updateLifecycleActions() {
        this.lifecycleActions = patch(this.lifecycleActions, this.renderLifecycleActions());
    }

    renderButtons() {
        return h('div#page-controls.btn-controls', [
            h('div.pager', [
                h('button', { on: { click: () => this.goToPage(1) } }, [
                    h('i.icon.icon-fast-backward', { props: { title: _('First') } }),
                ]),
                h('button', { on: { click: () => this.goToPage(this.page - 1) } }, [
                    h('i.icon.icon-step-backward', { props: { title: _('Prev') } }),
                ]),
                // TODO: update
                h(
                    'span.page',
                    `${(this.page - 1) * 10 + 1} - ${Math.min(this.page * 10, this.nbPlayers)} / ${this.nbPlayers}`,
                ),
                h('button', { on: { click: () => this.goToPage(this.page + 1) } }, [
                    h('i.icon.icon-step-forward', { props: { title: _('Next') } }),
                ]),
                h('button', { on: { click: () => this.goToPage(10000) } }, [
                    h('i.icon.icon-fast-forward', { props: { title: _('Last') } }),
                ]),
                h('button', { on: { click: () => this.goToMyPage() } }, [
                    h('i.icon.icon-target', { props: { title: _('Scroll to your player') } }),
                ]),
            ]),
            h('div#action'),
        ]);
    }

    updateActionButton() {
        let button = h('div#action');
        switch (this.tournamentStatus) {
            case 'created':
                if (this.userStatus === 'joined') {
                    button = h(
                        'button#action',
                        { on: { click: () => this.withdraw() }, class: { icon: true, 'icon-flag-o': true } },
                        _('WITHDRAW'),
                    );
                } else {
                    button = h(
                        'button#action',
                        { on: { click: () => this.join() }, class: { icon: true, 'icon-play': true } },
                        _('JOIN'),
                    );
                }
                break;
            case 'started':
                if ('spectator|paused|withdrawn'.includes(this.userStatus)) {
                    button = h(
                        'button#action',
                        { on: { click: () => this.join() }, class: { icon: true, 'icon-play': true } },
                        _('JOIN'),
                    );
                } else {
                    const pauseLabel = this.system > 0 ? _('WITHDRAW') : _('PAUSE');
                    button = h(
                        'button#action',
                        { on: { click: () => this.pause() }, class: { icon: true, 'icon-pause': true } },
                        pauseLabel,
                    );
                }
                break;
        }
        if (this.anon && 'created|started'.includes(this.tournamentStatus)) {
            button = h(
                'button#action',
                { on: { click: () => this.login() }, class: { icon: true, 'icon-play': true } },
                _('LOG IN'),
            );
        }
        // console.log("updateActionButton()", this.tournamentStatus, button);
        this.action = patch(document.getElementById('action') as HTMLElement, button);
    }

    completed() {
        return 'aborted|finished|archived'.includes(this.tournamentStatus);
    }

    private isArenaSystem() {
        return this.system === 0;
    }

    renderSummary(msg: MsgTournamentStatus) {
        const summaryRows: VNode[] = [];
        summaryRows.push(
            h('tr', [h('th', _('Players')), h('td', msg.nbPlayers)]),
            h('tr', [h('th', _('Average rating')), h('td', Math.round(msg.sumRating / msg.nbPlayers))]),
            h('tr', [h('th', _('Games played')), h('td', msg.nbGames)]),
            h('tr', [
                h('th', _('%1 wins', _(this.variant.colors.first))),
                h('td', this.calcRate(msg.nbGames, msg.wWin)),
            ]),
            h('tr', [
                h('th', _('%1 wins', _(this.variant.colors.second))),
                h('td', this.calcRate(msg.nbGames, msg.bWin)),
            ]),
            h('tr', [h('th', _('Draws')), h('td', this.calcRate(msg.nbGames, msg.draw))]),
        );
        if (this.isArenaSystem()) {
            summaryRows.push(
                h('tr', [h('div', _('Berserk rate')), h('td', this.calcRate(msg.nbGames * 2, msg.berserk))]),
            );
        }
        const downloadLinks: VNode[] = [
            h('table.tour-stats-links', [
                h(
                    'a.i-dl.icon.icon-download',
                    {
                        attrs: {
                            href: '/games/export/tournament/' + this.tournamentId,
                            download: 'pychess_tournament_' + this.tournamentId + '.pgn',
                        },
                    },
                    _('Download all games'),
                ),
            ]),
            h('table.tour-stats-links', [
                h(
                    'a.i-dl.icon.icon-download',
                    {
                        attrs: {
                            href: '/tournament/json/' + this.tournamentId,
                            download: 'pychess_tournament_' + this.tournamentId + '.json',
                        },
                    },
                    _('Download all games in JSON'),
                ),
            ]),
        ];

        if (this.system === SWISS_SYSTEM) {
            downloadLinks.push(
                h('table.tour-stats-links', [
                    h(
                        'a.i-dl.icon.icon-download',
                        {
                            attrs: {
                                href: '/games/export/tournament/' + this.tournamentId + '/trf',
                                download: 'pychess_tournament_' + this.tournamentId + '.trf',
                            },
                        },
                        _('Download TRF pairing state'),
                    ),
                ]),
            );
        }

        const summary = h('div#summary', { class: { box: true } }, [
            h('h2', _('Tournament complete')),
            h('table', summaryRows),
            ...downloadLinks,
        ]);
        const el = document.getElementById('summarybox') as HTMLElement;
        if (el) patch(el, summary);
    }

    renderPlayers(players: TournamentPlayer[]) {
        const rows = players.map((player, index) => this.playerView(player, (this.page - 1) * 10 + index + 1));
        return rows;
    }

    private scoreSheetEntries(points: any[]): Array<any | null> {
        if (!(this.system > 0 && this.rounds > 0)) return points;
        const entries = points.slice(0, this.rounds);
        while (entries.length < this.rounds) entries.push(null);
        return entries;
    }

    private playerView(player: TournamentPlayer, index: number) {
        if (player.name === this.visitedPlayer) {
            this.doSend({ type: 'get_games', tournamentId: this.tournamentId, player: this.visitedPlayer });
        }
        let fullScore = Math.trunc(player.score / SCORE_SHIFT);
        if (this.system > 0 && this.variant.name !== 'janggi') fullScore = fullScore / 2;
        const fixedRoundSheet = this.system > 0 && this.rounds > 0;
        const sheetEntries = this.scoreSheetEntries(player.points);
        const rowCells: Array<VNode | string | number> = [
            h('td.rank', [
                player.paused && !this.completed() ? h('i', { class: { icon: true, 'icon-pause': true } }) : index,
            ]),
            h('td.player', [
                h('span.title', player.title),
                userLink(player.name, [displayUsername(player.name)], { className: 'name user-link' }),
                h('span', player.rating),
            ]),
            h(`td.sheet${fixedRoundSheet ? '.fixed-rounds' : ''}`, [
                h(
                    'div',
                    sheetEntries.map((s: any | null) => {
                        if (s === null) {
                            return h('score.point.empty', '\u00a0');
                        }
                        let score = Array.isArray(s) ? s[0] : s;
                        if (this.system > 0 && score !== '*' && score !== '-' && this.variant.name !== 'janggi')
                            score = score / 2;
                        const pointKlass = this.system > 0 ? '.point' : '';
                        const isNumericScore = typeof score === 'number';
                        const resultKlass =
                            this.system > 0 && isNumericScore
                                ? score >= 1
                                    ? '.win'
                                    : score === 0.5
                                      ? '.draw'
                                      : '.lose'
                                : '';
                        if (score === 0.5) score = '½';
                        return h(scoreTagNames[(s[1] || 1) - 1] + pointKlass + resultKlass, [score]);
                    }),
                ),
            ]),
            h('td.total', [
                h('fire', [
                    player.fire === 2 && this.tournamentStatus === 'started'
                        ? h('i', { class: { icon: true, 'icon-fire': true } })
                        : '',
                ]),
                h('strong.score', fullScore),
                // h('span.perf', player.perf)
            ]),
        ];

        if (this.system > 0) {
            rowCells.push(h('td.berger', this.bergerDisplay(player.berger)));
        }

        return h('tr', { on: { click: () => this.onClickPlayer(player.name) } }, rowCells);
    }

    private onClickPlayer(player: string) {
        console.log('onClickPlayer()', player);
        if (this.tournamentStatus === 'created') return;

        if (this.completed()) {
            if (this.playerGamesOn && this.visitedPlayer === player) {
                (document.getElementById('summary') as HTMLElement).style.display = 'block';
                (document.getElementById('player') as HTMLElement).style.display = 'none';
                this.playerGamesOn = false;
            } else {
                this.doSend({ type: 'get_games', tournamentId: this.tournamentId, player: player });
                (document.getElementById('summary') as HTMLElement).style.display = 'none';
                (document.getElementById('player') as HTMLElement).style.display = 'block';
                this.playerGamesOn = true;
                this.visitedPlayer = player;
            }
            // started
        } else {
            this.doSend({ type: 'get_games', tournamentId: this.tournamentId, player: player });
            if (this.playerGamesOn && this.visitedPlayer === player) {
                this.renderTopGame();
                (document.getElementById('player') as HTMLElement).style.display = 'none';
                this.playerGamesOn = false;
            } else {
                this.renderEmptyTopGame();
                (document.getElementById('player') as HTMLElement).style.display = 'block';
                this.playerGamesOn = true;
            }
            this.visitedPlayer = player;
        }
    }

    renderGames(games: TournamentGame[]) {
        const rows = games.reverse().map((game, index) => this.gameView(game, games.length - index));
        return rows;
    }

    result(result: string, color: string, status?: number) {
        if (this.variant.name === 'janggi') {
            let value = '*';
            let klass = '';
            if (result === '1-0') {
                const won = color === 'w';
                if (status === VARIANTEND_STATUS) {
                    value = won ? '4' : '2';
                } else {
                    value = won ? '7' : '0';
                }
                klass = won ? '.win' : '.lose';
            } else if (result === '0-1') {
                const won = color === 'b';
                if (status === VARIANTEND_STATUS) {
                    value = won ? '4' : '2';
                } else {
                    value = won ? '7' : '0';
                }
                klass = won ? '.win' : '.lose';
            } else if (result === '1/2-1/2') {
                value = '0';
            } else if (result === '-') {
                value = '-';
            }
            return h(`td.result${klass}`, value);
        }

        let value = '*';
        switch (result) {
            case '1-0':
                value = color === 'w' ? '1' : '0';
                break;
            case '0-1':
                value = color === 'b' ? '1' : '0';
                break;
            case '1/2-1/2':
                value = '½';
                break;
            case '-':
                value = '-';
                break;
        }
        const klass = value === '1' ? '.win' : value === '0' ? '.lose' : '';
        return h(`td.result${klass}`, value);
    }

    private gameView(game: TournamentGame, index: number) {
        if (game.result === '-') {
            const variantIsJanggi = this.variant.name === 'janggi';
            const unplayedLabel =
                game.unplayedType === 'late' ? _('Late') : game.unplayedType === 'absent' ? _('Absent') : _('Bye');
            const unplayedScore =
                game.unplayedType === 'late'
                    ? variantIsJanggi
                        ? '2'
                        : '½'
                    : this.system === SWISS_SYSTEM && game.unplayedType === 'bye'
                      ? variantIsJanggi
                          ? '7'
                          : '1'
                      : '-';
            return h('tr', [
                h('th', index),
                h('td.bye', { attrs: { colspan: '3' } }, unplayedLabel),
                h('td.result', unplayedScore),
            ]);
        } else {
            const color = game.color === 'w' ? this.variant.colors.first : this.variant.colors.second;
            return h(
                'tr',
                {
                    on: {
                        click: () => {
                            window.open('/' + game.gameId, '_blank', 'noopener');
                        },
                    },
                },
                [
                    h('th', index),
                    h('td.player', [
                        h('span.title', game.title),
                        userLink(game.name, [displayUsername(game.name)], { className: 'name user-link' }),
                    ]),
                    h('td', game.rating),
                    h('td', [h('i-side.icon', { class: { [colorIcon(this.variant.name, color)]: true } })]),
                    this.result(game.result, game.color, game.status),
                ],
            );
        }
    }

    private tSystem(system: number) {
        switch (system) {
            case 0:
                return _('Arena');
            case 1:
                return _('Round-Robin');
            default:
                return _('Swiss');
        }
    }

    private updateTournamentSystemLabel() {
        const tsystem = document.getElementById('tsystem') as Element | null;
        if (!tsystem) return;

        const parts = [gameType(this.rated)];
        if (this.system > 0 && this.rounds > 0 && this.tournamentStatus !== 'created') {
            const round = this.completed() ? this.rounds : Math.min(this.rounds, Math.max(1, this.currentRound));
            parts.push(`${round}/${this.rounds} ${_('rounds')}`);
        }
        parts.push(this.tSystem(this.system));
        patch(tsystem, h('div#tsystem', parts.join(' • ')));
    }

    renderStats(msg: MsgGetGames) {
        const games = msg.games.filter(game => game.result !== '-');
        const gamesLen = games.length;
        const avgOp = gamesLen ? Math.round(games.reduce((a, b) => a + b.rating, 0) / gamesLen) : undefined;
        const statsRows: VNode[] = [];
        if (this.system > 0) {
            statsRows.push(h('tr', [h('th', _('Tie Break')), h('td', this.bergerDisplay(msg.berger))]));
        }
        statsRows.push(h('tr', [h('th', _('Performance')), h('td', msg.perf)]));
        statsRows.push(h('tr', [h('th', _('Games played')), h('td', gamesLen)]));
        statsRows.push(h('tr', [h('th', _('Win rate')), h('td', this.calcRate(msg.nbGames, msg.nbWin))]));
        statsRows.push(h('tr', [h('th', _('Average opponent')), h('td', avgOp)]));
        if (this.isArenaSystem()) {
            statsRows.push(h('tr', [h('th', _('Berserk rate')), h('td', this.calcRate(msg.nbGames, msg.nbBerserk))]));
        }

        return [
            h('span.close', {
                on: { click: () => this.onClickPlayer(this.visitedPlayer) },
                attrs: { 'data-icon': 'j' },
            }),
            h('h2', [h('rank', msg.rank + '. '), playerInfo(msg.name, msg.title)]),
            h('table.stats', statsRows),
        ];
    }

    renderEmptyTopGame() {
        patch(document.getElementById('top-game') as HTMLElement, h('div#top-game.empty'));
    }

    renderTopGame() {
        if (this.topGame === undefined) return;

        const game = this.topGame;
        const variant = VARIANTS[game.variant];
        const elements = [
            h('div.player', [
                h('user', [
                    h('rank', '#' + game.br),
                    userLink(game.b, [displayUsername(game.b)], { className: 'user-link' }),
                ]),
                h('div#bresult'),
            ]),
            h(
                `div#mainboard.${variant.boardFamily}.${variant.pieceFamily}.${variant.ui.boardMark}`,
                {
                    class: { 'with-pockets': !!variant.pocket },
                    on: { click: () => window.location.assign('/' + game.gameId) },
                },
                [
                    h(`div.cg-wrap.${variant.board.cg}.mini`, {
                        hook: {
                            insert: vnode => {
                                boardSettings.updateScopedBoardStyle(variant, vnode.elm as Element);
                                boardSettings.updateScopedPieceStyle(variant, vnode.elm as Element);
                                let lastMove, fen;
                                [lastMove, fen] = getLastMoveFen(this.variant.name, game.lastMove, game.fen);
                                const cg = Chessground(vnode.elm as HTMLElement, {
                                    fen: fen,
                                    lastMove: lastMove,
                                    dimensions: variant.board.dimensions,
                                    coordinates: false,
                                    viewOnly: true,
                                    addDimensionsCssVarsTo: document.body,
                                    pocketRoles: variant.pocket?.roles,
                                });
                                this.topGameChessground = cg;
                                this.topGameId = game.gameId;
                            },
                        },
                    }),
                ],
            ),
            h('div.player', [
                h('user', [
                    h('rank', '#' + game.wr),
                    userLink(game.w, [displayUsername(game.w)], { className: 'user-link' }),
                ]),
                h('div#wresult'),
            ]),
        ];

        patch(document.getElementById('top-game') as HTMLElement, h('div#top-game', elements));
    }

    calcRate(nbGames: number, nbWin: number) {
        return (nbGames !== 0 ? Math.round(100 * (nbWin / nbGames)) : 0) + '%';
    }

    private bergerDisplay(berger: number) {
        const rounded = Math.round(berger * 2) / 2;
        return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
    }

    renderPodium(players: TournamentPlayer[]) {
        return h('div.podium', [
            h('div.second', [
                h('div.trophy'),
                playerInfo(players[1].name, players[1].title),
                h('table.stats', [
                    ...(this.system > 0
                        ? [h('tr', [h('th', _('Tie Break')), h('td', this.bergerDisplay(players[1].berger))])]
                        : []),
                    h('tr', [h('th', _('Performance')), h('td', players[1].perf)]),
                    h('tr', [h('th', _('Games played')), h('td', players[1].nbGames)]),
                    h('tr', [h('th', _('Win rate')), h('td', this.calcRate(players[1].nbGames, players[1].nbWin))]),
                    ...(this.isArenaSystem()
                        ? [
                              h('tr', [
                                  h('th', _('Berserk rate')),
                                  h('td', this.calcRate(players[1].nbGames, players[1].nbBerserk)),
                              ]),
                          ]
                        : []),
                ]),
            ]),
            h('div.first', [
                h('div.trophy'),
                playerInfo(players[0].name, players[0].title),
                h('table.stats', [
                    ...(this.system > 0
                        ? [h('tr', [h('th', _('Tie Break')), h('td', this.bergerDisplay(players[0].berger))])]
                        : []),
                    h('tr', [h('th', _('Performance')), h('td', players[0].perf)]),
                    h('tr', [h('th', _('Games played')), h('td', players[0].nbGames)]),
                    h('tr', [h('th', _('Win rate')), h('td', this.calcRate(players[0].nbGames, players[0].nbWin))]),
                    ...(this.isArenaSystem()
                        ? [
                              h('tr', [
                                  h('th', _('Berserk rate')),
                                  h('td', this.calcRate(players[0].nbGames, players[0].nbBerserk)),
                              ]),
                          ]
                        : []),
                ]),
            ]),
            h('div.third', [
                h('div.trophy'),
                playerInfo(players[2].name, players[2].title),
                h('table.stats', [
                    ...(this.system > 0
                        ? [h('tr', [h('th', _('Tie Break')), h('td', this.bergerDisplay(players[2].berger))])]
                        : []),
                    h('tr', [h('th', _('Performance')), h('td', players[2].perf)]),
                    h('tr', [h('th', _('Games played')), h('td', players[2].nbGames)]),
                    h('tr', [h('th', _('Win rate')), h('td', this.calcRate(players[2].nbGames, players[2].nbWin))]),
                    ...(this.isArenaSystem()
                        ? [
                              h('tr', [
                                  h('th', _('Berserk rate')),
                                  h('td', this.calcRate(players[2].nbGames, players[2].nbBerserk)),
                              ]),
                          ]
                        : []),
                ]),
            ]),
        ]);
    }

    private onMsgGetGames(msg: MsgGetGames) {
        const oldStats = document.getElementById('stats') as Element;
        oldStats.innerHTML = '';
        patch(oldStats, h('div#stats.box', [h('tbody', this.renderStats(msg))]));

        const oldGames = document.getElementById('games') as Element;
        oldGames.innerHTML = '';
        patch(oldGames, h('table#games.pairings.box', [h('tbody', this.renderGames(msg.games))]));
    }

    private onMsgGetPlayers(msg: MsgGetPlayers) {
        if (this.completed() && msg.podium && msg.players.length >= 3 && msg.nbGames > 0) {
            const podium = document.getElementById('podium') as HTMLElement;
            if (podium instanceof Element) {
                patch(podium, this.renderPodium(msg.podium));
            }
        }
        if (this.completed()) {
            this.vDuels = patch(this.vDuels, h('div.duels'));
        }

        if (this.page === msg.page || msg.requestedBy === this.username) {
            this.players = msg.players;
            this.page = msg.page;
            this.nbPlayers = msg.nbPlayers;
            this.buttons = patch(this.buttons, this.renderButtons());

            const oldPlayers = document.getElementById('players') as Element;
            oldPlayers.innerHTML = '';
            patch(
                oldPlayers,
                h('table#players.players.box', { class: { 'fixed-rounds': this.system > 0 } }, [
                    h('tbody', this.renderPlayers(msg.players)),
                ]),
            );
        }
    }

    private onMsgNewGame(msg: MsgNewGame) {
        redirectFirst(msg.gameId, () => {
            sound.genericNotify();
            // Give the short notification sound time to become audible before
            // unloading this tab, like lila's beeping redirect does.
            window.setTimeout(() => window.location.assign('/' + msg.gameId), 700);
        });
    }

    private onMsgGameUpdate() {
        this.doSend({ type: 'get_players', tournamentId: this.tournamentId, page: this.page });
    }

    durationString(minutes: number) {
        if (minutes === 0) return '';
        if (minutes < 60) {
            return ' • ' + minutes + 'm';
        } else {
            return ' • ' + Math.floor(minutes / 60) + 'h' + (minutes % 60 !== 0 ? ' ' + (minutes % 60) + 'm' : '');
        }
    }

    renderDescription(text: string) {
        const parts = text.split(/(\[.*?\))/g);
        if (parts !== null && parts.length > 0) {
            const newArr = parts.map(el => {
                const txtPart = el.match(/\[(.+)\]/); //get only the txt
                const urlPart = el.match(/\((.+)\)/); //get only the link
                if (txtPart && urlPart) {
                    return h('a', { attrs: { href: urlPart[1], target: '_blank' } }, txtPart[1]);
                } else {
                    return el;
                }
            });
            return h('div.description', newArr);
        }
        return h('div.description', text);
    }

    renderDefender(name: string, title: string) {
        return h('div.defender', [_('Defender:'), playerInfo(name, title)]);
    }

    private onMsgUserConnected(msg: MsgUserConnectedTournament) {
        if (msg.chatClosed) {
            const chatEntryEl = document.getElementById('chat-entry') as HTMLInputElement;
            chatEntryEl.disabled = true;
        }

        const chess960 = this.chess960;
        const dataIcon = this.variant.icon(chess960);

        const trophy = document.getElementById('trophy') as Element;
        if (trophy && msg.frequency === SHIELD) patch(trophy, h('a', { class: { 'shield-trophy': true } }, dataIcon));

        this.system = msg.tsystem;

        const tminutes = document.getElementById('tminutes') as Element;
        patch(tminutes, h('span#tminutes', this.durationString(msg.tminutes)));

        this.startDate = msg.startsAt;
        const startsAtDate = new Date(msg.startsAt);
        const startsAt = document.getElementById('startsAt') as Element;
        if (startsAt) patch(startsAt, h('date', startsAtDate.toLocaleString('default', localeOptions)));

        if (msg.startFen !== '') {
            const startFen = document.getElementById('startFen') as Element;
            const fen = msg.startFen.split(' ').join('_').replace(/\+/g, '.');
            patch(
                startFen,
                h('p', [
                    _('Custom position') + ' • ',
                    h('a', { attrs: { href: '/analysis/' + this.variant.name + '?fen=' + fen } }, _('Analysis board')),
                ]),
            );
        }

        if (msg.defender_name !== undefined) {
            msg.description =
                _(
                    'This Shield trophy is unique. The winner keeps it for one month, then must defend it during the next %1 Shield tournament!',
                    this.variant.displayName(chess960),
                ) +
                ' ' +
                msg.description;
        }
        const description = document.getElementById('description') as Element;
        if (msg.description.length > 0 && description) patch(description, this.renderDescription(msg.description));

        const defender = document.getElementById('defender') as Element;
        if (msg.defender_name && defender) patch(defender, this.renderDefender(msg.defender_name, msg.defender_title));

        this.username = msg.username;
        this.tournamentStatus = T_STATUS[msg.tstatus as keyof typeof T_STATUS];
        this.userStatus = msg.ustatus;
        this.userRating = msg.urating;
        this.secondsToStart = msg.secondsToStart;
        this.secondsToFinish = msg.secondsToFinish;
        this.rounds = msg.rounds ?? this.rounds;
        this.currentRound = msg.currentRound ?? 0;
        this.roundOngoingGames = msg.roundOngoingGames ?? 0;
        this.secondsToNextRound = msg.secondsToNextRound ?? 0;
        this.manualNextRoundPending = msg.manualNextRound ?? false;
        this.creatorCanManage = msg.creatorCanManage;
        this.private = msg.private;
        this.updateTournamentSystemLabel();

        this.updateActionButton();
        this.updateLifecycleActions();

        if (!this.completed()) {
            initializeClock(this);
        }
    }

    private onMsgSpectators = (msg: MsgSpectators) => {
        const container = document.getElementById('spectators') as HTMLElement;
        this.spectatorsContainer = patch(
            this.spectatorsContainer ?? container,
            h('under-chat#spectators', this.renderSpectators(msg.spectators)),
        );
    };

    private renderSpectators(raw: string): Array<VNode | string> {
        if (/^\d+$/.test(raw)) {
            return [_('Spectators: '), raw];
        }

        const parts = raw
            .split(',')
            .map(part => part.trim())
            .filter(Boolean);
        const children: Array<VNode | string> = [_('Spectators: ')];
        parts.forEach((part, idx) => {
            if (idx > 0) children.push(', ');
            if (part.startsWith('Anonymous(')) {
                children.push(part);
            } else {
                children.push(userLink(part, [displayUsername(part)]));
            }
        });
        return children;
    }

    private onMsgUserStatus(msg: MsgUserStatus) {
        this.userStatus = msg.ustatus;
        syncTournamentStartAlerts(this);
        this.updateActionButton();
    }

    private onMsgTournamentStatus(msg: MsgTournamentStatus) {
        const oldStatus = this.tournamentStatus;
        const oldCurrentRound = this.currentRound;
        const oldRoundOngoingGames = this.roundOngoingGames;
        const oldSecondsToNextRound = this.secondsToNextRound;
        const oldManualNextRoundPending = this.manualNextRoundPending;
        const oldRounds = this.rounds;
        this.tournamentStatus = T_STATUS[msg.tstatus as keyof typeof T_STATUS];
        if (msg.secondsToFinish !== undefined) {
            this.secondsToFinish = msg.secondsToFinish;
        }
        if (msg.rounds !== undefined) {
            this.rounds = msg.rounds;
        }
        if (msg.currentRound !== undefined) {
            this.currentRound = msg.currentRound;
        }
        if (msg.roundOngoingGames !== undefined) {
            this.roundOngoingGames = msg.roundOngoingGames;
        }
        if (msg.secondsToNextRound !== undefined) {
            this.secondsToNextRound = msg.secondsToNextRound;
        }
        if (msg.manualNextRound !== undefined) {
            this.manualNextRoundPending = msg.manualNextRound;
        }
        if (
            oldStatus !== this.tournamentStatus ||
            oldRounds !== this.rounds ||
            oldCurrentRound !== this.currentRound ||
            oldRoundOngoingGames !== this.roundOngoingGames ||
            oldSecondsToNextRound !== this.secondsToNextRound ||
            oldManualNextRoundPending !== this.manualNextRoundPending
        ) {
            initializeClock(this);
        }
        this.updateTournamentSystemLabel();
        this.updateActionButton();
        this.updateLifecycleActions();
        const fixedRoundRoundStarted =
            this.system > 0 &&
            this.tournamentStatus === 'started' &&
            oldRoundOngoingGames === 0 &&
            this.roundOngoingGames > 0;
        if (fixedRoundRoundStarted) {
            this.doSend({ type: 'get_players', tournamentId: this.tournamentId, page: this.page });
        }
        if (this.tournamentStatus !== 'created') {
            const faqEl = document.querySelector('div.tour-faq') as HTMLElement;
            if (faqEl) patch(faqEl, h('!'));
        }
        if (this.completed()) {
            patch(this.clockdiv, h('div#clockdiv'));
            this.renderEmptyTopGame();
            (document.getElementById('player') as HTMLElement).style.display = 'none';
            this.renderSummary(msg);
            this.doSend({ type: 'get_players', tournamentId: this.tournamentId, page: this.page });
        }
    }

    private onMsgTopGame(msg: TopGame) {
        this.topGame = msg;
        if (this.tournamentStatus === 'started' && !this.playerGamesOn) {
            this.renderEmptyTopGame();
            this.renderTopGame();
        }
    }

    private renderDuels(duels: Duel[]) {
        return duels.map(duel =>
            h('a', { attrs: { href: '/' + duel.id } }, [
                h('line.a', [
                    h('strong', [userLink(duel.wp, [displayUsername(duel.wp)], { className: 'user-link' })]),
                    h('span', [h('em.rating', duel.br), h('em.rank', '#' + duel.bk)]),
                ]),
                h('line.b', [
                    h('span', [h('em.rank', '#' + duel.wk), h('em.rating', duel.wr)]),
                    h('strong', [userLink(duel.bp, [displayUsername(duel.bp)], { className: 'user-link' })]),
                ]),
            ]),
        );
    }

    private onMsgDuels(msg: MsgDuels) {
        if (this.vDuels) {
            const header = this.tournamentStatus !== 'created' ? _('Top games') : '';
            this.vDuels = patch(this.vDuels, h('div.duels', [h('h2', header)].concat(this.renderDuels(msg.duels))));
        }
    }

    private onMsgBoard = (msg: MsgBoard) => {
        if (this.topGameChessground === undefined || this.topGameId !== msg.gameId) {
            return;
        }
        let lastMove, fen;
        [lastMove, fen] = getLastMoveFen(this.variant.name, msg.lastMove, msg.fen);

        this.topGameChessground.set({
            fen: fen,
            turnColor: msg.fen.split(' ')[1] === 'w' ? 'white' : 'black',
            check: msg.check,
            lastMove: lastMove,
        });
    };

    private checkStatus = (msg: MsgGameEnd) => {
        if (this.topGameChessground === undefined || this.topGameId !== msg.gameId) {
            return;
        }
        console.log(msg);
        if (msg.status >= 0) {
            const result = msg.result.split('-');
            patch(document.getElementById('wresult') as HTMLElement, h('div#wresult', result[0]));
            patch(document.getElementById('bresult') as HTMLElement, h('div#bresult', result[1]));
        }
    };

    private onMsgChat(msg: MsgChat) {
        chatMessage(msg.user, msg.message, 'lobbychat', msg.time);
    }
    private onMsgFullChat(msg: MsgFullChat) {
        // To prevent multiplication of messages we have to remove old messages div first
        replayingChat('lobbychat');
        patch(document.getElementById('messages') as HTMLElement, h('div#messages-clear'));
        // then create a new one
        patch(document.getElementById('messages-clear') as HTMLElement, h('div#messages', { attrs: { role: 'none' } }));
        msg.lines.forEach(line => chatMessage(line.user, line.message, 'lobbychat', line.time));
    }

    private onMsgPing(msg: MsgPing) {
        this.doSend({ type: 'pong', timestamp: msg.timestamp });
    }
    private onMsgError(msg: MsgError) {
        void alertDialog({ text: msg.message });
    }

    onMessage(evt: MessageEvent) {
        //console.log("<+++ tournament onMessage():", evt.data);
        if (evt.data === '/n') return;
        const msg = JSON.parse(evt.data);
        switch (msg.type) {
            case 'ustatus':
                this.onMsgUserStatus(msg);
                break;
            case 'tstatus':
                this.onMsgTournamentStatus(msg);
                break;
            case 'get_players':
                this.onMsgGetPlayers(msg);
                break;
            case 'new_game':
                this.onMsgNewGame(msg);
                break;
            case 'game_update':
                this.onMsgGameUpdate();
                break;
            case 'get_games':
                this.onMsgGetGames(msg);
                break;
            case 'board':
                this.onMsgBoard(msg);
                break;
            case 'gameEnd':
                this.checkStatus(msg);
                break;
            case 'duels':
                this.onMsgDuels(msg);
                break;
            case 'tournament_user_connected':
                this.onMsgUserConnected(msg);
                break;
            case 'spectators':
                this.onMsgSpectators(msg);
                break;
            case 'top_game':
                this.onMsgTopGame(msg);
                break;
            case 'lobbychat':
                this.onMsgChat(msg);
                break;
            case 'fullchat':
                this.onMsgFullChat(msg);
                break;
            case 'ping':
                this.onMsgPing(msg);
                break;
            case 'error':
                this.onMsgError(msg);
                break;
        }
    }
}

function runTournament(vnode: VNode, model: PyChessModel) {
    const el = vnode.elm as HTMLElement;
    new TournamentController(el, model);
}

export function tournamentView(model: PyChessModel): VNode[] {
    const variant = VARIANTS[model.variant] ?? VARIANTS['chess'];
    const chess960 = model.chess960 === 'True';
    const dataIcon = variant.icon(chess960);
    document.body.setAttribute(
        'style',
        `--ranks: ${variant.board.dimensions.height}; --files: ${variant.board.dimensions.width};`,
    );
    const canEdit = (model.tournamentmanager && model.status === 0) || model.admin;
    return [
        h('aside.sidebar-first', [
            h('div.game-info', [
                h('div.info0.icon', { attrs: { 'data-icon': dataIcon } }, [
                    h('div.info2', [
                        h('div.tc', [
                            timeControlStr(model['base'], model['inc'], model['byo']) + ' • ',
                            h(
                                'a',
                                {
                                    attrs: {
                                        target: '_blank',
                                        href: '/variants/' + variantKey(model.variant, chess960),
                                    },
                                },
                                variant.displayName(chess960),
                            ),
                            h('span#tminutes'),
                        ]),
                        h('div#tsystem'),
                        model.tournamentteamid
                            ? h('div.tournament-team', [
                                  h('strong', _('Team')),
                                  ' ',
                                  h(
                                      'a',
                                      { attrs: { href: `/team/${model.tournamentteamid}` } },
                                      model.tournamentteamname || model.tournamentteamid,
                                  ),
                              ])
                            : null,
                        canEdit
                            ? h('a.icon-cog.edit-tournament', {
                                  attrs: {
                                      href: `/tournaments/${model.tournamentId}/edit`,
                                      title: _('Edit tournament'),
                                  },
                              })
                            : null,
                    ]),
                ]),
                // TODO: update in onMsgUserConnected()
                h('div#description'),
                h('div#defender'),
                h('div#requirements'),
                h('div#startsAt'),
                h('div#startFen'),
            ]),
            h('div#tournament-lifecycle'),
            h('div#lobbychat'),
        ]),
        h(`div.players.${model['variant']}`, [
            h('div.box', [
                h('div.tour-header', [h('div#trophy'), h('h1', model['tournamentname']), h('div#clockdiv')]),
                h('div#podium'),
                h('div#page-controls'),
                h('div.tournament-standing-wrap', [
                    h('table#players', {
                        class: { 'fixed-rounds': model.tsystem > 0 },
                        hook: { insert: vnode => runTournament(vnode, model) },
                    }),
                ]),
                h('div.tour-faq'),
            ]),
        ]),
        h('div.tour-table', [
            h('div#summarybox'),
            h('div#top-game'),
            h('div#player', [h('div#stats.box'), h('table#games.box')]),
            h('div.duels'),
        ]),
        h('under-chat#spectators'),
    ];
}

function playerInfo(name: string, title: string) {
    return userLink(name, [h('player-title', ' ' + title + ' '), displayUsername(name)]);
}
