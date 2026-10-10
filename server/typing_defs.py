from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Literal, NotRequired, TypedDict

if TYPE_CHECKING:
    from user import User


class PerfGl(TypedDict):
    r: float
    d: float
    v: float


class PerfEntry(TypedDict):
    gl: PerfGl
    la: datetime
    nb: int


PerfMap = dict[str, PerfEntry]
ClockValues = Sequence[int | float]


class UserCount(TypedDict):
    game: int
    win: int
    loss: int
    draw: int
    rated: int


class ArenaCreationHistoryEntry(TypedDict):
    at: datetime
    id: str


class UserDocument(TypedDict, total=False):
    _id: str
    title: str
    enabled: bool
    shadowban: bool
    patron: bool
    createdAt: datetime
    count: UserCount
    tournamentPoints: int | float
    forumPosts: int
    variantCount: int
    swissBanUntil: datetime
    swissBanHours: int
    swissBanGameId: str
    chatTimeoutUntil: datetime
    tournamentGameEffectIds: list[str]
    lastArenaCreatedAt: datetime
    arenaCreationHistory: list[ArenaCreationHistoryEntry]
    fixedRoundCreationHistory: list[ArenaCreationHistoryEntry]
    perfs: PerfMap
    pperfs: PerfMap
    lang: str
    theme: str
    ct: str
    pmf: bool
    cps: bool
    rps: bool
    cvf: list[str]
    oauth_id: str
    oauth_provider: str
    security: dict[str, object]


class RelationDocument(TypedDict):
    u1: str
    u2: str
    r: int


class Crosstable(TypedDict):
    _id: str
    s1: int
    s2: int
    r: list[str]


class UserJson(TypedDict):
    _id: str
    title: str
    online: bool
    simul: bool


class FollowingUserRow(TypedDict):
    username: str
    title: str
    patron: bool
    games: int
    rating: str
    variant: str
    online: bool


class UserStatusJson(TypedDict):
    id: str
    online: bool
    patron: NotRequired[bool]


class UserBlocksResponse(TypedDict):
    blocks: list[str]


class VideoDoc(TypedDict, total=False):
    _id: str
    category: str
    tags: list[str]


class GameSummaryJson(TypedDict):
    gameId: str
    title: str
    name: str
    rating: int
    color: Literal["w", "b"]
    result: str
    # Optional game termination status code (used for variant-specific tournament point display).
    status: NotRequired[int]


class TvGameJson(TypedDict):
    type: Literal["tv_game"]
    gameId: str
    variant: str
    fen: str
    wt: str
    bt: str
    w: str
    b: str
    wr: int | str
    br: int | str
    chess960: bool
    base: int | float
    inc: int
    byoyomi: int
    lastMove: str | None


class RatingDiffs(TypedDict):
    brdiff: int | str
    wrdiff: int | str


class AnalysisVariationStep(TypedDict):
    move: str
    fen: str
    turnColor: str
    check: bool
    san: str
    sanSAN: str


class AnalysisAdvice(TypedDict):
    nag: int
    comment: str
    variation: list[AnalysisVariationStep]


class AnalysisStep(TypedDict, total=False):
    s: object
    d: int
    p: str
    advice: AnalysisAdvice


class GameRatingDoc(TypedDict):
    e: int | str
    d: NotRequired[int | str]
    n: NotRequired[PerfEntry]


