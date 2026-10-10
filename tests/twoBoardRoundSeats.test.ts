import { h } from 'snabbdom';

import { patch } from '../client/document';
import { twoBoardSeats } from '../client/two-board/common/seatConfiguration';
import { Seat } from '../client/two-board/common/seat';
import { RoundSeatView, RoundSeatViews } from '../client/two-board/round/roundSeatView';
import { RoundControllerBughouse } from '../client/two-board/round/roundCtrl';
import { SeatConfiguration } from '../client/two-board/common/seatConfiguration';
import { PyChessModel, BugBoardName } from '../client/types';
import * as cg from 'chessgroundx/types';

function model(overrides: Partial<PyChessModel> = {}): PyChessModel {
    return {
        wplayer: 'Anna',
        wtitle: 'GM',
        wrating: '2500',
        bplayer: 'Boris',
        btitle: '',
        brating: '1800',
        wplayerB: 'Carl',
        wtitleB: 'BOT',
        wratingB: '2000',
        bplayerB: 'Dana',
        btitleB: 'IM',
        bratingB: '2200',
        ...overrides,
    } as PyChessModel;
}

const slots: Array<[0 | 1, BugBoardName]> = [
    [0, 'a'],
    [0, 'b'],
    [1, 'a'],
    [1, 'b'],
];

// Builds the four views and mounts their composed blocks the way round.ts does:
// one top-level patch over vnodes the views already hold, so every leaf's .elm is
// populated without a single id lookup. Board a stays first at each position, the
// DOM order flip/switch relies on.
function mountViews(): RoundSeatViews {
    const views: RoundSeatViews = {
        a: [new RoundSeatView(0, 'a'), new RoundSeatView(1, 'a')],
        b: [new RoundSeatView(0, 'b'), new RoundSeatView(1, 'b')],
    };
    document.body.innerHTML = '<div id="root"></div>';
    patch(
        document.getElementById('root')!,
        h('div#root', [views.a[0].view(), views.b[0].view(), views.a[1].view(), views.b[1].view()]),
    );
    return views;
}

// The round clock behavior lives on RoundControllerBughouse, which cannot be
// constructed in jsdom (chessground, sockets, a live websocket). Its clock methods
// only touch `seats` and `seatViews`, so drive them off the prototype with those two
// wired up — the same objects the real constructor would have built.
type CtrlInternals = RoundControllerBughouse & {
    seats: SeatConfiguration<Seat>;
    seatViews: RoundSeatViews;
    topColor: Record<BugBoardName, cg.Color>;
    username: string;
    base: number;
    inc: number;
    level: number;
    createSeatWidgets: () => void;
    wireClockDifferences: () => void;
};

function ctrlStub(
    viewer: string,
    views: RoundSeatViews,
    overrides: Partial<PyChessModel> = {},
): RoundControllerBughouse {
    const seats = twoBoardSeats(model(overrides), viewer);
    const ctrl = Object.create(RoundControllerBughouse.prototype) as CtrlInternals;
    ctrl.seats = seats;
    ctrl.seatViews = views;
    ctrl.topColor = { a: seats.initialTopColor('a'), b: seats.initialTopColor('b') };
    ctrl.username = viewer;
    ctrl.base = 5;
    ctrl.inc = 3;
    ctrl.level = 1;
    // Each clock also reports to its board's screen-reader summary, which these tests do not inspect.
    const board = () => ({ boardSummary: { setClock: () => {} } });
    Object.assign(ctrl, { boardA: board(), boardB: board() });
    ctrl.createSeatWidgets();
    ctrl.wireClockDifferences();
    return ctrl;
}

const el = (id: string) => document.getElementById(id);

