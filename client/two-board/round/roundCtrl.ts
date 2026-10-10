import { materializeTwoBoardHistory } from '../common/gameHistory';
import * as Mousetrap from 'mousetrap';
import * as cg from 'chessgroundx/types';
import * as util from 'chessgroundx/util';

import { _ } from '../../i18n';
import { RoundSeatView, RoundSeatViews } from './roundSeatView';
import { ChatPresetsView } from './chatPresets';
import { Seat } from '../common/seat';
import { Clock } from '../../clock';
import { RoundControllerBughouseSocket } from '../socket/sockets';
import { MovePlace, ReconnectController } from '../socket/reconnectController';
import { ChatController, chatMessage, chatSender, replayingChat } from '../../chat';
import { MovelistView } from '../common/movelist';
import { GameInfoView } from '../common/gameInfo';
import { SpectatorsView } from '../common/spectatorsView';
import { Clocks, MsgBoard, MsgGameEnd, MsgMove, MsgNewGame, MsgSpectators, MsgUserConnected, Step, StepChat } from '../../messages';
import {
    MsgUserDisconnected,
    MsgUserPresent,
    MsgDrawOffer,
    MsgDrawRejected,
    MsgResignOffer,
    MsgResignCancelled,
    MsgRematchOffer,
    MsgRematchRejected,
    MsgUpdateTV,
    MsgGameStart,
    MsgViewRematch,
} from '../../roundType';
import { BoardName, BugBoardName, JSONObject, PyChessModel } from '../../types';
import { GameControllerBughouse } from '../common/gameCtrl';
import { BLACK, WHITE, getTurnColor, uci2LastMove } from '../../chess';
import { result } from '../../result';
import { sound, soundThemeSettings } from '../../sound';
import { notify } from '../../notification';
import { chatMessageBug, resetChat } from '@/two-board/round/chat';
import { TwoBoardController, initBoardSettings, redrawBoards, clearBoardBounds } from '../twoBoardCtrl';
import {
    OfferState,
    RoundControlsView,
    renderRoundChat,
    resetMovelistDom,
    clearExtensionChoice,
    clearAbortIndicator,
    markGameOver,
    swapSeatBlocksForFlip,
    swapSeatStripsForSwitch,
    swapBoardsForSwitch,
    markRoles,
} from './roundControls';
import {
    buildGameKeyboardHelpSections,
    hideGameKeyboardHelp,
    isKeyboardHelpShortcut,
    showGameKeyboardHelp,
} from '../../gameKeyboardHelp';
import { ROUND_DROPPABLE, trackToolsPlacement } from '../common/toolsPlacement';
import { trackSeatNamePlacement } from '../common/seatNamePlacement';
import { bindPocketHotkeys } from '../../pocketHotkeys';

// live remaining time of a clock, whether or not it is currently running (mirrors Clock's own tick math)
const liveTime = (clock: Clock) => (clock.running ? clock.duration - (Date.now() - clock.startTime) : clock.duration);

export class RoundControllerBughouse extends TwoBoardController implements ChatController {
    socket: RoundControllerBughouseSocket;

    readonly anon: boolean;

    autoPromote: boolean;

    /* RECONNECTION AND RESYNCHRONISATION, WHICH IS ITS OWN SUBJECT AND NOW HAS ITS OWN OWNER.
     *
     * It holds both records — the durable queue of moves to resend, and the in-memory set of boards
     * this page is ahead of — because they answer the same question with different lifetimes and
     * only make sense together. Everything below asks it rather than deciding: what to send when the
     * socket opens, whether a board may be played on, whose clocks win, and when a queued move has
     * been overtaken. See `reconnectController.ts` for the cases and the histories that reach them.
     */
    readonly reconnect: ReconnectController;


    private readonly seatViews: RoundSeatViews;
    /* WHO IS WATCHING. The widget owns its node and the count on the Info tab; this controller's
       only part in it is handing on what the socket received. */
    private readonly spectatorsView: SpectatorsView;
    // color rendered at the top (position 0) of each board. This represents only the
    // initial positioning on the screen: flip/switch only move html elements around,
    // so these remain constant throughout the whole game.
    private readonly topColor: Record<BugBoardName, cg.Color>;

    profileid: string;
    level: number;

    tv: boolean;
    handicap: boolean = false;
    focus: boolean;
    finishedGame: boolean;

    spectator: boolean;

    controlsView: RoundControlsView;

    keyboardHelpOpen: boolean;
    private readonly onKeyboardHelpKeyDown: (event: KeyboardEvent) => void;

    get pocketHotkeyRoles(): readonly cg.Role[] | undefined {
        if (this.spectator || this.finishedGame || !this.variant.pocket) return undefined;

        const myBoards = (['a', 'b'] as const).filter(board => this.seats.myColor(board) !== undefined);
        if (myBoards.length !== 1) return undefined;

        const color = this.seats.myColor(myBoards[0])!;
        return this.variant.pocket.roles[color];
    }

    constructor(
        el1: HTMLElement,
        el1Pocket1: HTMLElement,
        el1Pocket2: HTMLElement,
        el2: HTMLElement,
        el2Pocket1: HTMLElement,
        el2Pocket2: HTMLElement,
        model: PyChessModel,
        movelistView: MovelistView,
        gameInfoView: GameInfoView,
        spectatorsView: SpectatorsView,
        seatViews: RoundSeatViews,
        chatPresetsView: ChatPresetsView | undefined,
    ) {
        super(el1, el1Pocket1, el1Pocket2, el2, el2Pocket1, el2Pocket2, model, movelistView, gameInfoView);

        this.spectatorsView = spectatorsView;

        this.anon = model.anon === 'True';

        this.focus = !document.hidden;
        document.addEventListener('visibilitychange', () => {
            this.focus = !document.hidden;
        });
        window.addEventListener('blur', () => {
            this.focus = false;
        });
        window.addEventListener('focus', () => {
            this.focus = true;
        });
        //
        // The same question isGameOver() asks. Kept because the base controller
        // maintains this field too and several places read it; the predicate is
        // what new code should use.
        this.finishedGame = this.isGameOver();
        this.tv = model['tv'];
        this.profileid = model['profileid'];
        this.level = model['level'];

        this.autoPromote = localStorage.autoPromote === undefined ? false : localStorage.autoPromote === 'true';

        this.seatViews = seatViews;
        this.topColor = { a: this.seats.initialTopColor('a'), b: this.seats.initialTopColor('b') };

        this.createSeatWidgets();
        this.wireClockDifferences();

        this.spectator = this.seats.isSpectator();

        const flagCallbackA = () => {
            if (this.seats.myColor('a') === this.boardA.turnColor) {
                this.boardA.chessground.stop();
                this.boardB.chessground.stop();
                // console.log("Flag");
                this.socket.doSend({ type: 'flag', gameId: this.gameId });
            }
        };
        const flagCallbackB = () => {
            if (this.seats.myColor('b') === this.boardB.turnColor) {
                this.boardA.chessground.stop();
                this.boardB.chessground.stop();
                // console.log("Flag");
                this.socket.doSend({ type: 'flag', gameId: this.gameId });
            }
        };

        if (!this.spectator) {
            this.seats.seatsOn('a').forEach(s => s.clock!.onFlag(flagCallbackA));
            this.seats.seatsOn('b').forEach(s => s.clock!.onFlag(flagCallbackB));
        }

        this.controlsView = new RoundControlsView();
        this.controlsView.renderInitialGameControls(
            this.spectator,
            () => this.draw(),
            () => this.resign(),
            () => this.acceptDraw(),
        );

        //////////////
        // todo: redundant setting turnColor here. It will be overwritten a moment later in onMsgBoard which is
        //       important and more correct in case of custom fen with black to move
        const myColorA = this.seats.myColor('a');
        const myColorB = this.seats.myColor('b');
        // my partner's color on one board is the opposite of my color on the other board
        const partnerColorA = myColorB === undefined ? undefined : myColorB === 'white' ? 'black' : 'white';
        const partnerColorB = myColorA === undefined ? undefined : myColorA === 'white' ? 'black' : 'white';
        this.boardA.chessground.set({
            orientation: myColorA === 'white' || partnerColorA === 'white' || this.spectator ? 'white' : 'black',
            turnColor: 'white',
            movable: {
                color: myColorA,
            },
            autoCastle: true,
        });
        this.boardB.chessground.set({
            orientation: myColorB === 'white' || partnerColorB === 'white' ? 'white' : 'black',
            turnColor: 'white',
            movable: {
                color: myColorB,
            },
            autoCastle: true,
        });

        // todo: if spectator do not render buttons, also good to render all player's messages for specatotors to see
        //       all communication as it happens. However not sure how this can be combined with usual spectators chat
        //       without becoming a bit messy, but maybe it is ok.
        renderRoundChat(this);

        // The presets' second initialisation step. They were constructed and
        // rendered before this controller existed — the page's view is built
        // first, and this runs from its insert hook — so this is the first moment
        // they can be given the ability to send. They are handed chat's own
        // sender, so a preset is reported and delivered exactly as typing the
        // same text would be.
        chatPresetsView?.wire(chatSender(this, 'bugroundchat'));

        /////////////////
        // const amISimuling = this.mycolor.get('a') !== undefined && this.mycolor.get('b') !== undefined;
        // const distinctOpps = new Set([this.wplayer, this.bplayer, this.wplayerB, this.bplayerB].filter((e) => e !== this.username));
        // const isOppSimuling = distinctOpps.size === 1;
        if (this.seats.me('a') === undefined && !this.spectator) {
            // I am not playing on board A at all. Switch:
            this.switchBoards();
        }
        // After the initial placement, so the first paint already knows which strip
        // is whose. switchBoards() marks again; this covers the case where it never
        // ran — a board-A player, a spectator, and simul, where the viewer holds a
        // seat on board A as well and so is never switched.
        markRoles(this.seatViews);
        // After the boards and the parts exist, so the first measurement is of the
        // real page; it keeps itself in step from then on.
        // First: it publishes the width the preset buttons are sized from, so the parts
        // are already their real height when the placement below measures them.
        trackToolsPlacement(ROUND_DROPPABLE, undefined, () => clearBoardBounds(this));
        trackSeatNamePlacement(() => clearBoardBounds(this));

        initBoardSettings(this.boardA, this.boardB, this.variant);

        // Before the socket, which asks it what to send the moment the connection opens.
        this.reconnect = new ReconnectController(this.gameId);

        /* WHY EACH BOARD MAY REFUSE A MOVE, WIRED ONCE.
         *
         * A board must not invite a move while one of ours is outstanding on it — branch 1.2.3 —
         * because a second move for the same ply overwrites the only record of the first, which is
         * the race scenario Q11 exists for. It must not invite one after the game has ended either.
         *
         * Neither fact is visible in the position, so `setDests()` cannot work it out; it asks
         * this instead, every time it computes. ASKED RATHER THAN PUSHED: a flag set from here
         * would be a second copy of what the controller already knows, needing an update at every
         * point the records change — and a gate that depends on somebody remembering to refresh it
         * is the bug being fixed, not the fix. */
        this.boardA.movesAllowed = () => !this.isGameOver() && !this.reconnect.waiting('a');
        this.boardB.movesAllowed = () => !this.isGameOver() && !this.reconnect.waiting('b');

        // last so when it receive initial messages on connect all dom is ready to be updated
        this.socket = new RoundControllerBughouseSocket(this);

        this.keyboardHelpOpen = false;
        this.onKeyboardHelpKeyDown = (event: KeyboardEvent) => {
            if (!this.keyboardHelpOpen) return;

            if (event.key === 'Escape' || isKeyboardHelpShortcut(event)) {
                event.preventDefault();
                event.stopPropagation();
                this.closeKeyboardHelp();
                return;
            }

            if (event.key === 'Tab') return;

            event.preventDefault();
            event.stopPropagation();
        };

        Mousetrap.bind('left', () => this.movelistView.selectMove(this, this.movelistView.ply() - 1));
        Mousetrap.bind('right', () => this.movelistView.selectMove(this, this.movelistView.ply() + 1));
        Mousetrap.bind('up', () => this.movelistView.selectMove(this, 0));
        Mousetrap.bind('down', () => this.movelistView.selectMove(this, this.steps.length - 1));
        Mousetrap.bind('f', () => this.flipBoards());
        Mousetrap.bind('?', () => this.helpDialog());

        if (!this.spectator && !this.finishedGame && this.variant.pocket) {
            const myBoards = (['a', 'b'] as const).filter(board => this.seats.myColor(board) !== undefined);
            if (myBoards.length === 1) {
                const boardName = myBoards[0];
                const color = this.seats.myColor(boardName)!;
                const board = boardName === 'a' ? this.boardA : this.boardB;
                bindPocketHotkeys(board.chessground, color, this.variant.pocket.roles[color]);
            }
        }

        soundThemeSettings.buildBugChatSounds();
    }