GameDocument = TypedDict(
    "GameDocument",
    {
        "_id": str,
        "us": list[str],
        "v": str,
        "b": int | float,
        "i": int,
        "m": list[str],
        "d": datetime,
        "f": str,
        "p": NotRequired[int],
        "s": int,
        "r": str,
        "bp": NotRequired[int],
        "byost": NotRequired[list[dict[str, object]]],
        "byop": NotRequired[list[int]],
        "byoo": NotRequired[bool],
        "byoc": NotRequired[int],
        "if": NotRequired[str],
        "uci": NotRequired[int],
        "c": NotRequired[bool],
        "x": NotRequired[int],
        "y": NotRequired[int],
        "z": NotRequired[int],
        "tid": NotRequired[str],
        "rn": NotRequired[int],
        "aid": NotRequired[str],
        "sid": NotRequired[str],
        "sh": NotRequired[str],
        "cw0": NotRequired[int],
        "cb0": NotRequired[int],
        "a": NotRequired[list[AnalysisStep]],
        "cw": NotRequired[list[int]],
        "cb": NotRequired[list[int]],
        "p0": NotRequired[GameRatingDoc],
        "p1": NotRequired[GameRatingDoc],
        "by": NotRequired[str],
        "wd": NotRequired[bool],
        "bd": NotRequired[bool],
        "wb": NotRequired[bool],
        "bb": NotRequired[bool],
        "bj": NotRequired[list[str]],
        "wj": NotRequired[list[str]],
        "l": NotRequired[datetime],
        "mct": NotRequired[list[tuple[int, int]]],
        "mc": NotRequired[int],
        "ws": NotRequired[bool],
        "bs": NotRequired[bool],
        "fx": NotRequired[int],
    },
)


class GameStep(TypedDict, total=False):
    fen: str
    move: str
    san: str | None
    turnColor: str
    check: bool
    clocks: ClockValues
    analysis: AnalysisStep


class GameDisplayHistory(TypedDict):
    variant: str
    chess960: bool
    moves: list[str]
    showPromoted: bool
    countStarted: int
    usi: bool
    clocksWhite: NotRequired[list[int | float]]
    clocksBlack: NotRequired[list[int | float]]
    analysis: NotRequired[list[AnalysisStep | None]]
    countIntervals: NotRequired[list[tuple[int, int]]]
    jieqiCovered: NotRequired[dict[str, str]]


class GameBoardResponse(TypedDict):
    type: Literal["board"]
    gameId: str
    variant: str
    status: int
    result: str
    fen: str
    lastMove: str | None
    tp: str
    steps: list[GameStep]
    history: NotRequired[GameDisplayHistory]
    check: bool
    ply: int
    positionId: NotRequired[str]
    clocks: ClockValues
    byo: list[int] | str
    pgn: str
    rdiffs: RatingDiffs | str
    date: str
    uci_usi: str
    ct: Crosstable | str
    berserk: dict[str, bool]
    by: str
    jieqiCaptures: NotRequired[list[str]]
    jieqiCaptureStack: NotRequired[list[str | None]]
    takeback: NotRequired[bool]


class GameEndResponse(TypedDict):
    type: Literal["gameEnd"]
    status: int
    result: str
    gameId: str
    pgn: str
    ct: NotRequired[Crosstable | str]
    rdiffs: NotRequired[RatingDiffs | str]
    jieqiCaptures: NotRequired[list[str]]
    jieqiCaptureStack: NotRequired[list[str | None]]


TournamentPoint = tuple[int | str, int] | Literal["-"]


class FishnetCapabilities(TypedDict):
    variants: list[str]


class FishnetKey(TypedDict):
    apikey: str
    capabilities: NotRequired[FishnetCapabilities]


class FishnetAcquireFishnet(FishnetKey):
    version: str


class FishnetAcquireStockfish(TypedDict):
    name: str
    nnue: NotRequired[str]


class FishnetAcquirePayload(TypedDict):
    fishnet: FishnetAcquireFishnet
    stockfish: FishnetAcquireStockfish


class FishnetKeyPayload(TypedDict):
    fishnet: FishnetKey


class FishnetScore(TypedDict, total=False):
    cp: int
    mate: int


class FishnetAnalysisItem(TypedDict):
    score: FishnetScore
    depth: NotRequired[int]
    pv: NotRequired[str]