describe('RoundSeatView markup', () => {
    test('each slot renders its whole info-wrap block, with every element the round page expects', () => {
        mountViews();

        for (const [position, board] of slots) {
            const slot = `${position}${board}`;
            expect(el(`clock${slot}`)).not.toBeNull();
            expect(el(`difference${slot}`)).not.toBeNull();
            expect(el(`berserk${slot}`)).not.toBeNull();
            expect(el(`misc-info${slot}`)).not.toBeNull();
            expect(el(`rplayer${slot}`)).not.toBeNull();
        }

        // flip/switch reach these blocks by class name and take [0] — a class-token match,
        // so 'info-wrap0' also matches the bug block and board a must stay first in DOM order
        for (const position of [0, 1]) {
            expect(document.getElementsByClassName(`info-wrap${position} bug`)).toHaveLength(1);
            const plain = document.getElementsByClassName(`info-wrap${position}`);
            expect(plain).toHaveLength(2);
            expect(plain[0].classList.contains('bug')).toBe(false);
        }
    });

    test('board b carries the bug class on its info-wrap, clock-wrap and player bar; board a does not', () => {
        mountViews();

        expect(el('rplayer0b')!.classList.contains('bug')).toBe(true);
        expect(el('rplayer0a')!.classList.contains('bug')).toBe(false);
        expect(el('difference0b')!.closest('.clock-wrap')!.classList.contains('bug')).toBe(true);
        expect(el('difference0a')!.closest('.clock-wrap')!.classList.contains('bug')).toBe(false);
    });

    test('the player bar root is round-player{position}, not the tag that swallowed the class before', () => {
        mountViews();

        expect(el('rplayer0b')!.tagName.toLowerCase()).toBe('round-player0');
        expect(el('rplayer1a')!.tagName.toLowerCase()).toBe('round-player1');
    });

    test('the clock-difference indicator starts at zero, rendered by the page patch itself', () => {
        mountViews();

        const indicator = el('difference0a')!.querySelector('.clock-difference')!;
        expect(indicator.textContent).toBe('0');
        expect(indicator.classList.contains('positive')).toBe(true);
    });

    test('rendering the player bar keeps the root element and its layout classes', () => {
        const bugTop = mountViews().b[0];
        const rootBefore = el('rplayer0b');

        bugTop.renderPlayerBar({ username: 'Dana', title: 'IM', rating: '2200' }, 0);

        const rootAfter = el('rplayer0b');
        expect(rootAfter).toBe(rootBefore); // same element, not replaced
        expect(rootAfter!.classList.contains('bug')).toBe(true);
        expect(rootAfter!.querySelector('player-title')!.textContent).toBe('IM ');
        expect(rootAfter!.querySelector('rating')!.textContent).toBe('2200');
    });

    test('presence toggles the icon in place, keeping the online class and the i-side tag', () => {
        const topA = mountViews().a[0];
        topA.renderPlayerBar({ username: 'Boris', title: '', rating: '1800' }, 0);

        const icon = el('player0a')!;
        expect(icon.classList.contains('icon-offline')).toBe(true);

        topA.setPresence(true);

        expect(el('player0a')).toBe(icon); // diffed, not replaced
        expect(icon.tagName.toLowerCase()).toBe('i-side');
        expect(icon.classList.contains('online')).toBe(true);
        expect(icon.classList.contains('icon-online')).toBe(true);
        expect(icon.classList.contains('icon-offline')).toBe(false);
    });

    test('a presence change before the bar has a player is remembered, not rendered', () => {
        const topA = mountViews().a[0];

        topA.setPresence(true);
        expect(el('rplayer0a')!.querySelector('i-side')).toBeNull();

        topA.renderPlayerBar({ username: 'Boris', title: '', rating: '1800' }, 0);
        expect(el('player0a')!.classList.contains('icon-online')).toBe(true);
    });

    test('the difference is signed: + when ahead, - when behind, bare zero when level', () => {
        const topA = mountViews().a[0];
        const text = () => el('difference0a')!.querySelector('.clock-difference')!.textContent;

        topA.renderDifference(12);
        expect(text()).toBe('+12');
        topA.renderDifference(-12);
        expect(text()).toBe('-12');
        topA.renderDifference(0);
        expect(text()).toBe('0');
    });

    test('renderDifference patches only its own leaf, leaving inline grid-area styles alone', () => {
        const topA = mountViews().a[0];
        const block = document.getElementsByClassName('info-wrap0')[0] as HTMLElement;
        block.style.gridArea = 'clock-bot'; // what swapClockGridAreasForFlip() writes

        topA.renderDifference(-7);

        expect(block.style.gridArea).toBe('clock-bot');
        const indicator = el('difference0a')!.querySelector('.clock-difference')!;
        expect(indicator.textContent).toBe('-7');
        expect(indicator.classList.contains('negative')).toBe(true);
        expect(indicator.classList.contains('positive')).toBe(false);
    });
});

