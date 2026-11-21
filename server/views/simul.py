from datetime import UTC, datetime

import aiohttp_jinja2
from admin_api import record_mod_action
from aiohttp import web
from catalogued.variants import is_public_catalogued_variant, public_catalogued_variants_for_forms
from const import T_CREATED
from fairy import FairyBoard
from misc import time_control_str
from newid import id8
from pychess_global_app_state_utils import get_app_state
from request_utils import read_post_data
from settings import ADMINS, SIMULING
from simul.simul import MAX_SIMUL_VARIANTS, Simul, split_simul_variant_key
from simul.simuls import (
    SIMUL_HISTORY_PAGE_SIZE,
    delete_simul_from_db,
    get_hosted_simuls,
    get_simul_home_lists,
    load_simul,
    upsert_simul_to_db,
)
from team import get_team, is_team_member, teams_for_user
from typing_defs import ViewContext
from utils import NO_LEGAL_MOVES_START_FEN_MESSAGE, sanitize_fen
from variants import VARIANT_ICONS, VARIANTS, get_server_variant, is_catalogued_variant

from views import add_catalogued_variant_context, get_user_context


# Deferred translations for select labels rendered through Jinja gettext.
def _(message: str) -> str:
    return message


RATED_GAME_CHOICES = [
    (0, _("No restriction")),
    (5, _("5 rated games")),
    (10, _("10 rated games")),
    (20, _("20 rated games")),
    (50, _("50 rated games")),
    (100, _("100 rated games")),
    (200, _("200 rated games")),
]
RATED_GAME_VALUES = [value for value, _ in RATED_GAME_CHOICES]
MIN_RATING_CHOICES = [
    (0, _("No restriction")),
    (800, "800"),
    (900, "900"),
    (1000, "1000"),
    (1100, "1100"),
    (1200, "1200"),
    (1300, "1300"),
    (1400, "1400"),
    (1500, "1500"),
    (1600, "1600"),
    (1700, "1700"),
    (1800, "1800"),
    (1900, "1900"),
    (2000, "2000"),
    (2100, "2100"),
    (2200, "2200"),
]
MIN_RATING_VALUES = [value for value, _ in MIN_RATING_CHOICES]
MAX_RATING_CHOICES = [
    (0, _("No restriction")),
    (2200, "2200"),
    (2100, "2100"),
    (2000, "2000"),
    (1900, "1900"),
    (1800, "1800"),
    (1700, "1700"),
    (1600, "1600"),
    (1500, "1500"),
    (1400, "1400"),
    (1300, "1300"),
    (1200, "1200"),
    (1100, "1100"),
    (1000, "1000"),
    (900, "900"),
    (800, "800"),
]
MAX_RATING_VALUES = [value for value, _ in MAX_RATING_CHOICES]
ACCOUNT_AGE_CHOICES = [
    (0, _("No restriction")),
    (1, _("1 day")),
    (3, _("3 days")),
    (7, _("7 days")),
    (14, _("14 days")),
    (30, _("1 month")),
    (60, _("2 months")),
    (90, _("3 months")),
    (180, _("6 months")),
    (365, _("1 year")),
    (730, _("2 years")),
    (1095, _("3 years")),
]
ACCOUNT_AGE_VALUES = [value for value, _ in ACCOUNT_AGE_CHOICES]
HOST_EXTRA_TIME_CHOICES = [
    (-7200, _("-120 minutes")),
    (-5400, _("-90 minutes")),
    (-3600, _("-60 minutes")),
    (-3000, _("-50 minutes")),
    (-2400, _("-40 minutes")),
    (-1800, _("-30 minutes")),
    (-1200, _("-20 minutes")),
    (-900, _("-15 minutes")),
    (-600, _("-10 minutes")),
    (-300, _("-5 minutes")),
    (0, _("0 minutes")),
    (300, _("+5 minutes")),
    (600, _("+10 minutes")),
    (900, _("+15 minutes")),
    (1200, _("+20 minutes")),
    (1800, _("+30 minutes")),
    (2400, _("+40 minutes")),
    (3000, _("+50 minutes")),
    (3600, _("+60 minutes")),
    (5400, _("+90 minutes")),
    (7200, _("+120 minutes")),
]
HOST_EXTRA_TIME_VALUES = [value for value, _ in HOST_EXTRA_TIME_CHOICES]
HOST_EXTRA_TIME_PER_PLAYER_CHOICES = [
    (0, _("0 seconds")),
    (10, _("10 seconds")),
    (20, _("20 seconds")),
    (30, _("30 seconds")),
    (40, _("40 seconds")),
    (50, _("50 seconds")),
    (60, _("60 seconds")),
    (90, _("90 seconds")),
    (120, _("120 seconds")),
    (180, _("180 seconds")),
    (240, _("240 seconds")),
    (300, _("300 seconds")),
]
HOST_EXTRA_TIME_PER_PLAYER_VALUES = [value for value, _ in HOST_EXTRA_TIME_PER_PLAYER_CHOICES]
del _