class FishnetAnalysisPayload(TypedDict):
    fishnet: FishnetKey
    analysis: list[FishnetAnalysisItem | None]


class FishnetMoveInfo(TypedDict):
    bestmove: str
    fen: NotRequired[str]


class FishnetMovePayload(TypedDict):
    fishnet: FishnetKey
    move: FishnetMoveInfo


class FishnetAbortError(TypedDict):
    reason: str
    kind: NotRequired[str]
    message: NotRequired[str]
    engine_returncode: NotRequired[int]


class FishnetAbortPayload(TypedDict):
    fishnet: FishnetKey
    error: NotRequired[FishnetAbortError]


class FishnetWorkInfo(TypedDict):
    type: Literal["analysis", "move"]
    id: str
    level: NotRequired[int]


class FishnetWork(TypedDict):
    work: FishnetWorkInfo
    game_id: NotRequired[str]
    study_id: NotRequired[str]
    chapter_id: NotRequired[str]
    study_path: NotRequired[str]
    position: str
    variant: str
    chess960: bool
    moves: str
    nnue: object
    time: NotRequired[float]
    username: NotRequired[str]
    nodes: NotRequired[int]
    skipPositions: NotRequired[list[int]]
    variantsSha256: NotRequired[str]
    variantsScope: NotRequired[str]
    abort_count: NotRequired[int]
    stale_reissue_count: NotRequired[int]
    move_failure_count: NotRequired[int]
    engine_failure_count: NotRequired[int]
    engine_crash_count: NotRequired[int]
    last_abort_reason: NotRequired[str]


class StreamInfo(TypedDict):
    username: str
    streamer: str
    site: str
    title: str


class TwitchOAuthTokenResponse(TypedDict, total=False):
    access_token: str
    expires_in: int
    status: int
    message: str


class TwitchSubscriptionData(TypedDict):
    id: str


class TwitchSubscriptionsResponse(TypedDict):
    data: list[TwitchSubscriptionData]


class TwitchSubscriptionRequestResponse(TypedDict, total=False):
    data: list[TwitchSubscriptionData]
    error: str
    message: str


class TwitchUserData(TypedDict):
    login: str
    id: str


class TwitchUsersResponse(TypedDict):
    data: list[TwitchUserData]


class TwitchStreamData(TypedDict):
    title: str
    user_login: str
    type: str


class TwitchStreamsResponse(TypedDict):
    data: list[TwitchStreamData]


class TwitchWebhookEvent(TypedDict):
    broadcaster_user_login: str
    type: str
    title: NotRequired[str]


class TwitchWebhookPayload(TypedDict):
    event: TwitchWebhookEvent
    challenge: NotRequired[str]


class NotificationContent(TypedDict, total=False):
    id: str
    tid: str
    arr: str
    opp: str
    san: str
    topic: str
    slug: str
    categ: str
    team: str
    name: str
    text: str
    sender: str
    date: str
    win: bool | None


class NotificationDocument(TypedDict):
    _id: str
    notifies: str
    type: str
    read: bool
    createdAt: datetime
    expireAt: str
    content: NotificationContent


