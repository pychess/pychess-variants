from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from compress import (
    decode_move_duck,
    decode_move_extended,
    decode_move_flipping,
    decode_move_standard,
    encode_move_duck,
    encode_move_extended,
    encode_move_flipping,
    encode_move_standard,
)
from settings import PROD

MoveCodec = Callable[[str], str]
HiddenInfoMode = Literal["none", "fog", "covered_pieces"]
CATALOGUED_VARIANT_ICON = "☐"


@dataclass
class Variant:
    code: str
    uci_variant: str
    display_name: str
    icon: str
    chess960: bool = False
    grand: bool = False
    byo: bool = False
    two_boards: bool = False
    rating_enabled: bool = True
    hidden_info: bool = False
    hidden_info_mode: HiddenInfoMode = "none"
    base_variant: str = ""
    show_promoted: bool = False
    legal_moves_need_history: bool = False
    n_fold_is_draw: bool = False
    move_encoding: MoveCodec = encode_move_standard
    move_decoding: MoveCodec = decode_move_standard


@dataclass
class CataloguedServerVariant:
    """Runtime-loaded, user-catalogued variant.

    These variants deliberately look like ServerVariants to the rest of the
    game/replay code, but they are not members of VARIANTS/RATED_VARIANTS.
    That keeps them out of ratings, leaderboards, tournament schedules,
    puzzles, and other site-wide first-class variant features.
    """

    code: str
    uci_variant: str
    display_name: str
    translated_name: str
    icon: str = CATALOGUED_VARIANT_ICON
    chess960: bool = False
    random_start: bool = False
    grand: bool = False
    byo: bool = False
    two_boards: bool = False
    rating_enabled: bool = False
    hidden_info: bool = False
    hidden_info_mode: HiddenInfoMode = "none"
    base_variant: str = ""
    show_promoted: bool = False
    legal_moves_need_history: bool = False
    n_fold_is_draw: bool = False
    move_encoding: MoveCodec = encode_move_standard
    move_decoding: MoveCodec = decode_move_standard

    @property
    def server_name(self) -> str:
        return self.uci_variant


#  Deferred translations!
def _(message: str) -> str:
    return message