SIMUL_CLOCK_TIME_VALUES = [
    *range(5, 16, 5),
    *range(20, 91, 10),
    *range(120, 181, 20),
]
SIMUL_CLOCK_INCREMENT_VALUES = [
    *range(8),
    *range(10, 31, 5),
    *range(40, 61, 10),
    *range(90, 181, 30),
]
SIMUL_CLOCK_TIME_DEFAULT = 20
SIMUL_CLOCK_INCREMENT_DEFAULT = 60
SIMUL_NAME_MIN_LENGTH = 2
SIMUL_NAME_MAX_LENGTH = 40
SIMUL_TITLE_NAMES = {
    "GM": "GRANDMASTER",
    "WGM": "WOMAN GRANDMASTER",
    "IM": "INTERNATIONAL MASTER",
    "WIM": "WOMAN INTERNATIONAL MASTER",
    "FM": "FIDE MASTER",
    "WFM": "WOMAN FIDE MASTER",
    "CM": "CANDIDATE MASTER",
    "WCM": "WOMAN CANDIDATE MASTER",
    "NM": "NATIONAL MASTER",
    "WNM": "WOMAN NATIONAL MASTER",
    "LM": "LICHESS MASTER",
    "BOT": "BOT",
}


def _is_admin_username(username: str) -> bool:
    lowered = username.casefold()
    return any(lowered == admin.casefold() for admin in ADMINS)


def _can_manage_simul(user, simul: Simul) -> bool:
    return not user.anon and (
        user.username == simul.created_by or _is_admin_username(user.username)
    )


def parse_int_post_field(data, field_name: str, min_value: int, max_value: int) -> int:
    raw_value = data.get(field_name)
    if not isinstance(raw_value, (str, bytes)):
        raise web.HTTPBadRequest(text=f"Missing field: {field_name}")
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise web.HTTPBadRequest(text=f"Invalid integer value: {field_name}") from exc
    if value < min_value or value > max_value:
        raise web.HTTPBadRequest(text=f"Field out of range: {field_name}")
    return value


def parse_signed_int_post_field(data, field_name: str, min_value: int, max_value: int) -> int:
    raw_value = data.get(field_name)
    if not isinstance(raw_value, (str, bytes)):
        raise web.HTTPBadRequest(text=f"Missing field: {field_name}")
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise web.HTTPBadRequest(text=f"Invalid integer value: {field_name}") from exc
    if value < min_value or value > max_value:
        raise web.HTTPBadRequest(text=f"Field out of range: {field_name}")
    return value


def simul_default_name(user) -> str:
    if user.title and user.title != "BOT":
        return f"{user.title} {user.username}"
    return user.username


def parse_simul_name(data, host) -> str:
    name_raw = data.get("name", "")
    if not isinstance(name_raw, (str, bytes)):
        raise web.HTTPBadRequest(text="Invalid simul name")
    if isinstance(name_raw, bytes):
        name_raw = name_raw.decode("utf-8")
    name = name_raw.strip()
    if len(name) < SIMUL_NAME_MIN_LENGTH or len(name) > SIMUL_NAME_MAX_LENGTH:
        raise web.HTTPBadRequest(text="Invalid simul name length")

    # Match Lichess's anti-title-spoofing rule: ordinary hosts may use their
    # own chess title in an event name, but not another title.  Check both
    # acronyms (GM, WFM, ...) and their common long forms.
    words = {word.strip(".,:;'\"!?()[]{}+-").upper() for word in name.split()}
    normalized_name = " ".join(name.upper().split())
    own_title = (host.title or "").upper()
    for title, long_name in SIMUL_TITLE_NAMES.items():
        if title == own_title:
            continue
        if title in words or f" {long_name} " in f" {normalized_name} ":
            raise web.HTTPBadRequest(
                text="Simul name must not contain a chess title you do not hold"
            )
    return name