class ViewContext(TypedDict, total=False):
    user: User
    lang: str
    variant_display_name: Callable[[str], str]
    theme: str
    game_category: str
    category_variants: Mapping[str, object]
    category_variant_groups: Mapping[str, str]
    category_variant_list: tuple[str, ...]
    category_variant_set: frozenset[str]
    game_category_intro: bool
    catalogued_variants: str
    site_variants: Mapping[str, object]
    favorite_variants: Mapping[str, object]
    community_variants_for_tournaments: Mapping[str, object]
    community_variants_for_simuls: Mapping[str, object]
    max_simul_variants: int
    simul_teams: Sequence[Mapping[str, object]]
    community_arena_max_creations_per_24h: int
    fixed_round_max_creations_per_24h: int
    tournament_delete_allowed: bool
    tournament_teams: Sequence[Mapping[str, object]]
    selected_tournament_team_id: str
    pm_friends_only: bool
    corr_push_enabled: bool
    rr_push_enabled: bool
    menu_variant: str
    title: str
    view: str
    view_css: str
    anon: bool
    username: str
    csrf_token: str
    piece_sets: list[str]
    simuling: bool
    admin: bool
    admin_section: str
    admin_user_query: str
    admin_user_error: str
    admin_user_status: Mapping[str, object] | None
    admin_action_notice: str
    admin_timeout_reasons: Mapping[str, str]
    admin_operations_anons_disabled: bool
    admin_operations_streams: Sequence[Mapping[str, object]]
    admin_operations_fishnet: Sequence[Mapping[str, object]]
    admin_operations_variants: Sequence[Mapping[str, str]]
    admin_operations_history: Sequence[Mapping[str, object]]
    admin_system_message_active_days: int
    admin_system_message_history: Sequence[Mapping[str, object]]
    admin_team_query: str
    admin_team_status: str
    admin_teams: Sequence[Mapping[str, object]]
    admin_team_history: Sequence[Mapping[str, object]]
    mod_report_score: int
    vapid_public_key: str
    allusers: Sequence[User]
    anon_online: int
    blog_tag: Callable[[str], str]
    blogs: list[object] | str
    timeline: str
    following_profile: str
    following_users: list[FollowingUserRow]
    following_total: int
    following_prev_href: str
    following_next_href: str
    site_tag: str
    site_tags: list[str]
    community_posts: list[object]
    community_topic: str
    community_topics: list[str]
    community_variants: dict[str, object]
    community_prev_href: str
    community_next_href: str
    teams: Sequence[Mapping[str, object]]
    my_team_ids: set[str]
    mine_only: bool
    team: Mapping[str, object]
    team_closed: bool
    team_is_site_admin: bool
    team_can_close: bool
    team_can_reopen: bool
    team_member: Mapping[str, object] | None
    team_members: Sequence[Mapping[str, object]]
    team_members_total: int
    team_members_page: int
    team_members_prev_href: str | None
    team_members_next_href: str | None
    team_leaders: Sequence[Mapping[str, object]]
    team_requests: Sequence[Mapping[str, object]]
    team_request_teams: Mapping[str, Mapping[str, object]]
    team_declined_requests: Sequence[Mapping[str, object]]
    team_declined_requests_total: int
    team_declined_requests_page: int
    team_declined_requests_search: str
    team_declined_requests_prev_href: str | None
    team_declined_requests_next_href: str | None
    team_declined_requests_current_href: str
    team_pending_request: Mapping[str, object] | None
    team_declined_request: Mapping[str, object] | None
    team_request_default_message: str
    team_request_max_length: int
    team_can_manage_requests: bool
    team_can_kick: bool
    team_can_edit: bool
    team_can_create_tournament: bool
    team_can_manage_leaders: bool
    team_can_send_update: bool
    team_latest_update: Mapping[str, object] | None
    team_can_see_forum: bool
    team_forum_categ_id: str
    team_forum_topics: Sequence[Mapping[str, object]]
    team_public_permission: str
    team_tournaments: Sequence[Mapping[str, object]]
    team_update_teams: Sequence[Mapping[str, object]]
    team_updates: Sequence[Mapping[str, object]]
    updates_team: Mapping[str, object] | None
    team_updates_subscribed: bool
    team_update_max_length: int
    team_update_max_per_7_days: int
    team_update_quota_remaining: int
    team_max_joined: int
    team_max_created_per_7_days: int
    team_permission_definitions: Sequence[tuple[str, str, str]]
    team_max_admins: int
    team_max_leaders: int
    reports: list[object]
    report_status: str
    report_open_count: int
    report_processed_count: int
    report_error: str
    report_source: str
    report_username: str
    report_reason: str
    report_details: str
    report_game_id: str
    report_reason_options: list[object]
    report_user_locked: bool
    report_inbox_msgs: list[object]
    report_selected_msgs: list[str]
    can_block: bool
    can_follow: bool
    is_following: bool
    can_message: bool
    can_challenge: bool
    profile_system: bool
    corr_games: str
    simul_games: str
    simulhost: bool
    created_simuls: Sequence[object]
    my_simuls: Sequence[object]
    ct: str
    cup: Mapping[str, tuple[str, str]]
    edit: bool
    faq: str
    finished_simuls: Sequence[object]
    gameId: str
    highscore: object
    highscore_patrons: set[str]
    highscore_online: set[str]
    inviter: str
    bot_challenge_status: str
    bot_challenge_decline_reason: str
    bot_challenge_opponent: str
    bot_supported_variants: str
    lichess_id: str
    lishogi_id: str
    oauth_username_selection: Mapping[str, str | None] | None
    bot_tokens: list[Mapping[str, object]]
    bot_account_title: str
    bot_game_count: int
    bot_upgrade_eligible: bool
    bot_upgrade_reason: str
    bot_notice: str
    bot_error: str
    new_bot_token: str
    online_users: Sequence[User]
    profile: str | None
    profile_teams: Sequence[Mapping[str, object]]
    profile_simul_count: int
    profile_tournament_points: int | float
    profile_tournament_entries: list[dict[str, object]]
    profile_tournament_prev: str
    profile_tournament_next: str
    profile_forum_posts: int
    profile_variant_count: int
    profile_title: str
    profile_patron: bool
    profile_online: bool
    profile_restricted: bool
    ublog_posts: list[object]
    ublog_post_count: int
    ublog_is_owner: bool
    ublog_is_drafts: bool
    ublog_author_online: bool
    ublog_post: Mapping[str, object] | None
    ublog_related: list[object]
    ublog_step: str
    ublog_steps: list[str]
    ublog_create_mode: bool
    ublog_cancel_url: str
    ublog_can_publish_site: bool
    ublog_topic_whitelist: list[str]
    ublog_values: Mapping[str, object]
    ublog_errors: list[str]
    puzzle: str
    ratings: dict[str, tuple[str, int]]
    seekempty: bool
    simulid: str
    simulname: str
    started_simuls: Sequence[object]
    simul_history_profile: str
    simul_history_entries: Sequence[object]
    simul_history_total: int
    simul_history_prev_href: str
    simul_history_next_href: str
    tags: Sequence[str] | Mapping[str, str]
    tournament: object
    tournamentdirector: bool
    challengeid: str
    trophies: list[tuple[str, str]]
    users: Mapping[str, User]
    videoId: str | None
    videos: list[VideoDoc]
    video_tag: Callable[[str], str]
    video_target: Callable[[str], str]
    wberserk: bool
    winners: Mapping[str, list[tuple[str, str, str, str]]]
    bberserk: bool
    gameid: str
    variant: str
    wplayer: str
    wtitle: str
    wrating: int | str
    wrdiff: int | str
    chess960: bool
    rated: bool | int | None
    corr: bool
    level: int
    bplayer: str
    btitle: str
    brating: int | str
    brdiff: int | str
    fen: str
    posnum: int
    base: float
    inc: int
    byo: int
    result: str
    status: int
    date: str | datetime
    ply: int | str
    initialFen: str
    board: str
    wplayerB: str
    wtitleB: str
    wratingB: str
    bplayerB: str
    btitleB: str
    bratingB: str
    variants: Mapping[str, object]
    groups: Mapping[str, str]
    icons: Mapping[str, str]
    pairing_system_name: Callable[[int], str]
    time_control_str: Callable[..., str]
    tables: object
    td: bool
    tournamentid: str
    tournamentname: str
    tournamentcreator: str
    tournamentmanager: bool
    tournamentteamid: str
    tournamentteamname: str
    description: str
    before_start: int
    minutes: int
    rounds: int
    round_interval: int
    frequency: str


