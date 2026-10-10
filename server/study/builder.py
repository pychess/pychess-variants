from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from catalogued_variants import CATALOGUED_SOURCE_FSF_BUILTIN, find_catalogued_variant_doc
from fairy.fairy_board import FEN_OK, FairyBoard, validate_fen
from settings import URI
from utils import MAX_CUSTOM_FEN_LENGTH, load_game, sanitize_fen
from variants import (
    ALL_VARIANTS,
    C2V,
    TWO_BOARD_VARIANT_CODES,
    catalogued_variant_random_start,
    is_catalogued_variant,
)

from study.annotations import StudyAnnotations, StudyComment, canonical_tags
from study.models import (
    StudyChapterMode,
    StudySource,
    study_chapter_mode,
    study_chapter_mode_enabled,
    study_conceal_ply,
)
from study.tree import StudyTree, StudyTreeNode
from study.variant import (
    StudyVariantCapacityError,
    study_variant_context,
    validate_study_variant_import_without_mutating_server,
)

StudyOrientation = Literal["white", "black"]


class StudyChapterBuildError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StudyChapterDraft:
    variant: str
    initial_fen: str
    orientation: StudyOrientation = "white"
    chess960: bool = False
    variant_ini: str | None = None
    mode: StudyChapterMode = "normal"
    conceal_ply: int | None = None
    root: StudyTree = field(default_factory=StudyTree)
    name: str | None = None
    source: StudySource = field(default_factory=StudySource)
    description: str = ""
    tags: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            mode = study_chapter_mode(self.mode)
            conceal_ply = study_conceal_ply(mode, self.conceal_ply, self.root)
        except ValueError as exc:
            raise StudyChapterBuildError(str(exc)) from exc
        if not study_chapter_mode_enabled(mode):
            raise StudyChapterBuildError("Study chapter mode is not enabled")
        if self.root.has_gamebook and not study_chapter_mode_enabled("gamebook"):
            raise StudyChapterBuildError("Interactive lesson data is not enabled")
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "conceal_ply", conceal_ply)