def parse_simul_description(data) -> str:
    description_raw = data.get("description", "")
    if not isinstance(description_raw, (str, bytes)):
        raise web.HTTPBadRequest(text="Invalid simul description")
    if isinstance(description_raw, bytes):
        description_raw = description_raw.decode("utf-8")
    description = description_raw.strip()
    if len(description) > 2000:
        raise web.HTTPBadRequest(text="Simul description is too long")
    return description


def parse_host_color(data) -> str:
    host_color = data.get("host_color", "random")
    if not isinstance(host_color, (str, bytes)):
        raise web.HTTPBadRequest(text="Invalid host color")
    if isinstance(host_color, bytes):
        host_color = host_color.decode("utf-8")
    if host_color not in ("random", "white", "black"):
        raise web.HTTPBadRequest(text="Invalid host color value")
    return host_color


async def parse_simul_team_condition(
    app_state, data, host_username: str
) -> tuple[str | None, str | None]:
    raw_team_id = data.get("entryTeam", "")
    if not isinstance(raw_team_id, (str, bytes)):
        raise web.HTTPBadRequest(text="Invalid team entry condition")
    if isinstance(raw_team_id, bytes):
        raw_team_id = raw_team_id.decode("utf-8")
    team_id = raw_team_id.strip()
    if not team_id:
        return None, None

    team = await get_team(app_state, team_id)
    if team is None or not await is_team_member(app_state, team_id, host_username):
        raise web.HTTPBadRequest(text="You can only restrict a simul to a team you belong to")
    team_name = team.get("name")
    if not isinstance(team_name, str) or not team_name:
        raise web.HTTPBadRequest(text="Invalid team entry condition")
    return team_id, team_name


def parse_optional_datetime_post_field(data, field_name: str) -> datetime | None:
    raw_value = data.get(field_name, "")
    if not isinstance(raw_value, (str, bytes)):
        raise web.HTTPBadRequest(text=f"Invalid datetime value: {field_name}")
    if isinstance(raw_value, bytes):
        raw_value = raw_value.decode("utf-8")
    raw_value = raw_value.strip()
    if raw_value == "":
        return None
    try:
        parsed = datetime.fromisoformat(raw_value.rstrip("Z")).replace(tzinfo=UTC)
    except ValueError as exc:
        raise web.HTTPBadRequest(text=f"Invalid datetime value: {field_name}") from exc
    if parsed <= datetime.now(UTC):
        raise web.HTTPBadRequest(text=f"{field_name} must be in the future")
    return parsed


def validate_simul_variant_key(app_state, variant_key: str):
    if is_catalogued_variant(variant_key):
        if not is_public_catalogued_variant(app_state, variant_key):
            raise web.HTTPBadRequest(
                text="Only public user-defined variants can be used in simuls."
            )
        variant = get_server_variant(variant_key, False)
    else:
        variant = VARIANTS.get(variant_key)
        if variant is None:
            raise web.HTTPBadRequest(text="Unknown variant")
    if variant.two_boards:
        raise web.HTTPBadRequest(text="Two-board variants are not allowed in simuls")
    return variant


def parse_simul_variants(app_state, data) -> list[str]:
    getall = getattr(data, "getall", None)
    raw_variants = getall("variants", []) if callable(getall) else []
    variants: list[str] = []
    for raw_variant in raw_variants:
        if isinstance(raw_variant, bytes):
            raw_variant = raw_variant.decode("utf-8")
        if not isinstance(raw_variant, str):
            raise web.HTTPBadRequest(text="Invalid simul variant")
        variant_key = raw_variant.strip()
        if not variant_key or variant_key in variants:
            continue
        validate_simul_variant_key(app_state, variant_key)
        variants.append(variant_key)

    if not variants:
        raise web.HTTPBadRequest(text="Select at least one simul variant")
    if len(variants) > MAX_SIMUL_VARIANTS:
        raise web.HTTPBadRequest(text=f"A simul can offer at most {MAX_SIMUL_VARIANTS} variants")
    return variants