    helpDialog() {
        if (this.keyboardHelpOpen) {
            this.closeKeyboardHelp();
        } else {
            this.openKeyboardHelp();
        }
    }

    openKeyboardHelp() {
        this.keyboardHelpOpen = true;
        document.addEventListener('keydown', this.onKeyboardHelpKeyDown, true);
        showGameKeyboardHelp(
            this,
            buildGameKeyboardHelpSections(this, { flipDescription: _('Flip boards') }),
        );
    }

    closeKeyboardHelp() {
        if (!this.keyboardHelpOpen) return;
        this.keyboardHelpOpen = false;
        document.removeEventListener('keydown', this.onKeyboardHelpKeyDown, true);
        hideGameKeyboardHelp();
    }

    private viewAt(position: 0 | 1, board: BugBoardName): RoundSeatView {
        return this.seatViews[board][position];
    }

    private viewOf(seat: Seat): RoundSeatView {
        return this.viewAt(seat.color === this.topColor[seat.boardName] ? 0 : 1, seat.boardName);
    }

    // gives every seat the live clock its view renders into, and paints the player bars
    private createSeatWidgets(): void {
        this.seats.all.forEach(seat => {
            const view = this.viewOf(seat);
            const clock = view.createClock(this.base, this.inc);
            seat.clock = clock;
            const summary = (seat.boardName === 'a' ? this.boardA : this.boardB).boardSummary;
            clock.onRender(time => summary.setClock(seat.color, time));
            summary.setClock(seat.color, clock.duration);
            view.renderPlayerBar(seat.player, this.level);
        });
    }

    // difference value = this clock's live time minus the live time of the clock of your
    // opponent's partner (the same color, on the other board). Updated on every tick.
    private wireClockDifferences(): void {
        this.seats.all.forEach(seat => {
            seat.clock!.onTick(diff => {
                seat.clock!.renderTime(diff);
                this.renderClockDifferences();
            });
        });
    }

    /** Every seat's difference badge, recomputed from what the four clocks hold right now.
     *
     * ALL FOUR, and from live values rather than from the tick's own `diff`, because a clock's
     * value changes TWO ways and only one of them used to reach here. Ticking called this; being
     * SET did not — `Clock.setTime()` repaints the clock text and nothing else. So a seat that was
     * resynced while PAUSED kept a badge computed from its pre-resync value until it next ran, which
     * can be a whole move away.
     *
     * Measured on `d0cEddrd` 2026-08-30: after a reconnect gave board A black 44s back, the clocks
     * agreed to the second — `aw - bw` and `bb - ab` both 114 — while the two paused seats still
     * showed ±158. The badges corrected themselves only when that clock started ticking again.
     *
     * Cheap enough to do wholesale: four reads and four writes, on a tick whose granularity is
     * measured in tenths of a second.
     */
    private renderClockDifferences(): void {
        this.seats.all.forEach(seat => {
            const counterpart = this.seats.opponentsPartnerOf(seat);
            const mine = liveTime(seat.clock!);
            const theirs = liveTime(counterpart.clock!);
            this.viewOf(seat).renderDifference(Math.round((mine - theirs) / 1000));
        });
    }

    // online/offline indicator on the player bars of every seat this username occupies
    setPresence(username: string, online: boolean): void {
        this.seats.all.filter(s => s.player.username === username).forEach(s => this.viewOf(s).setPresence(online));
    }

    /**
     * @param boardName - for which board we are updating the clocks
     * @param turnColor - whose turn it is after this move - their clock should be started
     * @param status - current game status (needed to know whether the clock should actually start)
     *
     * Stops clock of user how made the move for the board in question,
     * updates the clock times with the new values,
     * starts the clock of the player whose turn is now
     * */
    /**
     * Whether a game status means the game has finished.
     *
     * The numbers come from `GameStatus` in `server/const.py`: CREATED is -2 and
     * STARTED is -1, so anything below zero is a game still being played. ABORTED
     * is 0 and every real result — mate, resign, timeout, draw, flag — is above it.
     * So "finished" is `>= 0`, and an aborted game counts as finished.
     *
     * Takes the status rather than reading `this.status`, because several callers
     * are asking about a status that has just arrived from the server and has not
     * been stored yet, and asking the wrong one of those two is a real bug rather
     * than a style question.
     *
     * An aborted game counts as over, including for the notice that chat has become
     * visible to everyone — that site tested `> 0` and so said nothing on an aborted
     * game; it asks this now, deliberately.
     */
    isGameOver(status: number = this.status): boolean {
        return status >= 0;
    }

    updateClocks(boardName: BoardName, turnColor: cg.Color, msgClocks: Clocks, status: number) {
        const board = boardName as BugBoardName;
        const whiteClock = this.seats.byBoardAndColor(board, 'white').clock!;
        const blackClock = this.seats.byBoardAndColor(board, 'black').clock!;

        const moverClock = turnColor === 'white' ? blackClock : whiteClock;
        const nextClock = turnColor === 'white' ? whiteClock : blackClock;

        moverClock.pause(false);

        // PAUSE THE CLOCK THAT IS ABOUT TO BE RESTARTED, TOO — it may already be running, and then
        // the `start()` below is a no-op that leaves its measurement origin stale.
        //
        // `Clock` keeps `duration` (the value when it last started) and `startTime`, and renders
        // `duration - (now - startTime)`. `setTime()` writes `duration` alone, and `start()` returns
        // immediately `if (this.running)` without refreshing `startTime`. So setting a server value
        // on an already-running clock subtracts the elapsed time A SECOND TIME: the server has
        // already deducted it before sending.
        //
        // On a normal move this cannot happen — the side to move next is the one that was just
        // waiting, so its clock is stopped and `pause()` here returns at once. It bites on the FULL
        // board message, a reconnect or a page load, where both boards' running clocks are re-set
        // while still running. The error is the age of `startTime`: the time since that board's last
        // move. Measured 2026-08-30 on `4G3ZyGze`: board A, whose last move was 57s earlier, came
        // back 57s light; board B, which had not moved all game, came back **397s light** — the
        // server sent a correct 3202447 and the page rendered 46:41 instead of 53:22. A board that
        // has not moved for 19 minutes reads 19 minutes short, which is `ZdoeZseB`'s 41:14.
        //
        // Not fixed inside `setTime()`, deliberately: the one-board round page calls
        // `setTime(duration + 15000)` on running clocks to add time, and relies on `startTime`
        // surviving so that the live value gains exactly 15s.
        nextClock.pause(false);

        whiteClock.setTime(msgClocks[WHITE]);
        blackClock.setTime(msgClocks[BLACK]);

        if (!this.isGameOver(status)) {
            nextClock.start();
        }

        // The two clocks above were SET, not ticked, and a set does not reach the badges on its
        // own — see `renderClockDifferences()`. Any resync therefore has to say so explicitly, or
        // the seats that are not running keep showing a difference computed from the old values.
        this.renderClockDifferences();
    }

