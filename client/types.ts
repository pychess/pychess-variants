import { FairyStockfish } from 'ffish-es6';
import { CrossTable, MsgBoard } from './messages';

export type JSONPrimitive = string | number | boolean | null;
export type JSONValue = JSONPrimitive | JSONObject | JSONArray;
export type JSONObject = { [member: string]: JSONValue };
export type JSONArray = JSONValue[];

export type BugBoardName = 'a' | 'b';
export type BoardName = '' | BugBoardName;

export interface SimulPlayer {
    name: string;
    rating: number;
    title: string;
}

export interface SimulGame {
    gameId: string;
    wplayer: string;
    bplayer: string;
    variant: string;
    fen: string;
    rated: boolean;
    base: number;
    inc: number;
    byo: number;
    status: number;
    result: string;
}

export type StudyFeatureSelection = 'nobody' | 'owner' | 'contributor' | 'member' | 'everyone';
export type StudyChapterMode = 'normal' | 'practice' | 'conceal' | 'gamebook';
export type StudyChapterStatus = '1-0' | '0-1' | '½-½' | '*';
export type PracticeGoal =
    | { result: 'mate' | 'win' }
    | { result: 'mateIn' | 'drawIn' | 'equalIn' | 'winIn'; moves: number }
    | { result: 'evalIn'; moves: number; cp: number }
    | { result: 'promotion'; cp: number };

export type StudyServerEval = {
    path: string;
    done: boolean;
    pending?: boolean;
    requestedAt: string;
    analysis: Array<{ s: { cp?: number; mate?: number }; d?: number; p?: string } | null>;
};

export type StudyChapterPreview = {
    id: string;
    name: string;
    order: number;
    orientation: 'white' | 'black';
    mode: StudyChapterMode;
    status?: StudyChapterStatus;
    concealPly?: number;
    descriptionPinned?: boolean;
};

export type StudyPageModel = {
    id: string;
    name: string;
    flair?: string;
    owner: string;
    visibility: 'private' | 'unlisted' | 'public';
    isOwner: boolean;
    canWrite: boolean;
    canPreviewPractice?: boolean;
    canClone: boolean;
    canShare?: boolean;
    canEmbed?: boolean;
    enabledModes?: StudyChapterMode[];
    features?: {
        computer: boolean;
        explorer: boolean;
    };
    settings?: {
        computer: StudyFeatureSelection;
        explorer: StudyFeatureSelection;
        cloneable: StudyFeatureSelection;
        shareable: StudyFeatureSelection;
    };
    canLike: boolean;
    liked: boolean;
    likes: number;
    topics: string[];
    maxTopics: number;
    topicMinLength: number;
    topicMaxLength: number;
    members: Record<string, 'read' | 'write'>;
    maxMembers: number;
    sharedChapter: string;
    sharedPath: string;
    roomSnapshotToken: string;
    practice?: {
        variant: string;
        sectionId: string;
        sectionName: string;
        studyTitle: string;
        studyDescription: string;
        studyIcon: string;
        menu: {
            id: string;
            name: string;
            studies: { id: string; name: string; url: string }[];
        }[];
        indexUrl: string;
        studyUrl: string;
        completedChapterIds: string[];
        persistProgress: boolean;
        preview?: boolean;
        goal?: PracticeGoal;
    };
    // Runtime collaboration mode. The server owns sharedChapter/sharedPath; these
    // three fields are local browser state initialized by the Study client.
    sticky?: boolean;
    write?: boolean;
    behind?: number;
    // Runtime-only Study session override. Preview never persists to the server.
    modeOverride?: 'preview' | 'analysis' | null;
    // Local sidebar UI state, kept across in-place chapter and member refreshes.
    sideTab?: 'chapters' | 'members';
    memberConfig?: string;
    likePending?: boolean;
    serverAnalysisError?: string;
    chapterDescriptionEditing?: boolean;
    chapter: {
        id: string;
        name: string;
        revision: number;
        snapshotToken: string;
        order: number;
        orientation: 'white' | 'black';
        mode: StudyChapterMode;
        concealPly?: number;
        variant: string;
        chess960: boolean;
        initialFen: string;
        variantIni: string | null;
        createdAt: string;
        source?: { kind: 'scratch' | 'game' | 'study' | 'import'; id?: string | null };
        description: string;
        tags: Record<string, string>;
        serverEval: StudyServerEval | null;
        tree: import('./study/studyTree').StudyTreeDto;
    };
    chapters: StudyChapterPreview[];
};

export type PyChessModel = {
    ffish: FairyStockfish;
    username: string;
    admin: boolean;
    home: string;
    anon: string;
    profileid: string;
    profileRestricted: boolean;
    title: string;
    variant: string;
    chess960: string;
    rated: string;
    corr: string;
    level: number;
    gameId: string;
    gameCategory: string;
    tournamentId: string;
    tournamentname: string;
    simulname: string;
    tournamentcreator: string;
    tournamentmanager: boolean;
    tournamentteamid: string;
    tournamentteamname: string;
    inviter: string;
    botChallengeStatus: string;
    botChallengeDeclineReason: string;
    botChallengeOpponent: string;
    botSupportedVariants: string[] | null;
    challengeId: string;
    ply: number;
    ct: CrossTable | string;
    board: MsgBoard | string;
    wplayer: string;
    wtitle: string;
    wpatron: boolean;
    wrating: string; // string, because can contain "?" suffix for provisional rating
    wrdiff: number;
    wberserk: string;
    bplayer: string;
    btitle: string;
    bpatron: boolean;
    brating: string; // string, because can contain "?" suffix for provisional rating
    brdiff: number;
    bberserk: string;
    fen: string;
    posnum: number;
    initialFen: string;
    base: number;
    inc: number;
    byo: number;
    result: string;
    status: number;
    tsystem: number;
    rounds: number;
    date: string;
    tv: boolean;
    embed: boolean;
    seekEmpty: boolean;
    tournamentDirector: boolean;
    assetURL: string;
    nnueDownloadRoot: string;
    puzzle: string;
    study: StudyPageModel | null;

    wplayerB: string;
    wtitleB: string;
    wpatronB: boolean;
    wratingB: string; // string, because can contain "?" suffix for provisional rating
    bplayerB: string;
    btitleB: string;
    bpatronB: boolean;
    bratingB: string; // string, because can contain "?" suffix for provisional rating

    blogs: string;
    timeline: string;
    corrGames: string;
    simulGames: string;
    simulHost: boolean;
    oauthUsernameSelection: {
        oauth_id: string;
        oauth_provider: string;
        oauth_username: string;
    } | null;
    pushVapidKey: string;
    pushEnabled: boolean;

    // Simul-specific properties
    simulId?: string;
    players?: SimulPlayer[];
    pendingPlayers?: SimulPlayer[];
    createdBy?: string;
    name?: string;
};