def parse_simul_fen(data, variants: list[str]) -> str:
    raw_fen = data.get("position", "")
    if not isinstance(raw_fen, (str, bytes)):
        raise web.HTTPBadRequest(text="Invalid simul starting position")
    if isinstance(raw_fen, bytes):
        raw_fen = raw_fen.decode("utf-8")
    fen = raw_fen.strip()
    if not fen:
        return ""
    if len(variants) != 1:
        raise web.HTTPBadRequest(
            text="A custom starting position requires exactly one simul variant."
        )

    variant, chess960 = split_simul_variant_key(variants[0])
    fen_valid, sanitized_fen = sanitize_fen(variant, fen, chess960)
    if not fen_valid:
        raise web.HTTPBadRequest(text="Invalid starting position for the selected variant.")

    board = FairyBoard(variant, sanitized_fen, chess960)
    if not board.has_legal_move():
        raise web.HTTPBadRequest(text=NO_LEGAL_MOVES_START_FEN_MESSAGE)
    return sanitized_fen


def add_simul_variant_form_context(context: ViewContext, app_state, user) -> None:
    site_variants = {key: variant for key, variant in VARIANTS.items() if not variant.two_boards}
    catalogued_variants = public_catalogued_variants_for_forms(app_state)
    favorite_names = user.catalogued_variant_favorites
    favorite_variants = {
        key: variant for key, variant in catalogued_variants.items() if key in favorite_names
    }
    community_variants = {
        key: variant for key, variant in catalogued_variants.items() if key not in favorite_names
    }
    context["site_variants"] = site_variants
    context["favorite_variants"] = favorite_variants
    context["community_variants_for_simuls"] = community_variants
    context["max_simul_variants"] = MAX_SIMUL_VARIANTS


def add_simul_form_context(context: ViewContext) -> None:
    context["rated_game_choices"] = RATED_GAME_CHOICES
    context["rated_game_values"] = RATED_GAME_VALUES
    context["min_rating_choices"] = MIN_RATING_CHOICES
    context["min_rating_values"] = MIN_RATING_VALUES
    context["max_rating_choices"] = MAX_RATING_CHOICES
    context["max_rating_values"] = MAX_RATING_VALUES
    context["account_age_choices"] = ACCOUNT_AGE_CHOICES
    context["account_age_values"] = ACCOUNT_AGE_VALUES
    context["host_extra_time_choices"] = HOST_EXTRA_TIME_CHOICES
    context["host_extra_time_values"] = HOST_EXTRA_TIME_VALUES
    context["host_extra_time_per_player_choices"] = HOST_EXTRA_TIME_PER_PLAYER_CHOICES
    context["host_extra_time_per_player_values"] = HOST_EXTRA_TIME_PER_PLAYER_VALUES
    context["simul_clock_time_values"] = SIMUL_CLOCK_TIME_VALUES
    context["simul_clock_increment_values"] = SIMUL_CLOCK_INCREMENT_VALUES
    context["simul_clock_time_default"] = SIMUL_CLOCK_TIME_DEFAULT
    context["simul_clock_increment_default"] = SIMUL_CLOCK_INCREMENT_DEFAULT


def ensure_valid_host_extra_time(base: int, inc: int, host_extra_time: int) -> None:
    total_seconds = (base * 60) + host_extra_time
    if total_seconds == 0 and inc >= 10:
        return
    if total_seconds > 0:
        return
    raise web.HTTPBadRequest(text="Invalid host extra time for this clock setup")


async def get_simul_for_request(request: web.Request) -> Simul:
    app_state = get_app_state(request.app)
    simul_id = request.match_info["simulId"]
    simul = app_state.simuls.get(simul_id)
    if simul is None:
        simul = await load_simul(app_state, simul_id)
    if simul is None:
        raise web.HTTPNotFound(text="Simul not found")
    return simul