    // required by the ChatController interface (chatView() calls ctrl.doSend()); forwards to the real implementation
    get doSend() {
        return this.socket.doSend;
    }

    flipBoards(): void {
        swapSeatBlocksForFlip(this.seatViews);
        super.flipBoards();
    }

    // Deliberately not super.switchBoards(): that also moves the pocket elements,
    // which is right for a page that places pockets on their own. Here a pocket
    // travels inside its seat's strip, so moving it again would undo the switch.
    switchBoards(): void {
        swapBoardsForSwitch();
        swapSeatStripsForSwitch(this.seatViews);
        markRoles(this.seatViews);
        redrawBoards(this);
    }

    sendMove = (b: GameControllerBughouse, move: string) => {
        console.log(b, move);
        // Nothing about offers here any more. Playing on still answers them — a move
        // declines the other team's draw and cancels this team's pending resignation —
        // but the SERVER does it, on the move it receives, and broadcasts the result. That
        // holds however the move arrived and leaves all four windows agreeing, where a
        // client deciding for itself left each of them guessing. See
        // cancel_team_offers_on_move() in server/bug/utils_bug.py.


        //moveColor is "my color" on that board
        const moveColor = this.seats.myColor(b.boardName as BugBoardName) === 'black' ? 'black' : 'white';
        const movedClock = this.seats.byBoardAndColor(b.boardName as BugBoardName, moveColor).clock!;

        // A premove is dispatched the instant the opponent's move lands, so the player is
        // charged nothing for it. Clock.duration is frozen while the clock runs, so before
        // pausing it still holds the time this turn started with; capture that plus the
        // increment and restore it afterwards, since pause() would otherwise deduct the
        // dispatch latency. setTime() also repaints, so what is shown matches what is sent.
        const increment = this.inc > 0 ? this.inc * 1000 : 0;
        const premoveTime = b.preaction ? movedClock.duration + increment : undefined;
        movedClock.pause(true);
        if (premoveTime !== undefined) movedClock.setTime(premoveTime);

        // all those values are generally ignored on the server except the one for the current move which is
        // communicated to the other players and recorded in the server move history
        //
        // DEPRECATED: three of these four are noise and must not be used. `duration` on a RUNNING
        // clock is its value at the last start, not what is on screen, so the seat thinking on the
        // other board is reported as it was when its turn began — 447s stale in one measured case,
        // and worse across a disconnect. Only the mover's own clock (paused just above) is real.
        // This should shrink to that ONE number; analysis derives the other three from the mover
        // values alone (`analysisClock.reconstructMainlineClocks`). Do not "fix" these by sending
        // the rendered value instead: an observation by a client of a seat it does not own is still
        // unreliable, and keeping the field invites new readers.
        const msgClocks = [
            this.seats.byBoardAndColor('a', 'white').clock!.duration,
            this.seats.byBoardAndColor('a', 'black').clock!.duration,
        ];
        const msgClocksB = [
            this.seats.byBoardAndColor('b', 'white').clock!.duration,
            this.seats.byBoardAndColor('b', 'black').clock!.duration,
        ];

        const moveMsg = {
            type: 'move',
            gameId: this.gameId,
            move: move,
            clocks: msgClocks,
            clocksB: msgClocksB,
            // THE GAME'S NEXT PLY, not the reader's cursor. `movelistView.ply()` is where the
            // list is pointing — `goPly()` moves it — and `steps.length` is how many plies we hold, so
            // the next one is `steps.length`. They agree only while the reader stays at the end,
            // and a move cannot be made from a scrolled-back position anyway, so this was never
            // observed wrong; it was still asking the wrong object, and one rollback left the
            // cursor stale enough to send a wrong number.
            ply: this.steps.length,
            board: b.boardName,
        } as MsgMove;

        // Both records, written in one place: the durable one so the move survives this page, and
        // the live one so this board stops inviting moves until the server answers.
        this.reconnect.moveSent(moveMsg);

        this.socket.doSend(moveMsg as JSONObject);
        this.seats
            .byBoardAndColor(b.boardName as BugBoardName, moveColor === 'white' ? 'black' : 'white')
            .clock!.start();
    };

    // Is this username on the viewer's own team? That is the whole of what the two offer
    // states turn on: an offer made by my team is one I am waiting on, an offer made by
    // theirs is one I may answer.
    private onMyTeam = (username: string): boolean =>
        this.seats.myTeam().seats.some(seat => seat.player.username === username);

    // ONE PRESS OFFERS. No confirmation: an offer decides nothing, the opponents may
    // decline it simply by playing on, and asking the same person the same question twice
    // is what this page is getting rid of. The button's own state is the feedback.
    //
    // No local state change either — the server broadcasts the offer back to all four
    // players including this one, and letting that one message paint every window keeps
    // the four of them from disagreeing about who is waiting on whom.
    private draw = () => {
        this.socket.doSend({ type: 'draw', gameId: this.gameId });
    };
    //
    // Accepting sends the same message; the server knows it is an acceptance because it
    // comes from the team that did not offer. Deliberately a separate method from draw()
    // all the same, so neither can grow a step that belongs to the other.
    private acceptDraw = () => {
        this.socket.doSend({ type: 'draw', gameId: this.gameId });
    };

    //
    // ONE PRESS ASKS. This no longer ends the game: the server records it and asks this
    // player's partner, whose own resign control turns red. The confirmation that used to
    // be a modal is now a second person, which is a better guard for a decision that ends
    // the game for both of them.
    //
    // The same message serves for confirming, and the server decides which it is — see
    // handle_resign_request_bughouse(). The client is deliberately not told there are two
    // steps, so it cannot get them out of order.
    private resign = () => {
        this.socket.doSend({ type: 'resign', gameId: this.gameId });
    };

    private notifyMsg = (msg: string) => {
        if (this.isGameOver()) return;

        // todo: assumes the viewer plays board A — for a board-B player this names the wrong opponent (preserved quirk)
        const wplayerA = this.seats.byBoardAndColor('a', 'white').player.username;
        const bplayerA = this.seats.byBoardAndColor('a', 'black').player.username;
        const opp_name = this.username === wplayerA ? bplayerA : wplayerA;
        const logoUrl = `${this.home}/static/favicon/android-icon-192x192.png`;
        notify('pychess.org', { body: `${opp_name}\n${msg}`, icon: logoUrl });
    };

    onMsgGameStart = (msg: MsgGameStart) => {
        // console.log("got gameStart msg:", msg);
        if (msg.gameId !== this.gameId) return;
        if (!this.spectator) {
            sound.genericNotify();
            if (!this.focus) this.notifyMsg('joined the game.');
        }
    };
    //
    onMsgNewGame = (msg: MsgNewGame) => {
        window.location.assign(this.home + '/' + msg['gameId']);
    };

    onMsgViewRematch = (msg: MsgViewRematch) => {
        this.controlsView.setViewRematch(() => window.location.assign(this.home + '/' + msg['gameId']));
    };
    //
    private rematch = () => {
        this.socket.doSend({ type: 'rematch', gameId: this.gameId, handicap: this.handicap });
        this.controlsView.setRematchOffer('offering');
    };
    //
    // Accepting is offering in return — the server pairs the two — so this sends the
    // same message and leaves the button showing an offer outstanding until the new
    // game arrives as a VIEW REMATCH link.
    private acceptRematch = () => {
        this.socket.doSend({ type: 'rematch', gameId: this.gameId, handicap: this.handicap });
        this.controlsView.setRematchOffer('offering');
    };
    //
    // Withdrawing MY OWN offer. `reject_rematch` now means exactly this in bughouse —
    // there is no decline control any more, because declining a rematch is not pressing
    // accept. The server clears this player from the offer set and tells everyone, so
    // the withdrawal also stops counting towards the all-four total.
    private cancelRematch = () => {
        this.socket.doSend({ type: 'reject_rematch', gameId: this.gameId });
    };
    //
    private newOpponent = (home: string) => {
        this.socket.doSend({ type: 'leave', gameId: this.gameId });
        window.location.assign(home);
    };
    //
    private analysis = (home: string) => {
        window.location.assign(home + '/' + this.gameId + '?ply=' + this.movelistView.ply().toString());
    };

