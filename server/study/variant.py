from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from catalogued_rules import catalogued_random_start
from catalogued_variants import (
    CATALOGUED_SOURCE_USER,
    CATALOGUED_VARIANT_COLLECTION,
    CATALOGUED_VISIBILITY_PRIVATE,
    CataloguedVariantValidation,
    catalogued_legal_moves_need_history,
    check_catalogued_ini_tree_without_mutating_server,
    extract_variant_name,
    replace_variant_section_name,
    validate_catalogued_ini,
)
from nnue_identity import fsf_ini_v1_fingerprint

from study.constants import STUDY_MAX_NATIVE_SNAPSHOT_VARIANTS


@dataclass(frozen=True, slots=True)
class StudyVariantOptions:
    runtime_variant: str
    show_promoted: bool = False
    legal_moves_need_history: bool = False
    random_start: bool = False


class StudyVariantCapacityError(RuntimeError):
    pass


_SNAPSHOT_VALIDATION: dict[str, CataloguedVariantValidation] = {}
# pyffish has no API to unload a loaded variant. Keep an independent admission
# ledger even when validation fails after load_variant_config(), because the native
# alias may already exist and must continue to count against the process budget.
_SNAPSHOT_NATIVE_ALIASES: set[str] = set()


def _snapshot_alias(variant_ini: str) -> str:
    # Use the repository's semantic INI fingerprint so comments/formatting cannot
    # manufacture fresh native aliases for identical Fairy-Stockfish rules. Twenty
    # hex chars keep the internal alias below the normal 32-character name limit.
    return f"studysnap_{fsf_ini_v1_fingerprint(variant_ini)[:20]}"


def _same_variant_rules(first: str, second: str) -> bool:
    if not first or not second:
        return first == second
    try:
        return fsf_ini_v1_fingerprint(first) == fsf_ini_v1_fingerprint(second)
    except ValueError:
        return first == second


def _snapshot_validation(variant_ini: str) -> CataloguedVariantValidation:
    """Validate/load a snapshot once under an immutable internal FSF alias.

    Fairy-Stockfish cannot replace an already-loaded variant definition. Historical
    Study rules therefore must never be loaded under their public catalogue name.
    The content hash makes the alias stable for the process lifetime and avoids
    accumulating another engine variant every time the same Study is opened.
    """

    alias = _snapshot_alias(variant_ini)
    cached = _SNAPSHOT_VALIDATION.get(alias)
    if cached is not None:
        return cached

    if alias not in _SNAPSHOT_NATIVE_ALIASES:
        if len(_SNAPSHOT_NATIVE_ALIASES) >= STUDY_MAX_NATIVE_SNAPSHOT_VARIANTS:
            raise StudyVariantCapacityError(
                "Study variant snapshot capacity is exhausted for this server process"
            )
        # Reserve before the irreversible native load begins. Never remove this on
        # failure: load_variant_config() may already have registered the alias.
        _SNAPSHOT_NATIVE_ALIASES.add(alias)

    aliased_ini = replace_variant_section_name(variant_ini, alias)
    validated = validate_catalogued_ini(aliased_ini)
    _SNAPSHOT_VALIDATION[alias] = validated
    return validated


async def validate_study_variant_import_without_mutating_server(
    variant: str,
    variant_ini: str,
    initial_fen: str,
) -> None:
    """Validate an untrusted embedded Study snapshot/root outside the server process.

    Move-tree legality is already validated by ffish.js before bulk Study import. Keep
    the isolated server-side admission check focused on the untrusted INI and initial
    FEN so a rejected snapshot cannot mutate the long-lived pyffish registry.
    """

    snapshot_name = extract_variant_name(variant_ini)
    if snapshot_name != variant:
        raise ValueError("Study variant snapshot name does not match chapter variant")
    alias = _snapshot_alias(variant_ini)
    aliased_ini = replace_variant_section_name(variant_ini, alias)
    await check_catalogued_ini_tree_without_mutating_server(aliased_ini, alias, initial_fen, ())


@contextmanager
def study_variant_context(
    app_state: Any,
    variant: str,
    variant_ini: str | None,
) -> Iterator[StudyVariantOptions]:
    """Resolve the engine variant used for an exact saved Study rules snapshot.

    When the saved rules are still the active catalogue definition, use the public
    variant directly. If the live definition has changed or disappeared, use a
    deterministic internal alias because Fairy-Stockfish cannot overwrite variants.
    No global live definition is mutated by this context.
    """

    if not variant_ini:
        yield StudyVariantOptions(runtime_variant=variant)
        return

    try:
        snapshot_name = extract_variant_name(variant_ini)
    except Exception as exc:
        raise ValueError("Invalid Study variant snapshot") from exc
    if snapshot_name != variant:
        raise ValueError("Study variant snapshot name does not match chapter variant")

    active_doc = getattr(app_state, "catalogued_variants", {}).get(variant)
    active_ini = str(active_doc.get("ini") or "") if isinstance(active_doc, Mapping) else ""

    if _same_variant_rules(active_ini, variant_ini):
        runtime_variant = variant
        random_start = catalogued_random_start(
            variant_ini,
            str(active_doc.get("startFen") or ""),
            int(active_doc.get("width") or 0),
            int(active_doc.get("height") or 0),
        )
        show_promoted = (
            bool(active_doc.get("showPromoted", False))
            if isinstance(active_doc, Mapping)
            else False
        )
    else:
        validated = _snapshot_validation(variant_ini)
        runtime_variant = validated.name
        show_promoted = validated.show_promoted
        random_start = catalogued_random_start(
            variant_ini,
            validated.start_fen,
            int(getattr(validated, "width", 0) or 0),
            int(getattr(validated, "height", 0) or 0),
        )

    yield StudyVariantOptions(
        runtime_variant=runtime_variant,
        show_promoted=show_promoted,
        legal_moves_need_history=catalogued_legal_moves_need_history(variant_ini),
        random_start=random_start,
    )