@aiohttp_jinja2.template("simuls.html")
async def simuls(request: web.Request) -> ViewContext:
    if not SIMULING:
        raise web.HTTPForbidden()

    user, context = await get_user_context(request)
    app_state = get_app_state(request.app)

    if request.method == "POST":
        if user.anon or user.bot:
            raise web.HTTPForbidden()
        data = await read_post_data(request)
        if data is None:
            raise web.HTTPNoContent()
        simul_id = id8()
        name = parse_simul_name(data, user)
        variants = parse_simul_variants(app_state, data)
        fen = parse_simul_fen(data, variants)
        host_color = parse_host_color(data)
        base = parse_int_post_field(data, "base", min_value=0, max_value=180)
        inc = parse_int_post_field(data, "inc", min_value=0, max_value=180)
        description = parse_simul_description(data)
        host_extra_time = parse_signed_int_post_field(
            data, "hostExtraTime", min_value=-7200, max_value=7200
        )
        host_extra_time_per_player = parse_int_post_field(
            data, "hostExtraTimePerPlayer", min_value=0, max_value=300
        )
        estimated_start_at = parse_optional_datetime_post_field(data, "estimatedStartAt")
        ensure_valid_host_extra_time(base, inc, host_extra_time)
        entry_min_rating = parse_int_post_field(data, "entryMinRating", min_value=0, max_value=4000)
        entry_max_rating = parse_int_post_field(data, "entryMaxRating", min_value=0, max_value=4000)
        entry_min_rated_games = parse_int_post_field(
            data, "entryMinRatedGames", min_value=0, max_value=100000
        )
        entry_min_account_age_days = parse_int_post_field(
            data, "entryMinAccountAgeDays", min_value=0, max_value=36500
        )
        entry_team_id, entry_team_name = await parse_simul_team_condition(
            app_state, data, user.username
        )
        if entry_max_rating > 0 and entry_min_rating > entry_max_rating:
            entry_min_rating, entry_max_rating = entry_max_rating, entry_min_rating

        simul = await Simul.create(
            app_state,
            simul_id,
            name=name,
            created_by=user.username,
            description=description,
            fen=fen,
            variants=variants,
            rated=False,
            base=base,
            inc=inc,
            host_color=host_color,
            host_extra_time=host_extra_time,
            host_extra_time_per_player=host_extra_time_per_player,
            estimated_start_at=estimated_start_at,
            entry_min_rating=entry_min_rating,
            entry_max_rating=entry_max_rating,
            entry_min_rated_games=entry_min_rated_games,
            entry_min_account_age_days=entry_min_account_age_days,
            entry_titled_only=False,
            entry_team_id=entry_team_id,
            entry_team_name=entry_team_name,
        )
        app_state.simuls[simul_id] = simul
        await upsert_simul_to_db(simul, app_state)
        await app_state.timeline.publish(
            "simul-create",
            user,
            {"simulId": simul.id, "name": simul.name},
        )
        raise web.HTTPFound(f"/simul/{simul_id}")

    username = None if user.anon else user.username
    my_simuls, created_simuls, started_simuls, finished_simuls = await get_simul_home_lists(
        app_state, username=username
    )
    context["my_simuls"] = my_simuls
    context["created_simuls"] = created_simuls
    context["started_simuls"] = started_simuls
    context["finished_simuls"] = finished_simuls
    context["icons"] = VARIANT_ICONS
    context["time_control_str"] = time_control_str
    context["view_css"] = "simul.css"
    return context