    // THE RESULT, in words, as a chat line — how the game ended and who won it.
    //
    // The movelist already shows this, but only to whoever is looking at the Moves tab,
    // and the tab that is open by default is Chat. So the one place every player is
    // certainly looking said nothing about the result and went straight to housekeeping
    // about who can now read what.
    //
    // Emitted before those notices, and once: gameOver() can run twice, from the board
    // message and from gameEnd, which is the same reason updateResult() guards itself.
    private resultAnnounced = false;
    private announceResult = () => {
        if (this.resultAnnounced || this.status < 0) return;
        this.resultAnnounced = true;
        const teams = this.seats.teams;
        // `result()` already composes the whole sentence — the reason, then " • X won" or
        // " • Draw" — which is exactly what this line needs to say. It is reused rather
        // than rebuilt so the chat and the movelist can never word the same result
        // differently, and so a new ending only has to be described in one place.
        //
        // Composing it here was tried and was wrong twice over: it duplicated the winner
        // that result() already names, and `_()` in this codebase substitutes only ONE
        // placeholder — `i18n.gettext(msgid, vars)` receives the vars ARRAY, so a second
        // `%2` came out as the literal `undefined` and `%1` as the array joined by a
        // comma. One placeholder per string is the rule here.
        // PREFIXED, because `result()` alone is not always a sentence. For a resignation
        // it reads "A+B resigned • C+D won", which is unmistakable; for a draw it is the
        // single word "Draw", which lands in a column of chat lines and reads as somebody
        // having typed it. The prefix makes every ending announce itself as an ending.
        //
        // Concatenated rather than interpolated: `_()` here substitutes ONE placeholder,
        // because `i18n.gettext(msgid, vars)` takes the vars as an array — a second `%2`
        // comes out as the literal `undefined`.
        const reason = result(this.boardA.variant, this.status, this.result, teams[0].name(), teams[1].name());
        chatMessage('', `${_('Game over')} — ${reason}`, 'bugroundchat');
    };

    private gameOver = () => {
        this.announceResult();
        this.updateBoardSummaryStatus();
        markGameOver();
        this.controlsView.renderGameOverControls(
            this.spectator,
            () => this.rematch(),
            () => this.acceptRematch(),
            () => this.cancelRematch(),
            () => this.newOpponent(this.home),
            () => this.analysis(this.home),
        );
    };

    checkStatus = (msg: MsgBoard | MsgGameEnd) => {
        console.log(msg);
        if (msg.gameId !== this.gameId) return;
        if (this.isGameOver(msg.status)) {
            // game over
            this.status = msg.status;
            this.result = msg.result;
            this.seats.all.forEach(s => s.clock!.pause(false));

            // Nothing can be resent into a finished game, so whatever is still cached for it is
            // dead — including an entry the server deduplicated silently. This is what bounds the
            // cache: every game ends, and every game's key goes when it does.
            this.reconnect.gameEnded();
            // this.dests = new Map();

            if (this.result !== '*' && !this.spectator && !this.finishedGame) {
                sound.gameEndSoundBughouse(msg.result, this.seats.myTeam().teamNumber);
            }
            this.movelistView.selectMove(this, this.steps.length - 1); // show final position (also important to disable cg's movable)
            this.movelistView.renderResult(this);
            this.gameOver();

            // clean up gating/promotion widget left over the ground while game ended by time out
            clearExtensionChoice();

            if (this.tv) {
                setInterval(() => {
                    this.socket.doSend({ type: 'updateTV', gameId: this.gameId, profileId: this.profileid });
                }, 2000);
            }

            // The game is over, so a draw offer outstanding across the result has
            // nothing left to answer. The rematch offer is NOT reset here: this is the
            // moment it becomes possible, and gameOver() above has just drawn the
            // button that carries it.
            this.controlsView.setDrawOffer('rest');
        }
    };

    onMsgUpdateTV = (msg: MsgUpdateTV) => {
        console.log(msg); // todo: tv for bug not supported
    };

    private updateSteps = (full: boolean, steps: Step[], ply: number, follow: boolean) => {
        if (full) {
            // all steps in one message
            this.steps = [];
            this.plyA = 0;
            this.plyB = 0;
            resetChat();
            // THE RESULT ANNOUNCEMENT LIVES IN THE CHAT, AND resetChat() HAS JUST REMOVED IT.
            //
            // A game that ends while we are watching arrives as TWO messages — `gameEnd`, which
            // announces the result, and then a full board message, which lands here and rebuilds
            // the chat from the steps. The announcement was posted by the first and erased by the
            // second, and `resultAnnounced` then stopped it ever being posted again: every player
            // present at the end saw "0-1" and no word of how it happened, while anyone who
            // reloaded saw the sentence, because a reload runs these two in the other order.
            //
            // Clearing the flag lets the rebuild re-announce into the fresh chat, below.
            this.resultAnnounced = false;
            resetMovelistDom();
            replayingChat('bugroundchat');

            steps.forEach((step, idx) => {
                if (idx === 0) {
                    chatMessage('', 'Messages visible to all 4 players for the first 4 moves', 'bugroundchat');
                }
                this.stampStepPlys(step, idx);
                if (idx === 4) {
                    chatMessage('', 'Chat visible only to your partner', 'bugroundchat');
                }
                if (step.chat) {
                    step.chat.forEach(c => {
                        const myTeam = this.seats.myTeam();
                        // while the game is on, a partner's messages are filtered
                        if (!this.isGameOver()) {
                            if (
                                c.username === myTeam.seats[0].player.username ||
                                c.username === myTeam.seats[1].player.username
                            ) {
                                chatMessageBug(idx, this, c);
                            }
                        } else {
                            chatMessageBug(idx, this, c);
                        }
                    });
                }
                if (idx === steps.length - 1 && this.isGameOver()) {
                    // Before the housekeeping notice, which is the order this was always meant to
                    // have: how the game ended, then who may now read what.
                    this.announceResult();
                    chatMessage(
                        '',
                        'Game over. All messages visible to all.',
                        'bugroundchat',
                    );
                }
            });
            this.movelistView.render(this, true, true, false);
        } else {
            // single step message
            if (ply === this.steps.length) {
                if (ply === 0) {
                    chatMessage('', 'Messages visible to all 4 players for the first 4 moves', 'bugroundchat');
                }
                this.stampStepPlys(steps[0], ply);
                const full = false;
                // A PLAYER'S LIST ALWAYS ACTIVATES; a spectator's follows only when their view is
                // following the game. Same `follow` the boards use, so the list and the boards
                // cannot disagree about whether this message was applied.
                const activate = !this.spectator || follow;
                const result = false;
                this.movelistView.render(this, full, activate, result);
                if (this.steps.length === 5) {
                    chatMessage('', 'Chat visible only to your partner', 'bugroundchat');
                }
            }
        }
    };

    private updateBoardsAndClocksSpectors = (
        board: GameControllerBughouse,
        fen: cg.FEN,
        fenPartner: cg.FEN,
        lastStepA: Step,
        lastStepB: Step,
        msgClocks: Clocks,
        /** Should the spectator's boards follow this message? TWO CONDITIONS, decided by the
         *  caller: the message is one this view should apply (a whole snapshot, or the very next
         *  move), AND the spectator has not scrolled away. The player path has required both since
         *  the render gate was split; this one asked only the first, in the looser form
         *  `latestPly`, so a spectator examining an earlier ply was dragged forward by every
         *  arriving move — scenario R3. */
        follow: boolean,
        status: number,
        check: boolean,
    ) => {
        console.log(
            'updateBoardsAndClocksSpectors',
            board,
            fen,
            fenPartner,
            lastStepA,
            lastStepB,
            msgClocks,
            follow,
            status,
            check,
        );

        if (!this.spectator) {
            clearAbortIndicator();
        }
        const step = board.boardName === 'a' ? lastStepA : lastStepB;
        const stepPartner = board.boardName === 'b' ? lastStepA : lastStepB;
        const msgTurnColor = getTurnColor(fen); //step.turnColor; // whose turn it is after this move

        // todo: same clock logic also in updateSingleBoardAndClocks - move to reusable method.
        // important we update only the board where the single move happened, the other clock values do not include the
        // time passed since last move on that board, but contain what is last recorded on the server for that board,
        // while the clock values for this move contain what the user making the moves has in their browser, which we
        // consider most accurate

        this.updateClocks(board.boardName, msgTurnColor, msgClocks, this.status);

        //when message is for opp's move, meaning turnColor is my color - it is now my turn after this message
        if (follow) {
            const move = step == undefined ? undefined : board.boardName == 'a' ? step.move : step.moveB;
            const lastMove = uci2LastMove(move);
            let capture = false;
            if (move) {
                // const capture = !!lastMove && ((board.chessground.state.boardState.pieces.get(lastMove[1] as cg.Key) && step.san?.slice(0, 2) !== 'O-') || (step.san?.slice(1, 2) === 'x'));
                capture = board.ffishBoard.isCapture(move);
            }
            if (lastMove) {
                if (!this.finishedGame) sound.moveSound(this.variant, capture);
            }
            if (check && !this.finishedGame) {
                sound.check();
            }

            board.setState(fen, msgTurnColor, lastMove);
            board.renderState();

            // because pocket might have changed. todo: condition it on if(capture) maybe
            const movePartner =
                stepPartner == undefined
                    ? undefined
                    : board.partnerCC.boardName == 'a'
                      ? stepPartner.move
                      : stepPartner.moveB;
            board.partnerCC.setState(fenPartner, board.partnerCC.turnColor, uci2LastMove(movePartner));
            board.partnerCC.renderState();
        }
    };