async def study_variant_metadata(app_state: Any, variant: str) -> Mapping[str, Any] | None:
    """Return presentation metadata without applying normal catalogue visibility.

    The owner already possesses a persisted Study snapshot. Catalogue visibility is a
    separate concern, so an archived/private/deleted live entry must not make that Study
    unreadable. This metadata is only used for display hints; rules come from variantIni.
    """

    doc = getattr(app_state, "catalogued_variants", {}).get(variant)
    if isinstance(doc, Mapping):
        return doc
    db = getattr(app_state, "db", None)
    if db is None:
        return None
    found = await db[CATALOGUED_VARIANT_COLLECTION].find_one({"_id": variant})
    return found if isinstance(found, Mapping) else None


def study_variant_client_doc(
    variant: str,
    variant_ini: str,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """Build the client variant definition from the saved Study rules snapshot.

    If the persisted snapshot is still the exact live catalogue definition, reuse the
    already-validated catalogue metadata. Loading a hashed Fairy-Stockfish alias merely
    to rebuild client metadata would otherwise permanently add an unnecessary variant
    definition to the process. Historical/changed snapshots still use the immutable
    alias because their old rules must remain executable.
    """

    if extract_variant_name(variant_ini) != variant:
        raise ValueError("Study variant snapshot name does not match chapter variant")

    meta = metadata or {}
    required_metadata = (
        "startFen",
        "width",
        "height",
        "pieces",
        "kingRoles",
        "pocketRoles",
        "captureToHand",
        "promotionType",
        "promotionRoles",
        "promotionOrder",
        "showPromoted",
        "rulesGate",
        "rulesPass",
        "showCheckCounters",
    )
    use_live_metadata = _same_variant_rules(str(meta.get("ini") or ""), variant_ini) and all(
        key in meta for key in required_metadata
    )

    if use_live_metadata:
        base_variant = str(meta.get("baseVariant") or "")
        start_fen = str(meta["startFen"])
        width = int(meta["width"])
        height = int(meta["height"])
        pieces = list(meta["pieces"])
        king_roles = list(meta["kingRoles"])
        pocket_roles = list(meta["pocketRoles"])
        capture_to_hand = bool(meta["captureToHand"])
        promotion_type = str(meta["promotionType"])
        promotion_roles = list(meta["promotionRoles"])
        promotion_order = list(meta["promotionOrder"])
        show_promoted = bool(meta["showPromoted"])
        rules_gate = bool(meta["rulesGate"])
        rules_pass = bool(meta["rulesPass"])
        show_check_counters = bool(meta["showCheckCounters"])
    else:
        validated = _snapshot_validation(variant_ini)
        base_variant = validated.base_variant
        start_fen = validated.start_fen
        width = validated.width
        height = validated.height
        pieces = validated.pieces
        king_roles = validated.king_roles
        pocket_roles = validated.pocket_roles
        capture_to_hand = validated.capture_to_hand
        promotion_type = validated.promotion_type
        promotion_roles = validated.promotion_roles
        promotion_order = validated.promotion_order
        show_promoted = validated.show_promoted
        rules_gate = validated.rules_gate
        rules_pass = validated.rules_pass
        show_check_counters = validated.show_check_counters

    doc: dict[str, object] = {
        "name": variant,
        "displayName": str(meta.get("displayName") or variant),
        "tooltip": str(meta.get("description") or "Saved Study variant"),
        "ini": variant_ini,
        "baseVariant": base_variant,
        "startFen": start_fen,
        "randomStart": catalogued_random_start(variant_ini, start_fen, width, height),
        "width": width,
        "height": height,
        "pieces": pieces,
        "kingRoles": king_roles,
        "pocketRoles": pocket_roles,
        "captureToHand": capture_to_hand,
        "promotionType": promotion_type,
        "promotionRoles": promotion_roles,
        "promotionOrder": promotion_order,
        "showPromoted": show_promoted,
        "rulesGate": rules_gate,
        "rulesPass": rules_pass,
        "rulesArrowing": bool(meta.get("rulesArrowing", False)),
        "showCheckCounters": show_check_counters,
        "category": "catalogued",
        "author": str(meta.get("author") or ""),
        "source": str(meta.get("source") or CATALOGUED_SOURCE_USER),
        "system": bool(meta.get("source") == "fairy-stockfish-builtin"),
        "visibility": str(meta.get("visibility") or CATALOGUED_VISIBILITY_PRIVATE),
        "archived": bool(meta.get("archived", False)),
        "enabled": True,
        "hasPieceSet": bool(meta.get("pieceSet")),
        "pieceSetDirectional": bool(meta.get("pieceSetDirectional", False)),
        "directionalPieceSet": bool(meta.get("pieceSetDirectional", False)),
        "hasBoard": bool(meta.get("boardSvg")),
    }
    for key in (
        "clientVariant",
        "premoveVariant",
        "pieceFamilyOverride",
        "boardFamilyOverride",
        "pieceNames",
        "betzaPieces",
        "pieceSetRevision",
        "boardRevision",
        "fsfBuiltinVariant",
    ):
        value = meta.get(key)
        if value not in (None, "", {}, []):
            doc[key] = value
    return doc