@aiohttp_jinja2.template("simul_history.html")
async def simul_history(request: web.Request) -> ViewContext:
    if not SIMULING:
        raise web.HTTPForbidden()

    _user, context = await get_user_context(request)
    app_state = get_app_state(request.app)
    profile_id = request.match_info["profileId"]

    profile_user = await app_state.public_users.get_profile(profile_id)
    if profile_user is None or not profile_user.enabled:
        raise web.HTTPNotFound()

    try:
        page = max(int(request.rel_url.query.get("page", "1")), 1)
    except ValueError:
        page = 1

    profile_id = profile_user.username
    hosted_simuls, total = await get_hosted_simuls(app_state, profile_id, page)
    base_url = f"/@/{profile_id}/simuls"
    context["title"] = f"{profile_id} • Hosted simuls"
    context["view"] = "simul-history"
    context["view_css"] = "simul.css"
    context["simul_history_profile"] = profile_id
    context["simul_history_entries"] = hosted_simuls
    context["simul_history_total"] = total
    context["simul_history_prev_href"] = (
        base_url if page == 2 else f"{base_url}?page={page - 1}" if page > 2 else ""
    )
    context["simul_history_next_href"] = (
        f"{base_url}?page={page + 1}" if page * SIMUL_HISTORY_PAGE_SIZE < total else ""
    )
    context["time_control_str"] = time_control_str
    return context


@aiohttp_jinja2.template("simul_new.html")
async def simul_new(request: web.Request) -> ViewContext:
    if not SIMULING:
        raise web.HTTPForbidden()

    user, context = await get_user_context(request, include_catalogued_variants=True)
    if user.anon or user.bot:
        raise web.HTTPForbidden()

    app_state = get_app_state(request.app)
    add_simul_variant_form_context(context, app_state, user)
    context["simul_teams"] = await teams_for_user(app_state, user.username)
    context["edit"] = False
    context["simul_form_action"] = "/simul"
    context["simul_form_title"] = "Host a new simul"
    context["simul_submit_label"] = "Create a new simul"
    context["simul_cancel_url"] = "/simul"
    context["simul_editable"] = True
    context["simul_default_name"] = simul_default_name(user)
    context["view_css"] = "simul.css"
    add_simul_form_context(context)
    return context


@aiohttp_jinja2.template("simul_new.html")
async def simul_edit(request: web.Request) -> ViewContext:
    if not SIMULING:
        raise web.HTTPForbidden()

    user, context = await get_user_context(request, include_catalogued_variants=True)
    simul = await get_simul_for_request(request)

    if not _can_manage_simul(user, simul):
        raise web.HTTPForbidden(text="Only the host or a site admin can edit the simul")

    app_state = get_app_state(request.app)
    form_user = await app_state.users.get(simul.created_by)
    add_simul_variant_form_context(context, app_state, form_user)
    context["simul_teams"] = await teams_for_user(app_state, simul.created_by)
    context["edit"] = True
    context["simul"] = simul
    context["simul_form_action"] = f"/simul/{simul.id}/edit"
    context["simul_form_title"] = f"Edit {simul.name}"
    context["simul_submit_label"] = "Save"
    context["simul_cancel_url"] = f"/simul/{simul.id}"
    context["simul_abort_url"] = f"/simul/{simul.id}/cancel"
    context["simul_editable"] = simul.status == T_CREATED
    context["view_css"] = "simul.css"
    add_simul_form_context(context)
    return context


@aiohttp_jinja2.template("index.html")
async def simul(request: web.Request) -> ViewContext:
    if not SIMULING:
        raise web.HTTPForbidden()

    _user, context = await get_user_context(request, include_catalogued_variants=True)
    app_state = get_app_state(request.app)

    simul_id = request.match_info["simulId"]
    simul = app_state.simuls.get(simul_id)
    if simul is None:
        simul = await load_simul(app_state, simul_id)
    if simul is None:
        raise web.HTTPNotFound(text="Simul not found")

    context["simulid"] = simul.id
    context["name"] = simul.name
    context["variant"] = simul.primary_variant_key
    for variant_key in simul.variants:
        variant_name, _chess960 = split_simul_variant_key(variant_key)
        await add_catalogued_variant_context(app_state, _user, context, variant_name)
    context["base"] = simul.base
    context["inc"] = simul.inc
    context["rated"] = False
    context["view"] = "simul"
    context["status"] = simul.status
    context["view_css"] = "simul.css"
    return context