    private updateBothBoardsAndClocksOnFullBoardMsg = (
        lastStepA: Step,
        lastStepB: Step,
        fenA: cg.FEN,
        fenB: cg.FEN,
        clocksA: Clocks,
        clocksB: Clocks,
    ) => {
        console.log('updateBothBoardsAndClocksOnFullBoardMsg', lastStepA, lastStepB, clocksA, clocksB);

        // A BOARD WE ARE STILL AHEAD OF MUST NOT INVITE A MOVE.
        //
        // The snapshot has just been applied in full — the player sees the server's truth, nothing
        // is hidden. But a snapshot that predates our own move hands the board back to us with the
        // turn the server may already have passed. Anything that moves from there — a premove
        // releasing itself, or the player, who has just watched their move vanish and may simply
        // play it again — puts a SECOND move in flight for the same ply, and the resend cache holds
        // one entry per board, so the second silently overwrites the only record of the first.
        //
        // NOTHING IS APPLIED HERE ANY MORE. The board asks `movesAllowed()` — wired to this
        // controller in the constructor — whenever it computes its destinations, so the refusal
        // holds for every recompute rather than for the one that used to follow this line.
        // Blanking the map here was a one-shot overwrite at one of the four places that write
        // dests; `goPly()` recomputes them whenever the reader returns to the last ply, so pressing
        // left then right handed a shut board straight back. Scenario R1.

        this.boardA.setState(fenA, getTurnColor(fenA), uci2LastMove(lastStepA?.move));
        this.boardA.renderState();
        this.boardB.setState(fenB, getTurnColor(fenB), uci2LastMove(lastStepB?.moveB));
        this.boardB.renderState();

        /* ONE CONSULTATION, TWO QUESTIONS: has our move been overtaken by this history, and may
           each board be played on afterwards? Both are per board and both were decided here in
           pieces before. The controller is given the whole HISTORY of each board rather than its
           last move, which is what lets it recognise our move under the opponent's reply. */
        const decision = this.reconnect.snapshot(
            {
                a: this.steps.filter(step => step.boardName === 'a').map(step => step.move!),
                b: this.steps.filter(step => step.boardName === 'b').map(step => step.moveB!),
            },
            // Can a move we are still holding actually be played in the position that has just
            // arrived? Answered here because this is where the boards are; the controller has none.
            //
            // ASKED AFTER THE BOARDS ARE SET, AND THAT IS THE WHOLE POINT. `setState()` puts the
            // arriving position into ffish, so this reads the position the SERVER just sent. Until
            // 2026-09-07 the consultation ran at the top of this method, before the repaint, so it
            // read the position we already held — and a round-page move is never pushed to ffish
            // (only the analysis page calls `playMove()`), so ffish sat at the position the move
            // was GENERATED from, where it is legal by construction. The answer was therefore
            // always "yes", whatever the server had just said.
            //
            // What that cost: branch 1.2.3.4. The server refuses a move, hands back its position
            // and waits; the tree says 1.2.2 then drops the move. It could not — the check could
            // not see the refusal — so the move stayed pending and the board stayed shut. And the
            // refusal arrives on an OPEN socket, so no reconnection follows and nothing resends it:
            // the move sat on the reader's board, their clock stopped, while the server waited for
            // a move it had already thrown away.
            //
            // With the order right, a move that cannot be played is dropped rather than sent again
            // for ever, and 1.2.3.4 heals itself the way the tree says it does: the move goes, the
            // board reopens, and the reader can play again.
            (board, move) => {
                const ground = board === 'a' ? this.boardA : this.boardB;
                return ground.ffishBoard.legalMoves().split(' ').includes(move);
            },
            // Whose turn the arriving position leaves it — the other fact the controller cannot
            // hold, and the one that decides whether an armed premove goes now. Read after the
            // repaint for the same reason the legality question is: this must describe the
            // position the server just sent.
            board => (board === 'a' ? this.boardA : this.boardB).turnColor === this.seats.myColor(board),
        );

        // BRANCH 1.1.4 — the server has sent us a position older than one it had already shown us,
        // which means a move it acknowledged did not survive. Nothing here can undo that: the move
        // is gone and this position is the only truth left. What this must not be is silent, so it
        // is said once per board, loudly, and named by its branch.
        for (const board of ['a', 'b'] as BugBoardName[]) {
            if (decision[board].rolledBack) {
                console.warn(
                    `[reconnect] 1.1.4 board ${board}: the server's position went BACKWARDS — ` +
                        `a move we had already been shown is missing from it. ${decision[board].because}`,
                );
            }
        }

        /* THE GATE HAS JUST MOVED, SO THE DESTINATIONS ARE STALE — recompute them.
         *
         * `setState()` above calls `setDests()`, and it ran BEFORE the consultation: at that moment
         * a move of ours could still be pending, `movesAllowed()` was false, and the map was set
         * empty. `reconcile()` then cleared that move (1.2.1) and opened the board — but nothing
         * recomputed what it may play, so the board came back open and destless.
         *
         * WHAT THAT COST, and it is not only cosmetic: chessground's `playPremove` asks
         * `canMove()`, which reads `movable.dests`. An armed premove therefore could not fire after
         * a reconnection that cleared a pending move — and `playPremove` discards the premove
         * whether or not it plays it, so the move was not delayed, it was LOST. Scenario N9, with
         * the premove armed behind a move the server had not yet acknowledged.
         *
         * The same ordering trap as 1.2.2's legality check twenty lines up: both read a gate the
         * consultation is about to move. */
        this.boardA.setDests();
        this.boardB.setDests();

        // BRANCH 1.2.3 — PUT OUR OWN UNCONFIRMED MOVE BACK ON TOP. See `BoardDecision.replay`.
        // After the repaint, necessarily: `setState()` has just reset ffish to the server's
        // position, so a replay pushed earlier would be thrown away by the very repaint it must
        // survive. And after the consultation, which is what decided there is anything to replay.
        this.replayPendingMove('a', decision.a.replay);
        this.replayPendingMove('b', decision.b.replay);

        // ALL FOUR, OR NONE, AND THE DECISION SAYS WHICH — task 1.2, decided with 1.1. This was
        // `if (!this.isGameOver())`: the rule that a whole-game position replaces every clock was
        // applied here and stated nowhere, which is what the task was about. `takeAllClocks` is
        // the same answer from the object that owns the branch, and `checkStatus()` has already
        // stopped all four by the time a finished game reaches here.
        if (decision.takeAllClocks) {
            this.updateClocks('a', this.boardA.turnColor, clocksA, this.status);
            this.updateClocks('b', this.boardB.turnColor, clocksB, this.status);
        } else {
            // // TODO: this logic differs than single board games and lichess - not sure if to preserve+improve or remove
            // //       for finished games they dont update clocks according to move times of last moves and here i do
            // if (lastStepA) {
            //     this.updateClocks("a", this.b1.turnColor, lastStepA.clocks!, this.status);
            // }
            // if (lastStepB) {
            //     this.updateClocks("b", this.b2.turnColor, lastStepB.clocks!, this.status);
            // }
        }

        // THE RULE IS THE DECISION'S NOW, not this call site's. It used to be spelled out here as
        // `playable && premove && turnColor === myColor`, which put half of branch 1's premove rule
        // in the caller and left it beyond the reach of any test — the same split that still holds
        // for the clocks. `releasePremove` is the whole answer; all that is left here is whether a
        // premove exists to release.
        //
        // THE POSITION'S OWN TURN CANNOT ANSWER IT ALONE, which is why the decision AND-s the two:
        // a position that predates our own move says "your turn" quite truthfully, and only the
        // controller knows we are still waiting on something.
        if (decision.a.releasePremove && this.boardA.premove) this.boardA.performPremove();
        if (decision.b.releasePremove && this.boardB.premove) this.boardB.performPremove();
    };

    /** Show a move of ours again that the snapshot could not carry — branch 1.2.3's `replay`.
     *
     *  THIS REPRODUCES THE OPTIMISTIC STATE; IT DOES NOT RECOMPUTE THE POSITION. On the round page a
     *  move the reader makes advances CHESSGROUND ONLY: `onUserMove` runs `processInput` ->
     *  `doSendMove` -> `sendMove`, and none of them touches ffish. So between a move and its
     *  confirmation the board is deliberately mixed — the piece has moved on screen, while ffish,
     *  `turnColor`, `lastmove` and the clocks all still say it is our turn, because as far as the
     *  server knows it is. That mixture IS the state a reader had before the connection broke, and
     *  it is the state this restores.
     *
     *  WHICH IS WHY `pushMove()` IS NOT USED. It advances ffish and with it `turnColor`, and
     *  `updateClocks()` reads `turnColor` a few lines below: the client would start the OPPONENT's
     *  clock while the server still has us on the clock and our time running. It would also feed
     *  the 1.2.2 legality check a position the server has never seen, undoing the ordering this
     *  method now depends on.
     *
     *  LOCAL ONLY. Nothing is sent: the resend belongs to the reconnect payload and has already
     *  been arranged. The move list is left alone too — `steps` is the server's record and this
     *  move is not in it, which is exactly where an unconfirmed move has always stood.
     */
    private replayPendingMove = (boardName: BugBoardName, move: string | undefined) => {
        if (move === undefined) return;
        const board = boardName === 'a' ? this.boardA : this.boardB;
        const dest = move.slice(-2) as cg.Key;

        // A DROP TAKES NOTHING AND COMES OUT OF OUR OWN POCKET. `P@e4` has no origin square, so it
        // is placed rather than moved, and the pocket the snapshot just restored has to give the
        // piece back up again.
        const at = move.indexOf('@');
        if (at >= 0) {
            const piece = { role: util.roleOf(move.slice(0, at) as cg.Letter), color: board.turnColor } as cg.Piece;
            board.chessground.newPiece(piece, dest, true);
            return;
        }

        // What this capture removes, read BEFORE the piece is moved over it.
        const captured = board.chessground.state.boardState.pieces.get(dest);
        board.chessground.move(move.slice(0, 2) as cg.Orig, dest);
        if (captured) board.feedPartnerPocket(captured);
    };