class ServerVariants(Enum):
    def __init__(self, variant: Variant) -> None:
        self.code = variant.code
        self.uci_variant = variant.uci_variant
        self.display_name = variant.display_name.upper()
        self.translated_name = variant.display_name
        self.icon = variant.icon
        self.chess960 = variant.chess960
        self.grand = variant.grand
        self.byo = variant.byo
        self.two_boards = variant.two_boards
        self.rating_enabled = variant.rating_enabled
        self.hidden_info = variant.hidden_info
        self.hidden_info_mode = variant.hidden_info_mode
        self.base_variant = variant.base_variant
        self.show_promoted = variant.show_promoted
        self.legal_moves_need_history = variant.legal_moves_need_history
        self.n_fold_is_draw = variant.n_fold_is_draw
        self.move_encoding = variant.move_encoding
        self.move_decoding = variant.move_decoding

    CHESS = Variant("n", "chess", _("Chess"), "M")
    CHESS960 = Variant("n", "chess", _("Chess960"), "V", chess960=True)
    BUGHOUSE = Variant("F", "bughouse", _("Bughouse"), "¢", two_boards=True, base_variant="crazyhouse")  # fmt: skip
    BUGHOUSE960 = Variant("F", "bughouse", _("Bughouse960"), "⌀", chess960=True, two_boards=True, base_variant="crazyhouse")  # fmt: skip
    CRAZYHOUSE = Variant("h", "crazyhouse", _("Crazyhouse"), "+")
    CRAZYHOUSE960 = Variant("h", "crazyhouse", _("Crazyhouse960"), "%", chess960=True)
    ATOMIC = Variant("A", "atomic", _("Atomic"), "~")
    ATOMIC960 = Variant("A", "atomic", _("Atomic960"), "\\", chess960=True)
    KINGOFTHEHILL = Variant("B", "kingofthehill", _("King of the Hill"), "🏴")
    KINGOFTHEHILL960 = Variant("B", "kingofthehill", _("King of the Hill 960"), "🏁", chess960=True)
    _3CHECK = Variant("X", "3check", _("Three check"), "☰")
    _3CHECK960 = Variant("X", "3check", _("Three check 960"), "☷", chess960=True)
    ANTICHESS = Variant("’", "antichess", _("Antichess"), "🐥")
    ANTICHESS960 = Variant("’", "antichess", _("Antichess960"), "🐓", chess960=True)
    RACINGKINGS = Variant("°", "racingkings", _("Racing Kings"), "🚗")
    RACINGKINGS960 = Variant("°", "racingkings", _("Racing Kings 1440"), "🚙", chess960=True)
    HORDE = Variant("š", "horde", _("Horde"), "🐖")
    HORDE960 = Variant("š", "horde", _("Horde960"), "🐷", chess960=True)
    PLACEMENT = Variant("p", "placement", _("Placement"), "S")
    DUCK = Variant("U", "duck", _("Duck Chess"), "🦆", move_encoding=encode_move_duck, move_decoding=decode_move_duck)  # fmt: skip
    ALICE = Variant("Y", "alice", _("Alice Chess"), "👧")
    FOGOFWAR = Variant("Q", "fogofwar", _("Fog of War"), "🌫", hidden_info=True, hidden_info_mode="fog")  # fmt: skip

    MAKRUK = Variant("m", "makruk", _("Makruk"), "Q")
    MAKRUKHOUSE = Variant("Ł", "makrukhouse", _("Makrukhouse"), "Q")
    MAKBUG = Variant("ß", "makbug", _("Makbug"), "Q", two_boards=True, base_variant="makrukhouse")  # fmt: skip
    MAKPONG = Variant("l", "makpong", _("Makpong"), "O")
    CAMBODIAN = Variant("b", "cambodian", _("Ouk Chaktrang"), "!")
    SITTUYIN = Variant("y", "sittuyin", _("Sittuyin"), ":")
    ASEAN = Variant("S", "asean", _("ASEAN"), "♻")

    SHOGI = Variant("g", "shogi", _("Shogi"), "K", byo=True)
    SHOSHOGI = Variant("?", "shoshogi", _("Sho Shogi"), "🍹", byo=True)
    MINISHOGI = Variant("a", "minishogi", _("Minishogi"), "6")
    KYOTOSHOGI = Variant("k", "kyotoshogi", _("Kyoto Shogi"), ")", byo=True, move_encoding=encode_move_flipping, move_decoding=decode_move_flipping)  # fmt: skip
    DOBUTSU = Variant("D", "dobutsu", _("Dobutsu"), "8", byo=True)
    GOROGOROPLUS = Variant("G", "gorogoroplus", _("Gorogoro+"), "🐱", byo=True)
    TORISHOGI = Variant("T", "torishogi", _("Tori Shogi"), "🐦", byo=True)
    CANNONSHOGI = Variant("W", "cannonshogi", _("Cannon Shogi"), "💣", byo=True)
    YOKAI = Variant("*", "yokai", _("Yokai Shogi"), "👹", byo=True)

    XIANGQI = Variant("x", "xiangqi", _("Xiangqi"), "|", grand=True)
    XIANGQIHOUSE = Variant("[", "xiangqihouse", _("Xiangqihouse"), "|", grand=True)
    SUPPLY = Variant("@", "supply", _("Supply Chess"), "|", grand=True, two_boards=True, base_variant="xiangqihouse")  # fmt: skip
    MANCHU = Variant("M", "manchu", _("Manchu+"), "{", grand=True)
    JANGGI = Variant("j", "janggi", _("Janggi"), "=", grand=True, byo=True)
    MINIXIANGQI = Variant("e", "minixiangqi", _("Minixiangqi"), "7")
    JIEQI = Variant("V", "jieqi", _("Jieqi"), "⬤", grand=True, hidden_info=True, hidden_info_mode="covered_pieces")  # fmt: skip

    SHATRANJ = Variant("†", "shatranj", _("Shatranj"), "🐘")
    CAPABLANCA = Variant("c", "capablanca", _("Capablanca"), "P")
    CAPABLANCA960 = Variant("c", "capablanca", _("Caparandom"), ",", chess960=True)
    CAPAHOUSE = Variant("i", "capahouse", _("Capahouse"), "&")
    CAPAHOUSE960 = Variant("i", "capahouse", _("Capahouse960"), "'", chess960=True)
    GOTHIC = Variant("o", "gothic", _("Gothic"), "P")
    GOTHHOUSE = Variant("t", "gothhouse", _("Gothhouse"), "&")
    EMBASSY = Variant("E", "embassy", _("Embassy"), "P")
    DRAGON = Variant("R", "dragon", _("Dragon Chess"), "🐉")
    SEIRAWAN = Variant("s", "seirawan", _("S-Chess"), "L")
    SEIRAWAN960 = Variant("s", "seirawan", _("S-Chess960"), "}", chess960=True)
    SHOUSE = Variant("z", "shouse", _("S-House"), "$")
    GRAND = Variant("q", "grand", _("Grand"), "(", grand=True)
    GRANDHOUSE = Variant("r", "grandhouse", _("Grandhouse"), "*", grand=True)
    SHOGUN = Variant("u", "shogun", _("Shogun"), "-", byo=True)
    SHAKO = Variant("d", "shako", _("Shako"), "9", grand=True)
    HOPPELPOPPEL = Variant("w", "hoppelpoppel", _("Hoppel-Poppel"), "`")
    MANSINDAM = Variant("I", "mansindam", _("Mansindam"), "⛵")

    ORDA = Variant("f", "orda", _("Orda Chess"), "R")
    KHANS = Variant("L", "khans", _("Khan's Chess"), "🐎")
    SYNOCHESS = Variant("v", "synochess", _("Synochess"), "_")
    SHINOBI = Variant("J", "shinobi", _("Shinobi"), "🐢")
    SHINOBIPLUS = Variant("K", "shinobiplus", _("Shinobi+"), "🐢")
    EMPIRE = Variant("P", "empire", _("Empire"), "♚")
    ORDAMIRROR = Variant("O", "ordamirror", _("Orda Mirror"), "◩")
    CHAK = Variant("C", "chak", _("Chak"), "🐬")
    CHENNIS = Variant("H", "chennis", _("Chennis"), "🎾", move_encoding=encode_move_flipping, move_decoding=decode_move_flipping)  # fmt: skip
    SPARTAN = Variant("N", "spartan", _("Spartan"), "⍺")
    XIANGFU = Variant('"', "xiangfu", _("Xiang Fu"), "👊")
    CWDA = Variant("Æ", "cwda", _("CWDA"), "⚔", rating_enabled=False)

    BORDERLANDS = Variant("$", "borderlands", _("Borderlands"), " 🌄", grand=True)
    ATAXX = Variant("Z", "ataxx", _("Ataxx"), "☣")

    @property
    def server_name(self) -> str:
        return self.uci_variant + ("960" if self.chess960 else "")