class TournamentCreateData(TypedDict):
    name: str
    createdBy: str
    variant: str
    base: float
    inc: int
    system: int
    beforeStart: NotRequired[int]
    minutes: int
    password: NotRequired[str]
    rated: NotRequired[bool]
    chess960: NotRequired[bool]
    bp: NotRequired[int]
    fen: NotRequired[str]
    rounds: NotRequired[int]
    rrMaxPlayers: NotRequired[int]
    rrRequiresApproval: NotRequired[bool]
    rrJoiningClosed: NotRequired[bool]
    roundInterval: NotRequired[int]
    entryMinRating: NotRequired[int]
    entryMaxRating: NotRequired[int]
    entryMinRatedGames: NotRequired[int]
    entryMinAccountAgeDays: NotRequired[int]
    entryTitledOnly: NotRequired[bool]
    forbiddenPairings: NotRequired[str]
    manualPairings: NotRequired[str]
    teamId: NotRequired[str]
    startDate: NotRequired[datetime | None]
    frequency: NotRequired[str]
    description: NotRequired[str]
    createdAt: NotRequired[datetime]
    status: NotRequired[int]
    tid: NotRequired[str]
    with_clock: NotRequired[bool]


class ScheduledTournamentCreateData(TournamentCreateData):
    pass