    private updateSingleBoardAndClocks = (
        board: GameControllerBughouse,
        fen: cg.FEN,
        fenPartner: cg.FEN,
        /** THE STEP THIS MESSAGE CARRIES — one, and not a pair drawn from `this.steps`. Every
         *  fact about the move that just happened comes from here: an 'older' or 'ahead' message
         *  is never pushed into `this.steps`, so the page's own last step would describe another
         *  ply — another turn colour, another mover, another move.
         *
         *  It carries BOTH boards' fens, so one step is enough for the position and the pocket.
         *  It does NOT carry the partner board's last move — see `lastMovePartner` below, the one
         *  thing still read from the page's history. */
        step: Step,
        msgClocks: Clocks,
        place: MovePlace,
        status: number,
        check: boolean,
        readerAtEnd: boolean,
    ) => {
        console.log('updateSingleBoardAndClocks', board, fen, fenPartner, step, msgClocks, place, status, check);

        const msgTurnColor = step.turnColor; // whose turn it is after this move
        const msgMoveColor = msgTurnColor === 'white' ? 'black' : 'white'; // which color made the move
        const myMove = this.seats.myColor(board.boardName as BugBoardName) === msgMoveColor; // the received move was made by me

        const move = board.boardName === 'a' ? step.move : step.moveB;
        const lastMove = uci2LastMove(move);
        /* THE PARTNER BOARD'S LAST MOVE IS THE ONE FACT THIS MESSAGE DOES NOT CARRY, so it alone
         * is read from `this.steps` rather than from the step above.
         *
         * A LIVE step fills only the board its move happened on — `move_a = move if board == "a"
         * else ""` in `game_bug.py` — while the LOADER fills both boards' last moves into every
         * step (`utils_bug.py`). Taking the partner's move off an arriving single move therefore
         * reads `""`, and `setState` in the branch below would clear the other board's highlight.
         * Measured 2026-09-12 in the harness: a board-a move blanked the partner board's
         * last-move highlight in the window that was not playing on board a.
         *
         * The last step ON THE PARTNER BOARD is where that move lives, and it is still the page's
         * own history that holds it — the same source the pocket splice below reads. */
        const partnerStep = this.steps[this.steps.findLastIndex(s => s.boardName === board.partnerCC.boardName)];
        const lastMovePartner = partnerStep
            ? uci2LastMove(board.partnerCC.boardName === 'a' ? partnerStep.move : partnerStep.moveB)
            : undefined;

        let capture = false;
        if (move) {
            //const capture = !!lastMove && ((board.chessground.state.boardState.pieces.get(lastMove[1] as cg.Key) && step.san?.slice(0, 2) !== 'O-') || (step.san?.slice(1, 2) === 'x'));
            capture = board.ffishBoard.isCapture(move);
        }

        if (lastMove && !myMove) {
            if (!this.finishedGame) sound.moveSound(this.variant, capture);
        }
        if (check && !this.finishedGame) {
            sound.check();
        }

        /* BRANCH 2 — one move has arrived. ONE CONSULTATION, FOUR ANSWERS.
         *
         * This used to be two inline branches: `if (!myMove)` decided 2.1 here and never told the
         * controller anything, while the `else` asked it about 2.2. The controller therefore never
         * learned of a move it had not made — which is why branch 1.1.4 could not notice a rollback
         * that lost only somebody else's move. See `case-to-code.md`, finding 1.
         */
        const decision = this.reconnect.moveArrived(board.boardName as BugBoardName, move, myMove, place);

        // 2.1.3 — a move is missing between what we are showing and what just arrived. Nothing here
        // can ask for it; a full position is what fills a hole and the next one will. What must not
        // happen is passing over it in silence, which is what the old boolean did.
        if (decision.movesMissing) {
            console.warn(
                `[reconnect] board ${board.boardName}: ${decision.because}. ` +
                    `Showing ply ${this.movelistView.ply()}, message carries a later one.`,
            );
        }

        // ONE FIELD, ONE RULE — task 1.1, decided 2026-09-12. This site used to OR in "and this
        // seat's clock is still running", the caller's half of a split clock rule. The controller
        // owns the whole of it now: `this.ahead` already recorded whether THIS page sent the move,
        // which is the fact the running check was standing in for, and a truer form of it —
        // `updateClocks()` below flips `Clock.running` itself, so the old test went true for
        // reasons that had nothing to do with who sent what.
        if (decision.takeClocks) {
            // Only the board this move happened on. The other board's values in this message are
            // the mover's stale view of clocks they do not own — see `game_bug_clocks.update_clocks`.
            this.updateClocks(board.boardName, msgTurnColor, msgClocks, this.status);
        }

        /* THE CONTROLLER SAYS WHETHER THIS POSITION IS THE GAME'S TRUTH; THE VIEW SAYS WHETHER IT
         * IS WHAT THE READER IS LOOKING AT. Both must agree before the boards move. A reader who
         * has scrolled back keeps the position they chose — the move still reaches the move list
         * and the clocks, it simply is not painted over them.
         *
         * The clocks are deliberately NOT gated: they are the game's, not the view's, and a reader
         * examining an earlier ply still wants to see time running now. */
        if (decision.applyPosition && readerAtEnd) {
            board.setState(fen, board.turnColor === 'white' ? 'black' : 'white', lastMove);
            board.renderState();

            // THE POCKET IS REPAIRED DIFFERENTLY DEPENDING ON WHOSE MOVE THIS IS, and the two are
            // not interchangeable. For somebody else's move only the POCKETS of the partner board
            // are taken, spliced into the position we already hold: their message is authoritative
            // about what their capture put in our hand, and not about where the pieces on that
            // board stand. For our own move the partner position is taken whole, because it is the
            // one our move just produced.
            if (myMove) {
                board.partnerCC.setState(fenPartner, board.partnerCC.turnColor, board.partnerCC.lastmove);
            } else {
                const messageFenPartnerSplit = fenPartner.split(/\[|\]/);
                const currentFenPartnerSplit = board.partnerCC.fullfen.split(/\[|\]/);
                const newFen =
                    currentFenPartnerSplit[0] + '[' + messageFenPartnerSplit[1] + ']' + currentFenPartnerSplit[2];
                board.partnerCC.setState(newFen, board.partnerCC.turnColor, lastMovePartner);
            }
            board.partnerCC.renderState();

            if (!myMove && !this.focus) this.notifyMsg(`Played ${step.san}\nYour turn.`);
        }

        /* A PREMOVE IS RELEASED INTO THE LIVE POSITION, SO THE READER IS RETURNED TO IT FIRST.
         *
         * The reader may have armed a premove and then scrolled back to look at the game while they
         * wait, which is an ordinary thing to do — especially here, where the other board is worth
         * watching. Nothing about scrolling withdraws the intention, and the premove survives it:
         * a fen change does not touch `premovable.current`.
         *
         * WHAT WENT WRONG WITHOUT THIS, and it was a lost move rather than a stray one.
         * `renderPly` clears `movable.color`/`dests` for a reader who is not at the end, and the
         * boards are not repainted under them either. `playPremove` then asks `canMove()`, which
         * needs both — so it played nothing, and `unsetPremove()` runs OUTSIDE that `if` and
         * discarded the premove regardless. The reader was left with no premove, nothing sent, and
         * their clock running while they believed they had already moved.
         *
         * SNAPPING THEM FORWARD IS NOT THE YANK R2 AND R3 GUARD AGAINST. Those protect a reader who
         * is NOT trying to move, from having the board repainted under them by somebody else's
         * move. Arming a premove is the opposite: an explicit statement that you intend to move as
         * soon as it is your turn, so arriving at the live position when that happens is the thing
         * asked for.
         *
         * Only when a premove is actually armed — a reader browsing without one is left alone. */
        if (decision.releasePremove && board.premove) {
            if (!this.movelistView.isAtEnd(this)) this.movelistView.selectMove(this, this.steps.length - 1);
            board.performPremove();
        }
    };