del _


def get_server_variant(
    uci_variant: str, chess960: bool | None
) -> ServerVariants | CataloguedServerVariant:
    if uci_variant in CATALOGUED_VARIANTS:
        return CATALOGUED_VARIANTS[uci_variant]
    return ALL_VARIANTS[uci_variant + ("960" if chess960 else "")]


NO_VARIANTS: tuple[ServerVariants, ...] = (
    ServerVariants.EMBASSY,
    ServerVariants.GOTHIC,
    ServerVariants.GOTHHOUSE,
    ServerVariants.SHINOBI,
    ServerVariants.MAKRUKHOUSE,
    ServerVariants.XIANGQIHOUSE,
)

TWO_BOARD_VARIANTS: tuple[ServerVariants, ...] = tuple(
    variant for variant in ServerVariants if variant.two_boards
)
TWO_BOARD_VARIANT_CODES: list[str] = [variant.code for variant in TWO_BOARD_VARIANTS]

ALL_VARIANTS: dict[str, ServerVariants | CataloguedServerVariant] = {
    variant.server_name: variant for variant in ServerVariants
}

CATALOGUED_VARIANTS: dict[str, CataloguedServerVariant] = {}

VARIANTS: dict[str, ServerVariants] = {
    variant.server_name: variant for variant in ServerVariants if variant not in NO_VARIANTS
}

VARIANT_ICONS: dict[str, str] = {variant.server_name: variant.icon for variant in ServerVariants}