class SimulParticipantDoc(TypedDict):
    user: str
    variant: str
    host: bool


class SimulDoc(TypedDict):
    _id: str
    name: str
    description: str
    fen: str
    variants: list[str]
    rated: bool
    base: int
    inc: int
    hostColor: str
    hostExtraTime: int
    hostExtraTimePerPlayer: int
    entryMinRating: int
    entryMaxRating: int
    entryMinRatedGames: int
    entryMinAccountAgeDays: int
    entryTitledOnly: bool
    entryTeamId: NotRequired[str | None]
    entryTeamName: NotRequired[str | None]
    featurable: bool
    createdBy: str
    createdAt: datetime
    hostSeenAt: datetime
    estimatedStartAt: NotRequired[datetime | None]
    startsAt: NotRequired[datetime | None]
    endsAt: NotRequired[datetime | None]
    status: int
    hostGameId: NotRequired[str | None]
    players: list[SimulParticipantDoc]
    pendingPlayers: list[SimulParticipantDoc]


class SimulUpdateData(TypedDict, total=False):
    name: str
    description: str
    fen: str
    variants: list[str]
    rated: bool
    base: int
    inc: int
    hostColor: str
    hostExtraTime: int
    hostExtraTimePerPlayer: int
    entryMinRating: int
    entryMaxRating: int
    entryMinRatedGames: int
    entryMinAccountAgeDays: int
    entryTitledOnly: bool
    entryTeamId: str | None
    entryTeamName: str | None
    featurable: bool
    createdBy: str
    createdAt: datetime
    hostSeenAt: datetime
    estimatedStartAt: datetime | None
    startsAt: datetime | None
    endsAt: datetime | None
    status: int
    hostGameId: NotRequired[str | None]
    players: list[SimulParticipantDoc]
    pendingPlayers: list[SimulParticipantDoc]


