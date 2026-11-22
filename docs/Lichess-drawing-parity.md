# Lichess drawing parity audit

Audited before implementation on 2026-10-19, starting from PyChess
`63bf6bcf840be0009bbabf61f3e7ee1b3bea76f2` (PR #2420). References:

- Lila checkout `/home/tami/lila`, commit
  [`4641264ccba6f9f43b1836d81bbe00e0e1218634`](https://github.com/lichess-org/lila/tree/4641264ccba6f9f43b1836d81bbe00e0e1218634).
  The inspected drawing sources have no local modifications.
- Installed `node_modules/chessgroundx`, version **11.0.0**, including `src/`.
- Read PyChess's repository instructions, `Study.md`, `Learn-Practice.md`, and
  `Study-PGN-import.md`; Lila's repository instructions and contribution policies.

## Comparison before edits

Paths in the Lichess column are relative to Lila; PyChess paths are relative to
this repository. ChessgroundX paths are relative to its installed package.

| Item | Lichess behavior/source | PyChess behavior/source | Exact delta / value of port | Variant risk / decision |
| --- | --- | --- | --- | --- |
| P1: variation highlighting | `ui/analyse/src/autoShape.ts::hiliteVariations`, called by `compute` when `ctrl.showVariationArrows()` permits it; `ctrl.ts::setAutoShapes`, `allowLines`, `visibleChildren`; `fork.ts::ForkCtrl`; `keyboard.ts` | `client/analysis/analysisTreeCtrl.ts::selectTreeFork`, `getTreeMainChildPath`; `client/study/studyView.ts::renderStudyMoveListFooter`; `analysisCtrl.ts::shapeFromMove` draws PVs only | Keyboard fork selection and Study choices already exist, but have no corresponding board drawings. Port the fork drawing behavior and refresh triggers. | Best focused improvement. Use board dimensions and native variant moves, respect visibility and training ownership. Do not copy chessops's 8×8 move parser. |
| P2: on-board NAGs | `ui/lib/src/game/glyphs.ts::annotationShapes`: first four glyphs, SVG stack reversed for paint order, purple label fallback; called by `autoShape.ts::compute` when move annotations are enabled | `client/analysis/glyphs.ts::GLYPH_GROUPS`, `toggleGlyph` already reuse the 24 named upstream glyphs; `client/movelist.ts` renders NAGs; `studySync.ts::setNags`, `studyPgn.ts`, `studyPgnImport.ts` preserve numeric NAGs | Board glyphs are absent. ChessgroundX `src/glyph.ts::glyphToSvg` already provides the renderer, so future work should reuse it. No duplicated board SVG renderer was found to remove. | Defer to a separate change: upstream castling placement hard-codes c/g files and ranks 1/8; variant/960 castling and annotation visibility need validation. Preserve unknown NAGs and root NAGs in storage/export. |
| P3: endgame overlays | `ui/lib/src/game/endgame.ts::endgameShapesForNode`, `endgameResult`, `endgameShapes`, `findKingSquare`; called for last-mainline or terminal-variation nodes by `autoShape.ts::compute` | Inspected `client/roundCtrl.ts::checkStatus` and `client/analysis/analysisCtrl.ts`: textual results/game-end behavior, no equivalent king badge renderer | Would add a feature rather than remove existing duplication. | Leave unchanged. `dests().size === 0` plus check does not establish every FSF outcome; kings may be absent, multiple, or nonstandard roles. No safe generic placement/outcome mapping has been established. |
| P4: check counters | `ui/lib/src/game/material.ts::countChecks`, `view/material.ts::renderMaterialDiff`, and round socket `checkCount` render delivered checks as material-area king icons | ChessgroundX `src/config.ts::readCheckCounters` reads a FEN field matching `digits+digits` in **black+white** order; `src/svg.ts::checkCounterShapes`, `checkCounterSvg`; PyChess passes `variant.kingRoles` from `client/cgCtrl.ts` and `gameCtrl.ts` | Upstream has no equivalent on-royal SVG counter. PyChess's `3check` definition and `5check` alternate start use it; catalogue metadata can also supply check-counter variants. | Keep the renderer. It chooses the last encountered configured royal role of each color, anchors a 32×32 badge at translate(66,0) in square-local SVG coordinates, with a shadow and count-dependent colors. A label would change appearance and geometry without a demonstrated simplification. |

Check-counter rendering is driven by the FEN field, not the PyChess
`showCheckCounters` UI metadata flag. Colors are darkgrey for 0, red `#df5353`
for 1, orange `#e69f00` for 2, and darkkhaki otherwise. Its placement follows
ChessgroundX's orientation-aware square transform and remains above pieces.

## Selected implementation: P1 only

Borrow `hiliteVariations` behavior, `makeShapesFromUci`'s drop/promotion preview
convention, Lichess's variation brush (white, opacity .5, width 12), keyboard
refresh, Study fork hover, and the separate enabled-by-default variation-arrow
preference. Ordinary forks use grey outlines, selected forks blue `#3291ff`.
An existing automatic arrow gets a white selected outline without moving below
pieces or changing its brush/width. New variation SVG drawings use `below: true`.
Gamebook editor preferred/wrong branches use paleGreen/paleRed.

PyChess-specific adaptations:

- `client/analysis/variationShapes.ts` bounds-checks FSF decimal ranks and
  ChessgroundX single-character ranks through 16; it does not project coordinates
  by orientation. Uppercase FSF drop syntax avoids ambiguity with rank 16 (`@`).
  See the [FSF coordinate conventions](https://fairy-stockfish.github.io/chess-variant-standards/#coordinate-notation).
- Preview roles come from the saved child FEN, so promoted drops, promotion,
  demotion and gating suffixes do not depend on chess-only piece assumptions.
  Compound wall moves retain a separate target circle. Same-square pass moves
  retain their source indicator. Unrecognized/out-of-board moves add no drawing.
- Cached engine shapes are copied before highlighting; existing line widths,
  custom SVG anchors and labels survive. Manual drawings remain in `shapes`, not
  `autoShapes`. No PGN, Study mutation payload or synchronization schema changes.
- Existing tree visibility governs fork drawing and keyboard selection. Study's
  extension supplies the two missing upstream decisions: whether lines are
  allowed, and whether this is a gamebook editor. Practice chapters, both conceal
  views, lesson playback/preview, puzzles, fog, and root-only embeds receive no fork arrows.
  Practice/gamebook runtimes continue to own their hint shapes.
- The PNG compositor already copies below-piece SVG layers before pieces; it
  requires no change. Check counters and ChessgroundX itself require no change.

## Remaining differences and limits

This port does not change MultiPV arrow colors/widths, add numbered arrows,
add maneuver arrows, create an opening explorer, or replace PV hover mini-boards.
Ordinary analysis has keyboard fork selection but no Study-style fork footer;
no new footer is introduced. P1 left NAGs and endgame badges to separate follow-ups;
the P2 follow-up is recorded below. Endgame badges remain deferred.

An important limit: the inspected Fairy-Stockfish `src/types.h` LARGEBOARDS build
supports up to 12 files × 10 ranks. The 16×16 checks establish drawing/coordinate
compatibility with ChessgroundX, not legal live play on an unsupported engine
board. Irregular-board legality remains the engine's responsibility; drawings
consume saved legal moves and never infer destinations from chess movement rules.

The audit is pinned to the source above; it is not a claim of pixel equivalence
with the changing production Lichess site. Browser checks use local servers only.

## Verification

Final frontend checks, all passing:

```text
yarn lint
yarn typecheck
yarn dev
yarn md
yarn test --runInBand     # 114 suites, 959 tests
```

New regression coverage is in `tests/variationShapes.test.ts`,
`analysisExtension.test.ts`, `analysisTreeController.test.ts`, and
`studySync.test.ts`: brushes/layers, selected forks, existing PV widths, hover,
visibility, training policies, normal/promoted drops, promotions, gating, pass
moves, compound moves, 9×10/16×16 coordinates, and preservation of existing
custom SVG anchors/labels. Existing PNG, Study synchronization and PGN tests
also pass in the full Node run. No Python/server source changed, so Python
format/lint/type gates and unrelated tournament tests were not run.

Local Chromium acceptance used the existing mock-database Study GUI suite plus
a temporary variant/drawing harness, with this actual command:

```bash
env UV_CACHE_DIR=/tmp/uv-cache PYTHONPATH=server:tests uv run python -m pytest -q -s \
  tests/test_study_gui.py /tmp/test_parity_browser.py -p aiohttp.pytest_plugin \
  -k 'drawings_survive or practice_browser_acceptance or conceal_multiclient or variation_board_feedback or large_board_drawing or standalone_analysis_forks'
```

Result: **12 passed, 3 deselected**. Checked standalone analysis, Study fork
selection/hover, gamebook author colors, Practice/conceal suppression, manual
arrows, chess, Xiangqi, Crazyhouse drops, promotions, both orientations, and
synthetic 16×16 rendering. The three selected existing tests cover drawing
persistence, concealment across clients, and Practice/return-to-analysis.
Only local mock-database servers were used. Deprecation warnings come from
mongomock and the temporary harness's aiohttp handlers.

The browser's served stylesheet chain was recorded and computed styles checked:
below drawings have z-index 0; pieces/manual drawings have z-index 2;
the SVG layers have pointer-events none. Existing shared styles provide the
correct layering; no CSS changes were required. Screenshots and the exported
PNG were inspected. Temporary evidence lives in `/tmp/parity-browser.log`,
`/tmp/test_parity_browser.py`, `/tmp/variation-parity-harness.ts`,
`/tmp/parity-16x16.png`, and `/tmp/pychess-variation-export.png`.

The PNG compositor generated a valid **65,766-byte PNG** containing pieces,
manual drawings and the new below-piece arrows. Chromium's reported download
path was inaccessible to the driver (and `save_as` produced an empty file), so
the inspected artifact was extracted from the generated PNG Blob. This verifies
composition/rasterization; filesystem saving through that driver remains
unverified. No PNG implementation change was made.

The initial sandboxed Node run could not spawn the child processes used by two
Markdown tests; the unrestricted final run above passes all tests. The normal
in-app browser connection was unavailable, so Chromium acceptance used the
repository's existing Playwright launcher with system Chromium.

## P2 follow-up: Show move annotations

Starting from merged P1 (`54e883cb8f9fad3a8219d2747e6166f80d0f95ea`), rechecked
Lila at the same source revision before implementing this separate change.

| Concern | Verified upstream | PyChess delta and decision |
| --- | --- | --- |
| Preference | `ui/analyse/src/settingsCtrl.ts`, `view/settingsView.ts` and `ctrl.ts::showMoveAnnotations`: default-on `showMoveAnnotationsOnBoard`, labelled **Show move annotations** | Add the same browser preference to `client/analysis/analysisSettings.ts`; refresh shapes immediately. |
| Rendering | `ui/lib/src/game/glyphs.ts::annotationShapes`: shared `glyphToSvg(4)`, reversed stacking, purple label fallback | Adapt in `client/analysis/glyphs.ts`, reusing ChessgroundX's SVGs. Numeric unknown NAGs retain their existing `$n` text; no new NAG schema. |
| Visibility | `ctrl.ts::showMoveGlyphs`, `visibleGlyphs`; `autoShape.ts::compute` returns early for computer Practice | Follow existing Study annotation visibility and server-advice filtering. Keep authored Study glyphs when server analysis is hidden; standalone board glyphs follow server-analysis visibility, including during local search. Training/preview never exposes authored badges. |
| Placement | Upstream castling uses c/g1/8; other moves use their destination | Reuse bounded FSF coordinates through 16×16. Resolve castling from saved before/after positions and configured royal roles, including stationary Chess960 kings. Ambiguous castling gets no badge. |
| Native counters | No equivalent on-board counter in Lila | Keep ChessgroundX untouched. On a royal sharing a native counter, reserve its existing slot and limit NAGs to three, avoiding the shared four-slot SVG registry wrapping onto the counter. |

`analysisCtrl.ts::setAutoShapes` composes current-move badges with existing PVs
and fork drawings. Study annotation edits, remote updates, concealment changes,
and incoming server advice refresh the composition. `visibleNags` extracts the
move list's existing advice filter for both consumers. A saved NAG without advice
provenance retains its existing semantics; this change does not infer its origin.

The upstream outer custom-SVG layer allows overflow. Chromium confirmed PyChess's
`static/chessground.css` clipped top-rank badges, so `static/analysis.css` now allows
that overflow within analysis/Study. Piece clipping for Duck's holding square is
unchanged. Served stylesheet chains and computed overflow, z-index and pointer
behavior were inspected in desktop dark and mobile light layouts.

There are no PGN, comment, synchronization-payload, ChessgroundX, check-counter,
endgame or PNG compositor changes. Manual drawings remain separate. Root NAGs
remain stored/exported, without a board badge. Four known glyphs use the upstream
stack; unknown symbols use its label fallback, including its existing shared-corner
placement when combined with other badges.

### P2 verification

All required frontend commands passed:

```text
yarn lint
yarn typecheck
yarn dev
yarn md
yarn test --runInBand     # 115 suites, 983 tests
```

Focused coverage in `boardGlyphs.test.ts`, `analysisBoard.test.ts` and
`studySync.test.ts` checks shared SVG output, stacking, label fallback, visibility
toggles during local analysis, remote edits, training suppression, and immutable
NAGs. Five castling fixtures use real ffish WASM, including Black, stationary
Chess960 and Capablanca; a synthetic fixture checks a nonstandard royal role.
Existing PGN/import/synchronization and PNG tests pass in the full frontend run.
Python/server gates were skipped because no server source changed.

Local mock-database Chromium acceptance used:

```bash
env UV_CACHE_DIR=/tmp/uv-cache PYTHONPATH=server:tests uv run python -m pytest -q \
  /tmp/test_glyph_browser.py /tmp/test_glyph16_browser.py tests/test_study_gui.py \
  -p aiohttp.pytest_plugin \
  -k 'board_glyphs or glyph_16x16 or drawings_survive or practice_browser_acceptance or conceal_multiclient'
```

Result: **12 passed, 3 deselected** (mongomock deprecation warnings only).
The temporary harness covers eight Study cases: chess, unknown-NAG fallback,
Xiangqi, Crazyhouse drop, promotion on the top rank, stationary Chess960 castling,
Capablanca castling and three-check counters. Each checks both orientations and
the preference off/on with manual arrows retained. A two-tab check verifies live
NAG updates. A separate 16×16 harness checks synthetic drawing geometry and label
fallback; it makes no claim of engine support for that board size. The three
existing Study GUI checks cover drawing persistence, Practice/return-to-analysis
and concealed multi-client behavior. Only local servers were used.

Screenshots and the glyph-containing PNG Blob were inspected. As in P1, the Snap
Chromium download path is inaccessible to the driver; this verifies PNG generation
and composition, without claiming filesystem saving through that driver. Temporary
scripts/evidence are in `/tmp/test_glyph_browser.py`, `/tmp/test_glyph16_browser.py`,
`/tmp/glyph16-harness.ts`, `/tmp/glyph-browser-all.log`, `/tmp/glyph-*.png` and
`/tmp/glyph-*-styles.json`.