class StudyChapterBuilder:
    def __init__(self, app_state: Any, owner: str) -> None:
        self.app_state = app_state
        self.owner = owner

    async def blank_or_fen(
        self,
        *,
        variant: str = "chess",
        fen: str | None = None,
        chess960: bool = False,
        name: str | None = None,
        orientation: StudyOrientation = "white",
        mode: StudyChapterMode = "normal",
        conceal_ply: int | None = None,
    ) -> StudyChapterDraft:
        variant_ini = await self._variant_snapshot(variant, chess960)
        with study_variant_context(self.app_state, variant, variant_ini) as options:
            if fen and fen.strip():
                valid, initial_fen = self._validated_initial_fen(
                    variant, fen.strip(), chess960, options.runtime_variant
                )
                if not valid:
                    raise StudyChapterBuildError("Invalid FEN for this variant")
            else:
                try:
                    initial_fen = FairyBoard.start_fen(options.runtime_variant, chess960)
                except Exception as exc:
                    raise StudyChapterBuildError("Variant start position is unavailable") from exc
        return StudyChapterDraft(
            variant=variant,
            chess960=chess960,
            initial_fen=initial_fen,
            orientation=orientation,
            variant_ini=variant_ini,
            mode=mode,
            conceal_ply=conceal_ply,
            name=name,
        )

    async def from_game(
        self,
        game_id: str,
        *,
        name: str | None = None,
        mode: StudyChapterMode = "normal",
        conceal_ply: int | None = None,
    ) -> StudyChapterDraft:
        game_id = game_id.strip()
        if not game_id:
            raise StudyChapterBuildError("Game ID is required")
        doc = await self.app_state.db.game.find_one({"_id": game_id})
        if doc is None:
            raise StudyChapterBuildError("Game not found")

        game = await load_game(self.app_state, game_id, cache_finished=False)
        if game is None:
            raise StudyChapterBuildError("Game not found")
        if getattr(game.server_variant, "two_boards", False):
            raise StudyChapterBuildError("Two-board games are not supported by Study yet")

        # get_board(full=True) reconstructs the authoritative saved mainline if this
        # finished game was loaded lazily from MongoDB.
        board_payload = game.get_board(full=True)
        raw_steps = board_payload.get("steps", [])
        if not isinstance(raw_steps, list) or not raw_steps:
            raise StudyChapterBuildError("Saved game has no readable analysis steps")

        nodes: dict[str, StudyTreeNode] = {}
        parent_id: str | None = None
        from study.tree import new_study_node_id

        for raw_step in raw_steps[1:]:
            if not isinstance(raw_step, Mapping):
                raise StudyChapterBuildError("Saved game contains an invalid move step")
            move = raw_step.get("move")
            fen = raw_step.get("fen")
            turn_color = raw_step.get("turnColor")
            if not isinstance(move, str) or not move or not isinstance(fen, str) or not fen:
                raise StudyChapterBuildError("Saved game contains an invalid move step")
            if turn_color not in ("white", "black"):
                raise StudyChapterBuildError("Saved game contains an invalid side to move")
            node_id = new_study_node_id(nodes)
            node = StudyTreeNode(
                id=node_id,
                parent_id=parent_id,
                order=0,
                move=move,
                fen=fen,
                turn_color=cast(StudyOrientation, turn_color),
                check=bool(raw_step.get("check", False)),
                san=str(raw_step["san"]) if raw_step.get("san") is not None else None,
                clocks=self._step_clocks(raw_step),
            )
            nodes[node_id] = node
            parent_id = node_id

        variant_ini = str(doc.get("vini") or "") or None
        if variant_ini is None and is_catalogued_variant(game.variant):
            visible = await find_catalogued_variant_doc(self.app_state, game.variant, self.owner)
            if visible is not None:
                variant_ini = str(visible.get("ini") or "") or None

        default_name = f"{game.wplayer.username} - {game.bplayer.username}"
        initial_fen = str(raw_steps[0].get("fen") or game.initial_fen)
        tags = canonical_tags(
            {
                "Event": "PyChess game",
                "Site": f"{URI}/{game_id}",
                "Date": game.date.strftime("%Y.%m.%d"),
                "White": game.wplayer.username,
                "Black": game.bplayer.username,
                "Result": game.result,
                "WhiteElo": str(game.wrating),
                "BlackElo": str(game.brating),
                **({"WhiteTitle": game.wplayer.title} if game.wplayer.title else {}),
                **({"BlackTitle": game.bplayer.title} if game.bplayer.title else {}),
            }
        )
        return StudyChapterDraft(
            variant=game.variant,
            chess960=bool(game.chess960),
            initial_fen=initial_fen,
            orientation="white",
            variant_ini=variant_ini,
            mode=mode,
            conceal_ply=conceal_ply,
            root=StudyTree(nodes, root_clocks=self._step_clocks(raw_steps[0])),
            name=name or default_name,
            source=StudySource("game", game_id),
            tags=tags,
        )

    async def from_import(
        self,
        *,
        variant: str,
        initial_fen: str,
        tree_payload: Mapping[str, object],
        chess960: bool = False,
        variant_ini: str | None = None,
        name: str | None = None,
        orientation: StudyOrientation = "white",
        mode: StudyChapterMode = "normal",
        conceal_ply: int | None = None,
        description: str = "",
        tags: Mapping[str, str] | None = None,
    ) -> StudyChapterDraft:
        variant = variant.strip().lower()
        if not variant:
            raise StudyChapterBuildError("PGN variant is required")
        initial_fen = initial_fen.strip()
        if not initial_fen:
            raise StudyChapterBuildError("PGN initial FEN is required")
        if len(initial_fen) > MAX_CUSTOM_FEN_LENGTH:
            raise StudyChapterBuildError("PGN initial FEN is too long")

        snapshot = variant_ini if isinstance(variant_ini, str) and variant_ini.strip() else None
        if snapshot is not None:
            server_variant = ALL_VARIANTS.get(variant)
            if server_variant is not None and not is_catalogued_variant(variant):
                raise StudyChapterBuildError(
                    "Built-in variants cannot use an embedded custom rules snapshot"
                )
            try:
                submitted = StudyTree.from_payload(tree_payload)
                await validate_study_variant_import_without_mutating_server(
                    variant, snapshot, initial_fen
                )
                with study_variant_context(self.app_state, variant, snapshot) as options:
                    if chess960 and not options.random_start:
                        raise StudyChapterBuildError(
                            "Embedded custom variant snapshot does not support randomized Chess960 starts"
                        )
                    root = self._canonicalized_client_tree(
                        submitted,
                        comment_author=self.owner,
                        preserve_comment_attribution=True,
                    )
            except (StudyChapterBuildError, StudyVariantCapacityError):
                raise
            except Exception as exc:
                raise StudyChapterBuildError("Embedded PGN variant snapshot is invalid") from exc
        else:
            snapshot = await self._variant_snapshot(variant, chess960)
            with study_variant_context(self.app_state, variant, snapshot) as options:
                valid, sanitized_fen = self._validated_initial_fen(
                    variant, initial_fen, chess960, options.runtime_variant
                )
                if not valid:
                    raise StudyChapterBuildError("Invalid PGN FEN for this variant")
                initial_fen = sanitized_fen
                try:
                    submitted = StudyTree.from_payload(tree_payload)
                    root = self._canonicalized_client_tree(
                        submitted,
                        comment_author=self.owner,
                        preserve_comment_attribution=True,
                    )
                except StudyChapterBuildError:
                    raise
                except Exception as exc:
                    raise StudyChapterBuildError("PGN import tree is invalid") from exc

        return StudyChapterDraft(
            variant=variant,
            chess960=chess960,
            initial_fen=initial_fen,
            orientation=orientation,
            variant_ini=snapshot,
            mode=mode,
            conceal_ply=conceal_ply,
            root=root,
            name=name,
            source=StudySource("import"),
            description=description,
            tags=dict(tags or {}),
        )

    async def from_analysis(
        self,
        *,
        variant: str,
        initial_fen: str,
        tree_payload: Mapping[str, object],
        chess960: bool = False,
        game_id: str | None = None,
        name: str | None = None,
        orientation: StudyOrientation = "white",
        mode: StudyChapterMode = "normal",
        conceal_ply: int | None = None,
        tags: Mapping[str, str] | None = None,
    ) -> StudyChapterDraft:
        source_game = await self._analysis_source_game(game_id, variant, chess960)
        source_snapshot = str(source_game.get("vini") or "") if source_game is not None else ""
        variant_ini = source_snapshot or await self._variant_snapshot(variant, chess960)
        with study_variant_context(self.app_state, variant, variant_ini) as options:
            if source_game is not None and source_snapshot:
                # A finished game's analysis was produced under the game's saved rules,
                # which may no longer be the live catalogue definition. In that case do
                # not validate its root FEN through today's public variant. Require the
                # authoritative saved game root instead and validate/replay all moves
                # below through the immutable Study snapshot alias.
                saved_initial_fen = str(source_game.get("if") or "") or FairyBoard.start_fen(
                    options.runtime_variant, chess960
                )
                if initial_fen.strip() != saved_initial_fen:
                    raise StudyChapterBuildError("Analysis start FEN does not match source game")
                sanitized_fen = saved_initial_fen
            else:
                valid, sanitized_fen = self._validated_initial_fen(
                    variant, initial_fen.strip(), chess960, options.runtime_variant
                )
                if not valid:
                    raise StudyChapterBuildError("Invalid analysis start FEN")
            try:
                submitted = StudyTree.from_payload(tree_payload)
                root = self._canonicalized_client_tree(
                    submitted,
                    comment_author=self.owner,
                )
            except StudyChapterBuildError:
                raise
            except Exception as exc:
                raise StudyChapterBuildError("Analysis tree is invalid") from exc

        try:
            normalized_tags = canonical_tags(tags or {})
        except (TypeError, ValueError) as exc:
            raise StudyChapterBuildError("Analysis PGN tags are invalid") from exc

        source = StudySource("game", game_id) if game_id else StudySource()
        return StudyChapterDraft(
            variant=variant,
            chess960=chess960,
            initial_fen=sanitized_fen,
            orientation=orientation,
            variant_ini=variant_ini,
            mode=mode,
            conceal_ply=conceal_ply,
            root=root,
            name=name,
            source=source,
            tags=normalized_tags,
        )

    async def _analysis_source_game(
        self, game_id: str | None, variant: str, chess960: bool
    ) -> Mapping[str, object] | None:
        if not game_id:
            return None
        doc = await self.app_state.db.game.find_one({"_id": game_id})
        if not isinstance(doc, Mapping):
            raise StudyChapterBuildError("Source game not found")

        code = str(doc.get("v") or "")
        source_variant = C2V.get(code, code)
        if source_variant != variant:
            raise StudyChapterBuildError("Analysis variant does not match source game")
        if code in TWO_BOARD_VARIANT_CODES:
            raise StudyChapterBuildError("Two-board games are not supported by Study yet")

        raw_chess960 = doc.get("z", 0)
        try:
            source_chess960 = bool(int(raw_chess960))
        except (TypeError, ValueError):
            source_chess960 = bool(raw_chess960)
        if source_chess960 != chess960:
            raise StudyChapterBuildError("Analysis mode does not match source game")
        return doc

    @staticmethod
    def _validated_initial_fen(
        variant: str,
        initial_fen: str,
        chess960: bool,
        runtime_variant: str,
    ) -> tuple[bool, str]:
        if is_catalogued_variant(variant):
            # Generic sanitize_fen() deliberately carries first-class-variant
            # assumptions such as king counts and pieces derived from the start
            # position. Catalogued variants can legitimately violate those
            # assumptions (Joust and Amazons have no kings, for example), so the
            # loaded Fairy-Stockfish definition is the authoritative validator.
            if len(initial_fen) > MAX_CUSTOM_FEN_LENGTH:
                return False, ""
            return validate_fen(initial_fen, runtime_variant, chess960) == FEN_OK, initial_fen
        return sanitize_fen(variant, initial_fen, chess960)

    @staticmethod
    def _step_clocks(step: Mapping[str, object]) -> tuple[int | float, int | float] | None:
        raw = step.get("clocks")
        if raw is None:
            return None
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            raise StudyChapterBuildError("Saved game contains invalid clock data")
        values: list[int | float] = []
        for value in raw:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value < 0
                or not math.isfinite(value)
            ):
                raise StudyChapterBuildError("Saved game contains invalid clock data")
            values.append(value)
        return values[0], values[1]

    async def _variant_snapshot(self, variant: str, chess960: bool) -> str | None:
        server_variant = ALL_VARIANTS.get(variant)
        if server_variant is None:
            raise StudyChapterBuildError("Unknown variant")
        if server_variant.two_boards:
            raise StudyChapterBuildError("Two-board variants are not supported by Study yet")
        if is_catalogued_variant(variant):
            if chess960 and not catalogued_variant_random_start(variant):
                raise StudyChapterBuildError("Catalogued variants do not support Chess960 mode")
            doc = await find_catalogued_variant_doc(self.app_state, variant, self.owner)
            if doc is None:
                raise StudyChapterBuildError("Variant is unavailable")
            ini = str(doc.get("ini") or "")
            if not ini:
                # Fairy-Stockfish catalogue built-ins are metadata-only entries.
                # Their rules already live in the engine binary, so there is no INI
                # to snapshot (the same way normal built-in variants store none).
                if doc.get("source") == CATALOGUED_SOURCE_FSF_BUILTIN:
                    return None
                raise StudyChapterBuildError("Variant rules snapshot is unavailable")
            return ini
        return None

    @staticmethod
    def _canonicalized_client_tree(
        tree: StudyTree,
        *,
        comment_author: str,
        preserve_comment_attribution: bool = False,
    ) -> StudyTree:
        """Accept browser-derived chess data while enforcing cheap server invariants.

        Bulk Study creation/import is already fully replayed with ffish.js in the
        browser. Replaying every node again with pyffish would monopolize the aiohttp
        event loop, especially for history-dependent variants. The server therefore
        treats move/FEN/SAN/check data as client-derived cache here, while retaining
        structural/resource checks and authenticated comment authorship. Interactive
        single-move mutations remain server-authoritatively validated.
        """

        rebuilt: dict[str, StudyTreeNode] = {}
        for submitted in tree.nodes.values():
            if len(submitted.fen) > MAX_CUSTOM_FEN_LENGTH:
                raise StudyChapterBuildError("Study node FEN is too long")
            fields = submitted.fen.split()
            if len(fields) < 2 or fields[1] not in ("w", "b"):
                raise StudyChapterBuildError("Study node FEN has invalid side to move")
            fen_turn = "white" if fields[1] == "w" else "black"
            if submitted.turn_color != fen_turn:
                raise StudyChapterBuildError("Study node FEN/turn mismatch")

            rebuilt[submitted.id] = StudyTreeNode(
                id=submitted.id,
                parent_id=submitted.parent_id,
                order=submitted.order,
                move=submitted.move,
                fen=submitted.fen,
                turn_color=submitted.turn_color,
                check=submitted.check,
                san=submitted.san,
                san_san=submitted.san_san,
                eval_score=submitted.eval_score,
                clocks=submitted.clocks,
                force_variation=submitted.force_variation,
                annotations=StudyChapterBuilder._canonical_annotation_authors(
                    submitted.annotations, comment_author, preserve_comment_attribution
                ),
                gamebook=submitted.gamebook,
            )

        return StudyTree(
            rebuilt,
            root_annotations=StudyChapterBuilder._canonical_annotation_authors(
                tree.root_annotations, comment_author, preserve_comment_attribution
            ),
            root_gamebook=tree.root_gamebook,
            root_eval_score=tree.root_eval_score,
            root_clocks=tree.root_clocks,
        )

    @staticmethod
    def _canonical_annotation_authors(
        annotations: StudyAnnotations,
        comment_author: str,
        preserve_attribution: bool = False,
    ) -> StudyAnnotations:
        if not annotations.comments:
            return annotations
        return StudyAnnotations(
            shapes=annotations.shapes,
            comments=tuple(
                StudyComment(
                    comment.id,
                    comment_author,
                    comment.text,
                    comment.source_author if preserve_attribution else None,
                    comment.source_author_id if preserve_attribution else None,
                )
                for comment in annotations.comments
            ),
            nags=annotations.nags,
        )