class TournamentDoc(TypedDict):
    _id: str
    name: str
    password: str
    d: str
    fr: str
    minutes: int
    v: str
    vini: NotRequired[str]
    vd: NotRequired[str]
    vby: NotRequired[str]
    b: float
    i: int
    bp: int
    f: str
    y: int
    z: int
    system: int
    rounds: int
    rrMaxPlayers: NotRequired[int]
    rrRequiresApproval: NotRequired[bool]
    rrJoiningClosed: NotRequired[bool]
    rrPendingPlayers: NotRequired[list[str]]
    rrDeniedPlayers: NotRequired[list[str]]
    ri: NotRequired[int]
    entryMinRating: NotRequired[int]
    entryMaxRating: NotRequired[int]
    entryMinRatedGames: NotRequired[int]
    entryMinAccountAgeDays: NotRequired[int]
    entryTitledOnly: NotRequired[bool]
    forbiddenPairings: NotRequired[str]
    manualPairings: NotRequired[str]
    teamId: NotRequired[str]
    nbPlayers: int
    cr: NotRequired[int]
    pairingInProgressRound: NotRequired[int]
    manualPairingsInProgress: NotRequired[str]
    nextRoundStartsAt: NotRequired[datetime]
    createdBy: str
    createdAt: datetime
    beforeStart: int
    startsAt: datetime
    status: int
    finishReason: NotRequired[str]
    nbGames: NotRequired[int]
    nbBerserk: NotRequired[int]
    winner: NotRequired[str]


class TournamentUpdateData(TypedDict, total=False):
    profilePointsPending: bool
    name: str
    password: str
    d: str
    fr: str
    minutes: int
    v: str
    vini: str
    vd: str
    vby: str
    b: float
    i: int
    bp: int
    f: str
    y: int
    z: int
    system: int
    rounds: int
    rrMaxPlayers: int
    rrRequiresApproval: bool
    rrJoiningClosed: bool
    rrPendingPlayers: list[str]
    rrDeniedPlayers: list[str]
    ri: int
    entryMinRating: int
    entryMaxRating: int
    entryMinRatedGames: int
    entryMinAccountAgeDays: int
    entryTitledOnly: bool
    forbiddenPairings: str
    manualPairings: str
    teamId: str
    nbPlayers: int
    cr: int
    pairingInProgressRound: int | None
    manualPairingsInProgress: str | None
    nextRoundStartsAt: datetime
    createdBy: str
    createdAt: datetime
    beforeStart: int
    startsAt: datetime | None
    status: int
    finishReason: str
    nbGames: int
    winner: str
    nbBerserk: int


class TournamentPlayerDoc(TypedDict):
    _id: str
    tid: str
    uid: str
    r: int
    pr: str
    a: bool
    f: int
    s: int
    w: int
    b: int
    e: int
    g: NotRequired[int]
    p: list[TournamentPoint]
    jr: NotRequired[int]
    joinedAt: NotRequired[datetime]
    wd: bool


class TournamentPlayerUpdate(TypedDict, total=False):
    _id: str | None
    tid: str
    uid: str
    r: int
    pr: str
    a: bool
    f: int
    s: int
    w: int
    b: int
    e: int
    g: int
    p: list[TournamentPoint]
    jr: int
    joinedAt: datetime
    wd: bool


class TournamentPairingDoc(TypedDict):
    _id: str
    tid: str
    u: tuple[str, str]
    r: str
    d: datetime
    wr: str
    br: str
    wrd: NotRequired[int | str]
    brd: NotRequired[int | str]
    wb: bool
    bb: bool
    s: NotRequired[int]
    p: NotRequired[int]
    rn: NotRequired[int]
    bt: NotRequired[str]
    an: NotRequired[bool]


class TournamentPairingUpdate(TypedDict, total=False):
    tid: str
    u: tuple[str, str]
    r: str
    d: datetime
    wr: str
    br: str
    wrd: int | str
    brd: int | str
    wb: bool
    bb: bool
    s: int
    p: int | None
    rn: int
    bt: str
    an: bool


class TournamentArrangementDoc(TypedDict, total=False):
    _id: str
    tid: str
    u: tuple[str, str]
    c: tuple[str, str]
    rn: int
    s: str
    gid: str
    iid: str
    ch: str
    d: datetime
    d1: datetime
    d2: datetime
    sa: datetime
    ln: datetime
    pg: list[str]