    onMsgBoard = (msg: MsgBoard) => {
        console.log(msg);
        if (msg.gameId !== this.gameId) return;
        msg = materializeTwoBoardHistory(msg, this.boardA.ffish);


        /* IS THIS THE WHOLE GAME, OR ONE MOVE? ASKED OF THE MESSAGE, NOT OF OUR OWN HISTORY.
         *
         * The server answers it precisely, if you read what it sends: `get_board(full=True)` puts
         * `self.steps` in the message — the initial position plus one step per move — and
         * `get_board()` puts exactly one. So a whole-game message always carries `ply + 1` steps.
         *
         * `steps.length > 1` was a heuristic for that, with one hole: a game with NO MOVES YET has
         * a whole-game message of a single step, so it read as a single move. `isInitialBoardMessage`
         * — `ctrl.ply === undefined` — existed to patch that hole, and cost more than it fixed: the
         * cursor, declared `ply: number`, had to be undefined until the first message arrived, so
         * the field carried a third meaning ("have we loaded?") on top of "where the reader is
         * looking", and could not move to the move list while that was true. It has since moved:
         * the cursor is `MovelistView`'s private field.
         *
         * The ambiguous case cannot occur: a single-move broadcast follows a move, so its ply is at
         * least 1, and it can never look like the empty game's snapshot.
         *
         * One behaviour changes, and it is a correction. If the FIRST message this page sees is a
         * single move — a broadcast landing between the socket opening and the snapshot being sent
         * — it used to be treated as the whole game and rendered from its one step. Now it is a
         * move further ahead than the nothing we hold: branch 2.1.3, not applied, and the snapshot
         * already on its way is what fills the gap.
         */
        const full = msg.steps.length === msg.ply + 1;

        /* IS THE READER FOLLOWING THE GAME, or looking at something earlier?
         *
         * The VIEW's question, and separate from `place` below, which is the GAME's. The move
         * list holds the cursor and `steps.length - 1` is the last ply we hold; if they differ the
         * reader has scrolled away and nothing may be repainted under them.
         *
         * `latestPly` USED TO LIVE HERE and answered three questions at once: is this the next ply,
         * is a snapshot a rollback, and — before task 2.5 — is the reader following. Its name
         * described only the last. Each reader now takes the one it means: `place` for the game,
         * this for the view, `full` for a snapshot. */
        const readerAtEnd = this.movelistView.isAtEnd(this);

        /* WHERE THIS MOVE SITS RELATIVE TO THE GAME WE HOLD — branch 2.1's three answers.
         *
         * Compared against `steps.length`, which is the ply number the NEXT move will have: `steps`
         * is the initial position plus one per move, so a page holding N moves has N+1 steps and
         * the next move arrives as ply N+1. `updateSteps` decides whether a step is new with the
         * very same test, `if (ply === this.steps.length)`.
         *
         * Read BEFORE `updateSteps` pushes, so it is still the count without this message. */
        const place: MovePlace =
            msg.ply === this.steps.length
                ? 'next'
                : msg.ply > this.steps.length
                  ? 'ahead'
                  : 'older';

        /* WHAT WE ARE SHOWING, WHICH IS NOT THE SAME QUESTION AS WHERE THE MOVE LIST SCROLLS.
         *
         * A FULL MESSAGE ALWAYS WINS, because the branch below applies it unconditionally: both
         * positions, both pockets, all four clocks, the whole move list. Everything the client
         * holds is a copy of something the server can restate, and it has just restated all of it.
         * The one exception is a move of ours waiting to be sent, which the server cannot hand
         * back because it never had it — and that is kept by the reconnect controller, not here.
         *
         * `latestPly` was doing this job and answers a different question: should the move list
         * SCROLL to this ply. For a rolled-back snapshot — a full message whose ply is LOWER than
         * ours, which `bughouse-persist-moves-as-played` made possible — it is correctly false, so
         * a reader is not yanked backwards. But the boards were repainted anyway, and the cursor
         * kept describing a game nobody was looking at any more.
         *
         * What that cost: the NEXT move was compared against the stale number, came out as "older
         * than what we are showing" (branch 2.1.2), and was never rendered — the reader simply did
         * not see it happen. It self-limited, because the move after that matched `ply + 1` again;
         * scenario T8 measures exactly one move lost. It also stamped the wrong ply on our own
         * outgoing moves, `sendMove()` using the cursor rather than `steps.length`.
         */
        if (full) this.movelistView.setCursor(msg.ply);
        else if (readerAtEnd && place === 'next') this.movelistView.setCursor(msg.ply);

        this.result = msg.result;
        this.status = msg.status;

        this.updateSteps(full, msg.steps, msg.ply, full || (place === 'next' && readerAtEnd));
        this.checkStatus(msg);

        if (full) {
            /* A SNAPSHOT'S LAST STEPS COME FROM `this.steps`, WHICH `updateSteps` HAS JUST
             * REBUILT FROM THIS VERY MESSAGE — so these are the message's own steps, and the
             * indirection is harmless here. It is NOT harmless for a single move, which is why
             * the branch below reads the message directly; see the comment there. */
            const lastStep = this.steps[this.steps.length - 1];

            const lastStepA = this.steps[this.steps.findLastIndex(s => s.boardName === 'a')];
            const lastStepB = this.steps[this.steps.findLastIndex(s => s.boardName === 'b')];

            // reconnect after lost ws connection or refresh
            if (this.spectator) {
                this.updateBoardsAndClocksSpectors(
                    this.boardA,
                    lastStep.fen,
                    lastStep.fenB!,
                    lastStepA,
                    lastStepB,
                    msg.clocks!,
                    // A snapshot is a reset of everything the client holds, so it applies whatever
                    // the spectator was looking at — the same rule the player path follows.
                    true,
                    msg.status,
                    msg.check,
                );
                this.updateBoardsAndClocksSpectors(
                    this.boardB,
                    lastStep.fenB!,
                    lastStep.fen,
                    lastStepA,
                    lastStepB,
                    msg.clocksB!,
                    true,
                    msg.status,
                    msg.checkB!,
                );
            } else {
                this.updateBothBoardsAndClocksOnFullBoardMsg(
                    lastStepA,
                    lastStepB,
                    lastStep.fen,
                    lastStep.fenB!,
                    msg.clocks!,
                    msg.clocksB!,
                );
            }
        } else {
            /* THE MESSAGE'S OWN STEP, NOT THE PAGE'S LAST ONE.
             *
             * `updateSteps` pushes a single-move step only when it is the next one — `if (ply ===
             * this.steps.length)`, the very test that produced `place` — so an 'older' or 'ahead'
             * message is never in `this.steps`, and its last entry there describes a DIFFERENT
             * ply: another turn colour, another mover, another move.
             *
             * Nothing is missing by reading the message instead. A single-move board message
             * carries exactly one step (`get_board()` sends `steps[-1]`) and that step carries
             * both boards' fens and both boards' last moves, which is every fact wanted below.
             *
             * WHAT THE INDIRECTION COST. `updateClocks()` is handed `step.turnColor`, and that is
             * what decides WHICH of the two clocks is restarted — so an out-of-order message
             * could start the seat the server does not have on the move, with that board's pair
             * taken from the message all the same. And on a page whose `steps` is still empty —
             * the first message being a broadcast that beat the snapshot, the case the `full`
             * test above describes — `this.steps[-1]` was `undefined` and this threw before any
             * decision was consulted.
             */
            const msgStep = msg.steps[msg.steps.length - 1];
            const boardName = msgStep.boardName as BugBoardName;
            const board = boardName === 'a' ? this.boardA : this.boardB;
            const check = boardName == 'a' ? msg.check : msg.checkB!;
            const clocks = boardName == 'a' ? msg.clocks : msg.clocksB!;
            const fen = boardName == 'a' ? msgStep.fen : msgStep.fenB!;
            const fenPartner = boardName == 'a' ? msgStep.fenB! : msgStep.fen;
            if (this.spectator) {
                // BOTH STEP ARGUMENTS ARE THIS ONE STEP, which is what the pair means here: it
                // holds this board's last move and the partner board's alike. Only the snapshot
                // above has two different steps to give.
                this.updateBoardsAndClocksSpectors(
                    board,
                    fen,
                    fenPartner,
                    msgStep,
                    msgStep,
                    clocks!,
                    place === 'next' && readerAtEnd,
                    msg.status,
                    check,
                );
            } else {
                this.updateSingleBoardAndClocks(
                    board,
                    fen,
                    fenPartner,
                    msgStep,
                    clocks!,
                    place,
                    msg.status,
                    check,
                    readerAtEnd,
                );
            }
        }
    };

    /** One line, delegating to the move list, which owns the selection. See `twoBoardCtrl`. */
    goPly = (ply: number) => this.movelistView.showPly(this, ply);