DEV_VARIANTS: tuple[ServerVariants, ...] = (
    ServerVariants.MAKBUG,
    ServerVariants.SUPPLY,
    ServerVariants.BORDERLANDS,
    ServerVariants.CWDA,
)

# Remove DEV variants on prod site until they stabilize
if PROD:
    for variant in DEV_VARIANTS:
        del VARIANTS[variant.server_name]

# Two-board and explicitly casual-only variants have no ratings.
RATED_VARIANTS: tuple[str, ...] = tuple(
    variant.server_name
    for variant in ServerVariants
    if (variant not in NO_VARIANTS)
    and (variant not in DEV_VARIANTS)
    and not variant.two_boards
    and variant.rating_enabled
)

NOT_RATED_VARIANTS: tuple[str, ...] = tuple(
    variant.server_name
    for variant in ServerVariants
    if (variant.server_name not in RATED_VARIANTS) and (variant.server_name in VARIANTS)
)

C2V: dict[str, str] = {variant.code: variant.uci_variant for variant in ServerVariants}


def register_catalogued_server_variant(
    name: str,
    display_name: str,
    *,
    grand: bool = False,
    extended_move_codec: bool = False,
    arrowing: bool = False,
    show_promoted: bool = False,
    legal_moves_need_history: bool = False,
    n_fold_is_draw: bool = False,
    random_start: bool = False,
) -> CataloguedServerVariant:
    """Register a casual uploaded variant in the runtime server variant maps.

    The variant name itself is used as the game document code. Built-ins keep
    their short one-character codes, while catalogued variants need a stable
    full key so old games can be replayed without adding a new hard-coded code.
    """

    variant = CataloguedServerVariant(
        code=name,
        uci_variant=name,
        display_name=display_name.upper(),
        translated_name=display_name,
        icon=CATALOGUED_VARIANT_ICON,
        grand=grand,
        show_promoted=show_promoted,
        legal_moves_need_history=legal_moves_need_history,
        n_fold_is_draw=n_fold_is_draw,
        random_start=random_start,
        move_encoding=(
            encode_move_duck
            if arrowing
            else encode_move_extended
            if extended_move_codec
            else encode_move_standard
        ),
        move_decoding=(
            decode_move_duck
            if arrowing
            else decode_move_extended
            if extended_move_codec
            else decode_move_standard
        ),
    )
    CATALOGUED_VARIANTS[name] = variant
    ALL_VARIANTS[name] = variant
    VARIANT_ICONS[name] = variant.icon
    C2V[name] = name
    if grand:
        if name not in GRANDS:
            GRANDS.append(name)
    elif name in GRANDS:
        GRANDS.remove(name)

    return variant


def unregister_catalogued_server_variant(name: str) -> None:
    """Remove an uploaded variant from runtime site maps.

    Fairy-Stockfish itself cannot unload an already loaded config from the
    current process, so this only hides the variant from pychess routing and
    runtime lookups. Saved games keep their inline INI.
    """

    CATALOGUED_VARIANTS.pop(name, None)
    ALL_VARIANTS.pop(name, None)
    VARIANT_ICONS.pop(name, None)
    C2V.pop(name, None)
    if name in GRANDS:
        GRANDS.remove(name)


def is_catalogued_variant(name: str | None) -> bool:
    return bool(name) and name in CATALOGUED_VARIANTS


def catalogued_variant_random_start(name: str) -> bool:
    variant = CATALOGUED_VARIANTS.get(name)
    return variant is not None and variant.random_start


def is_catalogued_variant_code(code: str | None) -> bool:
    return bool(code) and code in CATALOGUED_VARIANTS


GRANDS: list[str] = [variant.server_name for variant in ServerVariants if variant.grand]

BYOS: tuple[str, ...] = tuple(variant.server_name for variant in ServerVariants if variant.byo)


if __name__ == "__main__":
    print(GRANDS)

    from deprecated import V2C_ORIG, VARIANT_ICONS_ORIG

    for sn, variant in VARIANTS.items():
        print(variant.code, variant.icon, sn)
        assert variant.code == V2C_ORIG[variant.uci_variant]
        assert variant.icon == VARIANT_ICONS_ORIG[variant.server_name]
