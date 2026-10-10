import { h, VNode } from 'snabbdom';

import { Api } from 'chessgroundx/api';
import * as cg from 'chessgroundx/types';
import { Chessground } from 'chessgroundx';

import { boardSettings } from './boardSettings';
import { patch } from './document';
import { timeControlStr } from './view';
import { PyChessModel } from './types';
import { aiDisplayName, aiLevel } from './result';
import { sizeMiniBoardHost } from './miniBoard';
import { getLastMoveFen, VARIANTS } from './variants';
import { subscribeOngoingRealtime } from './ongoingRealtime';
import { displayUsername } from './user';

export interface Game {
    gameId: string;
    variant: string;
    chess960: boolean;
    base: number;
    inc: number;
    byoyomi: number;
    b: string;
    bTitle: string;
    w: string;
    wTitle: string;
    level: number;
    fen: cg.FEN;
    lastMove: string;
    day: number;
}

type GameData = [Api, string];
type Games = Map<string, GameData>;
let gamesRealtime: ReturnType<typeof subscribeOngoingRealtime> | null = null;

function gameView(games: Games, game: Game) {
    const variant = VARIANTS[game.variant];
    let lastMove, fen;
    [lastMove, fen] = getLastMoveFen(variant.name, game.lastMove, game.fen);
    return h(
        `minigame#${game.gameId}.${variant.boardFamily}.${variant.pieceFamily}.${variant.ui.boardMark}`,
        {
            class: {
                'with-pockets': !!variant.pocket,
                'smaller-text': game.bTitle == 'BOT',
            },
            on: { click: () => window.location.assign('/' + game.gameId) },
        },
        h('div', [
            h('div.row', [
                h('div.variant-info', [
                    h('div.icon', {
                        props: { title: variant.displayName(game.chess960) },
                        attrs: { 'data-icon': variant.icon(game.chess960) },
                    }),
                    h('div.tc', timeControlStr(game.base, game.inc, game.byoyomi, game.day)),
                ]),
                h('div.name.row-name', [
                    h('player-title', ' ' + game.bTitle + ' '),
                    displayUsername(aiDisplayName(game.b, game.variant)) + aiLevel(game.b, game.level),
                ]),
            ]),
            h(`div.cg-wrap.${variant.board.cg}.mini`, {
                hook: {
                    insert: vnode => {
                        const boardWrap = vnode.elm as HTMLElement;
                        sizeMiniBoardHost(boardWrap);
                        boardSettings.updateScopedBoardStyle(variant, vnode.elm as Element);
                        boardSettings.updateScopedPieceStyle(variant, vnode.elm as Element);
                        const cg = Chessground(boardWrap, {
                            fen: fen,
                            lastMove: lastMove,
                            dimensions: variant.board.dimensions,
                            coordinates: false,
                            viewOnly: true,
                            pocketRoles: variant.pocket?.roles,
                        });
                        games.set(game.gameId, [cg, game.variant]);
                    },
                },
            }),
            h('div.name', [
                h('player-title', ' ' + game.wTitle + ' '),
                displayUsername(aiDisplayName(game.w, game.variant)) + aiLevel(game.w, game.level),
            ]),
        ]),
    );
}

export function renderGames(model: PyChessModel): VNode[] {
    boardSettings.assetURL = model.assetURL;
    const variant = model.variant;
    const xmlhttp = new XMLHttpRequest();
    const url = '/api/games' + (variant !== '' ? `/${variant}` : '');

    xmlhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            const response = JSON.parse(this.responseText);
            const oldVNode = document.getElementById('games');
            const games: Games = new Map();
            if (oldVNode instanceof Element) {
                patch(
                    oldVNode as HTMLElement,
                    h(
                        'grid-container#games',
                        response.map((game: Game) => gameView(games, game)),
                    ),
                );

                gamesRealtime?.close();
                gamesRealtime = subscribeOngoingRealtime(data => {
                    const message = JSON.parse(data);
                    const gameData = games.get(message.gameId);
                    if (gameData === undefined) return;
                    let cg, variantName;
                    [cg, variantName] = gameData;
                    let lastMove, fen;
                    [lastMove, fen] = getLastMoveFen(variantName, message.lastMove, message.fen);
                    cg.set({
                        fen: fen,
                        lastMove: lastMove,
                    });
                });
            }
        }
    };
    xmlhttp.open('GET', url, true);
    xmlhttp.send();

    return [h('grid-container#games')];
}
