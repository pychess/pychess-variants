// TODO: This files contains types related almost entirely only to web socket messages, and ONLY those that are used in more than one different places (.ts files)
//       Other such (message) types which are specific only to single file/page and never re-used in multiple places exist in their corresponding files.
//       Would be good to review the types here and those other types in each specific file (e.g. roundCtrl.ts, analysisCtrl.ts, editorCtrl.ts, tournament.ts, lobby.ts)
//       and see if there is any duplication or the ones that are here should be split or any other improvement that might be needed or better organization can be found
import * as cg from 'chessgroundx/types';

import { BoardName, BugBoardName } from './types';

export type Clocks = [number, number];

export interface Step {
    fen: cg.FEN;
    fenB?: cg.FEN;

    move: string | undefined;
    moveB?: string | undefined;

    check: boolean;
    turnColor: cg.Color;

    san?: string;
    analysis?: Ceval;

    ceval?: Ceval;
    scoreStr?: string;

    sanSAN?: string;

    boardName?: BoardName;

    chat?: StepChat[];

    // Only the entry for this step's mover is reliable; the other three are the mover client's
    // stale view of seats it does not own, kept as diagnostics and slated to be reduced to that
    // one number. Read them through `analysisClock.reconstructMainlineClocks`, never directly.
    clocks?: Clocks;
    clocksB?: Clocks;
    movetime?: number;
    movetimeB?: number;
    plyA?: number;
    plyB?: number;
    ts?: number;
}

export interface StepChat {
    message: string;
    username: string;
    time: number;
    room: string;
}

export interface CrossTable {
    s1: number;
    s2: number;
    r: string[];
    _id: string;
}

export interface MsgGameNotFound {
    gameId: string;
}

export interface MsgShutdown {
    message: string;
}

export interface MsgChat {
    room?: string; // Tournament/simul "lobbychat" messages have no room property; round chat reuses this interface.
    user: string;
    message: string;
    time?: number;
}

export interface MsgFullChat {
    lines: MsgChat[];
}

export interface GameDisplayHistory {
    variant: string;
    chess960: boolean;
    moves: string[];
    showPromoted: boolean;
    countStarted: number;
    usi: boolean;
    clocksWhite?: number[];
    clocksBlack?: number[];
    analysis?: Array<Ceval | null>;
    countIntervals?: Array<[number, number]>;
    jieqiCovered?: Record<string, string>;
}

export interface MsgBoard {
    gameId: string;
    fen: string;
    ply: number;
    positionId?: string;
    lastMove: string;
    bikjang: boolean;
    check: boolean;
    checkB?: boolean;
    by: string;
    status: number;
    pgn: string;
    tp: string;
    uci_usi: string;
    result: string;
    steps: Step[];
    history?: GameDisplayHistory;
    twoBoardHistory?: TwoBoardDisplayHistory;
    berserk: { w: boolean; b: boolean };
    jieqiCaptures?: string[];
    // Per-move captured fake identities for Jieqi; only populated for the viewer during play.
    jieqiCaptureStack?: Array<string | null>;

    byo?: number[];
    clocks?: Clocks; // different than last stp clock - includes correction for the color whose turn it is with elapsed time on server since last move
    clocksB?: Clocks; // different than last stp clock - includes correction for the color whose turn it is with elapsed time on server since last move

    takeback?: boolean;
}

export interface TwoBoardDisplayHistory {
    variant: string;
    chess960: boolean;
    moves: string[];
    boards: BugBoardName[];
    metadata: Array<Pick<Step, 'clocks' | 'clocksB' | 'ts' | 'analysis' | 'chat'>>;
}

export interface Ceval {
    d: number;
    multipv?: number;
    m?: string;
    p?: string;
    s: { cp?: number; mate?: number };
    k?: number;
    // Server-generated move advice. Its variation starts BEFORE the played move;
    // p remains the PV from the evaluated position.
    advice?: { nag: number; comment: string; variation: Step[] };
}

export interface MsgSpectators {
    spectators: string;
}

export interface MsgUserConnected {
    username: string;
    ply?: number; // used only in roundctrl
    firstmovetime?: number; // used only in roundctrl
}

export interface MsgGameEnd {
    /*"type": "gameEnd"*/
    status: number;
    result: string;
    gameId: string;
    pgn: string;
    ct: CrossTable;
    rdiffs: RDiffs;
    jieqiCaptures?: string[];
    jieqiCaptureStack?: Array<string | null>;
}

export interface MsgNewGame {
    gameId: string;
}

export interface RDiffs {
    brdiff: number;
    wrdiff: number;
}

export type MsgMove = {
    // cannot be interface because cannot be converted to an indexed type and JSONObject, which is used in doSend is such
    type: string; //"move"
    gameId: string;
    move: string;
    clocks: Clocks;
    clocksB?: Clocks;
    ply: number;
    positionId?: string;
    board?: BoardName;
    jieqiCapture?: string;
};

export type MsgMovesAfterReconnect = {
    type: string; //"reconnect"
    gameId: string;
    movesQueued: MsgMove[]; // in case of simul we might have 2 moves queued
};