    renderPly = (ply: number, steppedForward: boolean) => {
        console.log('RoundControllerBughouse.renderPly ' + ply);

        const step = this.steps[ply];
        console.log(step);

        const { board, fen, fenPartner, move, movePartner } = this.goPlyCore(step);

        const capture = this.stepCapture(step, board, move);

        board.partnerCC.setState(fenPartner!, getTurnColor(fenPartner!), movePartner);
        board.partnerCC.renderState();

        board.setState(fen!, getTurnColor(fen!), move);
        board.renderState();

        // The cursor is already on `ply` — `showPly()` sets it before calling this — so "is the
        // ply being rendered the latest one" and "is the reader following" are the same question.
        if (this.isGameOver() || !this.movelistView.isAtEnd(this)) {
            board.chessground.set({ movable: { color: undefined, dests: undefined } });
            board.partnerCC.chessground.set({ movable: { color: undefined, dests: undefined } });
        } else {
            if (this.seats.me('a') !== undefined) {
                this.boardA.setDests();
                this.boardA.chessground.set({ movable: { color: this.seats.myColor('a') } });
            }
            if (this.seats.me('b') !== undefined) {
                this.boardB.setDests();
                this.boardB.chessground.set({ movable: { color: this.seats.myColor('b') } });
            }
        }

        // if (this.status >= 0 && this.ply !== ply) {
        //     //if it is a game that ended, then when scrolling it makes sense to show clocks when the move was made
        //     // however if timeout happened and we receive gameEnd message we don't want to update clocks, we want to see
        //     // the zeros.
        //     // todo:this is a mess. also on lichess and other pychess variants we don't update clocks in round page only in analysis
        //     //      if we decide to preserver and improve this behaviour in round page, at least some refactoring to reduce this complexity
        //     //      of this if and calling goPly on gameEnd just for the sake of setting movable to none - really no other reason
        //     //      to call this on gameEnd.
        //     const whiteAClockAtIdx = this.colors[0] === 'white'? 0: 1;
        //     const blackAClockAtIdx = 1 - whiteAClockAtIdx;
        //     const whiteBClockAtIdx = this.colorsB[0] === 'white'? 0: 1;
        //     const blackBClockAtIdx = 1 - whiteBClockAtIdx;
        //
        //     const lastStepA = this.steps[this.steps.findLastIndex((s, i) => s.boardName === "a" && i <= ply)];
        //     const lastStepB = this.steps[this.steps.findLastIndex((s, i) => s.boardName === "b" && i <= ply)];
        //     if (lastStepA) {
        //         this.clocks[whiteAClockAtIdx].setTime(lastStepA.clocks![WHITE]);
        //         this.clocks[blackAClockAtIdx].setTime(lastStepA.clocks![BLACK]);
        //     } else {
        //         this.clocks[whiteAClockAtIdx].setTime(this.base * 60 * 1000);
        //         this.clocks[blackAClockAtIdx].setTime(this.base * 60 * 1000);
        //     }
        //     if (lastStepB) {
        //         this.clocksB[whiteBClockAtIdx].setTime(lastStepB.clocks![WHITE]);
        //         this.clocksB[blackBClockAtIdx].setTime(lastStepB.clocks![BLACK]);
        //     } else {
        //         this.clocksB[whiteBClockAtIdx].setTime(this.base * 60 * 1000);
        //         this.clocksB[blackBClockAtIdx].setTime(this.base * 60 * 1000);
        //     }
        // }

        // The cursor and this test belong to the move list now — it holds the old value, which is
        // the only thing that can answer "did we step forward by one".
        if (steppedForward) sound.moveSound(board.variant, capture);
    };

    onMsgUserConnected = (msg: MsgUserConnected) => {
        console.log(msg);
        if (!this.spectator) {
            this.setPresence(this.username, true);

            // prevent sending gameStart message when user just reconnecting
            //todo:niki:what is the point of this message - also what if we refresh before moves are made? also what is the point of this whole method at all?
            if (msg.ply === 0) {
                this.socket.doSend({ type: 'ready', gameId: this.gameId });
            }
        }
    };

    onMsgUserPresent = (msg: MsgUserPresent) => {
        console.log(msg);
        this.setPresence(msg.username, true);
    };

    onMsgUserDisconnected = (msg: MsgUserDisconnected) => {
        console.log(msg);
        this.setPresence(msg.username, false);
    };

    onMsgDrawOffer = (msg: MsgDrawOffer) => {
        chatMessage('', msg.message, 'bugroundchat');
        // By TEAM, not by sender. Both members of the offering team wait — including the
        // player who pressed the button, who is simply the one who pressed it — and both
        // members of the other team may answer.
        if (this.spectator) return;
        this.controlsView.setDrawOffer(this.onMyTeam(msg.username) ? 'offering' : 'offered');
    };

    onMsgResignOffer = (msg: MsgResignOffer) => {
        chatMessage('', msg.message, 'bugroundchat');
        if (this.spectator) return;
        // Only ever delivered to the two players on the resigning team, so there is no
        // opposing case to handle here: either this is my own request, or it is my
        // partner's and I am the one who confirms it.
        //
        // The message cannot tell these apart on its own — it goes to the WHOLE team, so the
        // asker receives it too, and showing them a live "Confirm resignation" they are not
        // allowed to press would be a button that lies. Hence the sender test.
        //
        // Unless I am the whole team: in a simul one user holds both seats, so the asker IS the
        // confirmer and `'offering'` would disable the only control that can end the game — the
        // reason a simul could not be resigned at all before 2026-08-30. The second press then
        // does what a partner's press does, and the server agrees (see
        // `handle_resign_request_bughouse`).
        const iAmTheWholeTeam =
            new Set(this.seats.myTeam().seats.map(seat => seat.player.username)).size === 1;
        const mine = msg.username === this.username && !iAmTheWholeTeam;
        this.controlsView.setResignOffer(mine ? 'offering' : 'offered');
    };

    onMsgResignCancelled = (msg: MsgResignCancelled) => {
        chatMessage('', msg.message, 'bugroundchat');
        if (this.spectator) return;
        this.controlsView.setResignOffer('rest');
    };

    onMsgDrawRejected = (msg: MsgDrawRejected) => {
        chatMessage('', msg.message, 'bugroundchat');
        // Load-bearing, not tidying: a button IS the record that an offer is outstanding,
        // so this is the only thing that returns it to rest. Broadcast to all four, so
        // every window clears together rather than each deciding for itself.
        this.controlsView.setDrawOffer('rest');
    };

    onMsgRematchOffer = (msg: MsgRematchOffer) => {
        chatMessage('', msg.message, 'bugroundchat');
        if (this.spectator) return;
        this.controlsView.setRematchOffer(this.rematchStateFrom(msg.offers));
    };

    onMsgRematchRejected = (msg: MsgRematchRejected) => {
        chatMessage('', msg.message, 'bugroundchat');
        if (this.spectator) return;
        this.controlsView.setRematchOffer(this.rematchStateFrom(msg.offers));
    };

    // A rematch is not one player offering and the others answering — it begins when ALL
    // FOUR have signed up, so every press is a sign-up and the only real question is
    // whether THIS player is already in. That is what the server sends, and reading it
    // is what keeps the four controls consistent:
    //
    //   in the list      -> `offering`, and the control withdraws
    //   not in, list set -> `offered`, and the control signs up
    //   list empty       -> `rest`
    //
    // Inferring it from `msg.username` was wrong in both directions. Someone else
    // accepting flipped the original offerer's CANCEL to ACCEPT — offering to accept
    // their own rematch — and a withdrawal reset everybody rather than only the player
    // who withdrew.
    //
    // `offers` is optional because the single-board server does not send it; absent, this
    // falls back to the old all-or-nothing reading rather than throwing.
    private rematchStateFrom = (offers?: string[]): OfferState => {
        if (offers === undefined) return 'rest';
        if (offers.includes(this.username)) return 'offering';
        return offers.length > 0 ? 'offered' : 'rest';
    };

    // private onMsgFullChat = (msg: MsgFullChat) => {
    // To prevent multiplication of messages we have to remove old messages div first
    // patch(document.getElementById('messages') as HTMLElement, h('div#messages-clear'));
    // // then create a new one
    // patch(document.getElementById('messages-clear') as HTMLElement, h('div#messages'));
    // if (this.ply > 4) {
    //     chatMessage("", "Chat visible only to your partner", "bugroundchat");
    // } else {
    //     chatMessage("", "Messages visible to all 4 players for the first 4 moves", "bugroundchat");
    // }
    // msg.lines.forEach((line) => {
    //     if ((this.spectator && line.room === 'spectator') || (!this.spectator && line.room !== 'spectator') || line.user.length === 0) {
    //         chatMessage(line.user, line.message, "bugroundchat", line.time);
    //     }
    // });
    // }

    /* THE WATCHERS, AS THE SERVER COUNTS THEM. `wsr.py` broadcasts `spectator_list` whenever
       anybody joins or leaves a game socket, players included (`full=True`), and it has always
       done so for bughouse — `GameBug.is_player` covers all four seats and `non_bot_players` the
       whole team, so a board-B player is not mistaken for a departing watcher. What was missing
       was anything on this side to receive it: the socket's `case 'spectators'` held a commented
       out call to a method that does not exist on this class, since `onMsgSpectators` is private
       on `GameController` and the two-board controllers extend `TwoBoardController`. */
    onMsgSpectators = (msg: MsgSpectators) => {
        this.spectatorsView.render(msg.spectators);
    };

    onMsgChat = (msg: StepChat) => {
        if (
            this.spectator /*spectators always see everything*/ ||
            (!this.spectator && msg.room !== 'spectator') ||
            msg.username.length === 0
        ) {
            // THE LATEST MOVE, NOT THE CURSOR. This labels an arriving chat message with the move
            // that was on the board when it was said — `chat.ts` reads `ctrl.steps[ply].san` for
            // that. The cursor is where the READER is looking, so a reader scrolled back to move 1
            // had their partner's messages labelled with move 1. Same confusion as R2, one field
            // further along.
            chatMessageBug(this.steps.length - 1, this, msg);
            if (msg.username !== this.username && msg.message.startsWith('!bug!')) {
                sound.bugChatSound(msg.message.replace('!bug!', ''));
            }
        }
    };
}