describe('round clock behavior on the controller', () => {
    test('every seat gets a clock rendered into its own slot, and the player bars are painted', () => {
        const views = mountViews();
        const ctrl = ctrlStub('Anna', views);

        // Anna is white on board a, so she sits at the bottom (position 1) of board a
        const wA = ctrl.seats.byBoardAndColor('a', 'white');
        expect(ctrl.seats.all.every(s => s.clock !== undefined)).toBe(true);
        expect(wA.clock!.id).toBe('clock1a');
        expect(wA.clock!.duration).toBe(5 * 60 * 1000);
        expect(el('rplayer1a')!.textContent).toContain('Anna');
        expect(el('rplayer0a')!.textContent).toContain('Boris');
    });

    test('a tick renders the difference against the opponent-partner clock, on both seats views', () => {
        const views = mountViews();
        const ctrl = ctrlStub('Anna', views);

        const wA = ctrl.seats.byBoardAndColor('a', 'white'); // slot 1a
        const wB = ctrl.seats.byBoardAndColor('b', 'white'); // her opponent's partner, slot 0b
        wB.clock!.setTime(4 * 60 * 1000); // one minute behind

        wA.clock!.tickCallbacks[0](5 * 60 * 1000);

        expect(el('difference1a')!.querySelector('.clock-difference')!.textContent).toBe('+60');
        expect(el('difference0b')!.querySelector('.clock-difference')!.textContent).toBe('-60');
    });

    test('updateClocks pauses the mover, applies both server times and starts the next clock', () => {
        const views = mountViews();
        const ctrl = ctrlStub('Anna', views);
        const white = ctrl.seats.byBoardAndColor('a', 'white').clock!;
        const black = ctrl.seats.byBoardAndColor('a', 'black').clock!;
        white.start();

        ctrl.updateClocks('a', 'black', [111000, 222000], -1);

        expect(white.running).toBe(false);
        expect(white.duration).toBe(111000);
        expect(black.duration).toBe(222000);
        expect(black.running).toBe(true);
    });

    test('updateClocks does not start a clock once the game is over', () => {
        const views = mountViews();
        const ctrl = ctrlStub('Anna', views);
        const black = ctrl.seats.byBoardAndColor('a', 'black').clock!;

        ctrl.updateClocks('a', 'black', [111000, 222000], 1);

        expect(black.running).toBe(false);
        expect(black.duration).toBe(222000);
    });

    test('updateClocks on board b leaves board a alone', () => {
        const views = mountViews();
        const ctrl = ctrlStub('Anna', views);
        const whiteA = ctrl.seats.byBoardAndColor('a', 'white').clock!;

        ctrl.updateClocks('b', 'white', [111000, 222000], -1);

        expect(whiteA.duration).toBe(5 * 60 * 1000);
        expect(ctrl.seats.byBoardAndColor('b', 'white').clock!.duration).toBe(111000);
    });

    test('setPresence marks every seat that username occupies', () => {
        const views = mountViews();
        const ctrl = ctrlStub('Anna', views);

        ctrl.setPresence('Dana', true);

        // for Anna (white on a), white is on top of board b, so Dana (black on b) is at the bottom
        expect(el('player1b')!.classList.contains('icon-online')).toBe(true);
        expect(el('player0b')!.classList.contains('icon-online')).toBe(false);
        expect(el('player1a')!.classList.contains('icon-online')).toBe(false);
    });

    test("the viewer's own presence marks their seat, not the board-a bottom slot", () => {
        // Dana plays black on board b only. For her, white is on top of board b (so she
        // is at 1b) and the bottom of board a is her partner Anna — the slot the connect
        // and reconnect handlers used to target regardless of where the viewer sits.
        const ctrl = ctrlStub('Dana', mountViews());

        ctrl.setPresence(ctrl.username, true);

        expect(el('player1b')!.classList.contains('icon-online')).toBe(true);
        expect(el('player1a')!.classList.contains('icon-online')).toBe(false);
    });

    test('presence toggles back off, keeping the icon element and updating its state classes', () => {
        const ctrl = ctrlStub('Anna', mountViews());

        ctrl.setPresence('Anna', true);
        const icon = el('player1a')!;
        expect(icon.classList.contains('icon-online')).toBe(true);

        ctrl.setPresence('Anna', false);

        expect(el('player1a')).toBe(icon);
        expect(icon.classList.contains('icon-online')).toBe(false);
        expect(icon.classList.contains('icon-offline')).toBe(true);
        expect(icon.classList.contains('online')).toBe(false);
        expect(icon.classList.contains('offline')).toBe(true);
    });

    test('setPresence in simul mode marks both of the shared seats', () => {
        const ctrl = ctrlStub('Anna', mountViews(), { bplayerB: 'Boris', btitleB: '', bratingB: '1800' });

        ctrl.setPresence('Boris', true);

        // Boris holds black on both boards: top of a, bottom of b
        expect(el('player0a')!.classList.contains('icon-online')).toBe(true);
        expect(el('player1b')!.classList.contains('icon-online')).toBe(true);
        expect(el('player1a')!.classList.contains('icon-online')).toBe(false);
    });
});