class TournamentArrangementUpdate(TypedDict, total=False):
    tid: str
    u: tuple[str, str]
    c: tuple[str, str]
    rn: int
    s: str
    gid: str | None
    iid: str | None
    ch: str | None
    d: datetime
    d1: datetime | None
    d2: datetime | None
    sa: datetime | None
    ln: datetime | None
    pg: list[str]


class TournamentPlayerJson(TypedDict):
    paused: bool
    title: str
    name: str
    rating: int
    points: list[TournamentPoint]
    fire: int
    score: int
    perf: int
    berger: float
    nbGames: int
    nbWin: int
    nbBerserk: int
    withdrawn: NotRequired[bool]


class TournamentManagePlayerJson(TypedDict):
    title: str
    name: str
    rating: int


class TournamentPlayersResponse(TypedDict):
    type: Literal["get_players"]
    requestedBy: str
    nbPlayers: int
    nbGames: int
    page: int
    players: list[TournamentPlayerJson]
    podium: NotRequired[list[TournamentPlayerJson]]


class TournamentGameJson(TypedDict):
    gameId: str
    title: str
    name: str
    rating: int | str
    prov: NotRequired[str]
    color: str
    result: str
    # Optional game termination status code (used for variant-specific tournament point display).
    status: NotRequired[int]
    unplayedType: NotRequired[Literal["bye", "late", "absent"]]


class TournamentGamesResponse(TypedDict):
    type: Literal["get_games"]
    rank: int
    title: str
    name: str
    perf: int
    berger: float
    nbGames: int
    nbWin: int
    nbBerserk: int
    games: list[TournamentGameJson | GameSummaryJson]


class TournamentRRManagementResponse(TypedDict):
    type: Literal["rr_management"]
    requestedBy: str
    createdBy: str
    approvalRequired: bool
    joiningClosed: bool
    pendingPlayers: list[TournamentManagePlayerJson]
    deniedPlayers: list[TournamentManagePlayerJson]


class TournamentRRSettingsResponse(TypedDict):
    type: Literal["rr_settings"]
    createdBy: str
    approvalRequired: bool
    joiningClosed: bool


class TournamentTopGameResponse(TypedDict):
    type: Literal["top_game"]
    gameId: str
    variant: str
    fen: str
    w: str
    b: str
    wr: int
    br: int
    chess960: bool
    base: int | float
    inc: int
    byoyomi: int
    lastMove: str | None


class TournamentDuelItem(TypedDict):
    id: str
    wp: str
    wt: str
    wr: int | str
    wk: int | str
    bp: str
    bt: str
    br: int | str
    bk: int | str


class TournamentDuelsResponse(TypedDict):
    type: Literal["duels"]
    duels: list[TournamentDuelItem]


class TournamentStatusResponse(TypedDict):
    type: Literal["tstatus"]
    tstatus: int
    secondsToFinish: NotRequired[float]
    rounds: NotRequired[int]
    currentRound: NotRequired[int]
    roundOngoingGames: NotRequired[int]
    secondsToNextRound: NotRequired[float]
    manualNextRound: NotRequired[bool]
    nbPlayers: NotRequired[int]
    nbGames: NotRequired[int]
    wWin: NotRequired[int]
    bWin: NotRequired[int]
    draw: NotRequired[int]
    berserk: NotRequired[int]
    sumRating: NotRequired[int]


class TournamentSpotlightItem(TypedDict):
    kind: Literal["tournament"]
    tid: str
    names: dict[str, str]
    variant: str
    chess960: bool
    nbPlayers: int
    startsAt: str


class SimulSpotlightItem(TypedDict):
    kind: Literal["simul"]
    sid: str
    name: str
    variants: list[str]
    nbPlayers: int


SpotlightItem = TournamentSpotlightItem | SimulSpotlightItem


class TournamentCalendarEvent(TypedDict):
    title: str
    start: datetime
    end: datetime
    classNames: str
    borderColor: NotRequired[str]
    url: NotRequired[str]