async def update_simul(request: web.Request) -> web.Response:
    if not SIMULING:
        raise web.HTTPForbidden()

    user, _ = await get_user_context(request)
    app_state = get_app_state(request.app)
    simul = await get_simul_for_request(request)

    if not _can_manage_simul(user, simul):
        raise web.HTTPForbidden(text="Only the host or a site admin can edit the simul")

    data = await read_post_data(request)
    if data is None:
        raise web.HTTPNoContent()

    host = await app_state.users.get(simul.created_by)
    simul.name = parse_simul_name(data, host)
    simul.description = parse_simul_description(data)

    if simul.status == T_CREATED:
        variants = parse_simul_variants(app_state, data)
        fen = parse_simul_fen(data, variants)
        removed_players = simul.set_variants(variants)
        simul.fen = fen
        simul.base = parse_int_post_field(data, "base", min_value=0, max_value=180)
        simul.inc = parse_int_post_field(data, "inc", min_value=0, max_value=180)
        simul.host_color = parse_host_color(data)
        simul.host_extra_time = parse_signed_int_post_field(
            data, "hostExtraTime", min_value=-7200, max_value=7200
        )
        simul.host_extra_time_per_player = parse_int_post_field(
            data, "hostExtraTimePerPlayer", min_value=0, max_value=300
        )
        simul.estimated_start_at = parse_optional_datetime_post_field(data, "estimatedStartAt")
        ensure_valid_host_extra_time(simul.base, simul.inc, simul.host_extra_time)
        simul.entry_min_rating = parse_int_post_field(
            data, "entryMinRating", min_value=0, max_value=4000
        )
        simul.entry_max_rating = parse_int_post_field(
            data, "entryMaxRating", min_value=0, max_value=4000
        )
        simul.entry_min_rated_games = parse_int_post_field(
            data, "entryMinRatedGames", min_value=0, max_value=100000
        )
        simul.entry_min_account_age_days = parse_int_post_field(
            data, "entryMinAccountAgeDays", min_value=0, max_value=36500
        )
        simul.entry_team_id, simul.entry_team_name = await parse_simul_team_condition(
            app_state, data, simul.created_by
        )
        simul.refresh_featurable(host)
        simul.entry_titled_only = False
        if simul.entry_max_rating > 0 and simul.entry_min_rating > simul.entry_max_rating:
            simul.entry_min_rating, simul.entry_max_rating = (
                simul.entry_max_rating,
                simul.entry_min_rating,
            )
    await upsert_simul_to_db(simul)
    if simul.status == T_CREATED:
        await simul.broadcast_spotlight()
        for username in removed_players:
            await simul.broadcast({"type": "player_denied", "username": username})
    if user.username != simul.created_by:
        await record_mod_action(
            app_state,
            user.username,
            simul.created_by,
            "simul_edited",
            f"{simul.id}: {simul.name}",
        )
    raise web.HTTPFound(f"/simul/{simul.id}")


async def cancel_simul(request: web.Request) -> web.Response:
    if not SIMULING:
        raise web.HTTPForbidden()

    user, _ = await get_user_context(request)
    app_state = get_app_state(request.app)
    simul = await get_simul_for_request(request)

    if not _can_manage_simul(user, simul):
        raise web.HTTPForbidden(text="Only the host or a site admin can cancel the simul")
    if simul.status != T_CREATED:
        raise web.HTTPBadRequest(text="Only a created simul can be cancelled")

    await simul.abort()
    app_state.simuls.pop(simul.id, None)
    await delete_simul_from_db(simul.id, app_state)
    if user.username != simul.created_by:
        await record_mod_action(
            app_state,
            user.username,
            simul.created_by,
            "simul_cancelled",
            f"{simul.id}: {simul.name}",
        )
    raise web.HTTPFound("/simul")


async def start_simul(request: web.Request) -> web.Response:
    if not SIMULING:
        raise web.HTTPForbidden()

    user, _context = await get_user_context(request)
    app_state = get_app_state(request.app)
    simulId = request.match_info["simulId"]
    simul = app_state.simuls.get(simulId)
    if simul is None:
        simul = await load_simul(app_state, simulId)
    if simul is None:
        raise web.HTTPNotFound(text="Simul not found")

    if user.username != simul.created_by:
        raise web.HTTPForbidden(text="Only the host can start the simul")

    start_error = simul.start_error()
    if start_error is not None:
        raise web.HTTPBadRequest(text=start_error)

    await simul.start()
    return web.Response(text="Simul started")
