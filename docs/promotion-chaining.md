# Historical promotion-chain variants

Fairy-Stockfish's native undo operation does not restore earlier promoted state
when the same piece promotes repeatedly. This affects engine search and helpers
that push and pop variations. Forward replay of saved UCI moves remains usable.
The Python server's `FairyBoard.pop()` rebuilds from the starting position and does
not use that native undo operation.

The policy lives in `server/catalogued/promotions.py`:

- `has_promotion_chaining()` detects chains, cycles, and self-promotions, including
  inherited mappings.
- `FSF_SUPPORTS_PROMOTION_CHAINING` records whether the deployed native and browser
  engines have verified support.
- `promotion_chaining_requires_replay_only()` derives the restriction from those
  two facts. Callers must use this policy instead of maintaining variant lists.

While support is disabled, uploads and catalogue restoration reject chains. Live
catalogue filtering, seek admission, game creation, and fishnet access also block
them. Historical validation permits chains while retaining all other definition
checks. Historical registration restores disabled, archived metadata without
reactivating the variant. No database archive flags are changed during replay.

The derived `replayOnly` client capability disables engine search, computer
practice, and making new analysis moves. Saved mainline positions, notation, PGN,
and results remain accessible to players and spectators. Navigation uses the
recorded/rebuilt FEN positions rather than pushing and undoing variations.

After an upstream fix, verify promotion chains, cycles, captures, repeated undo,
FEN round trips, SAN variation helpers, and search with the actual deployed
`pyffish`, worker engine, and `ffish-es6` versions. Then change the single support
constant and rerun the regression tests. Restart the server and rebuild the
frontend so runtime and client metadata are regenerated. Archive decisions remain
in effect until an author or administrator explicitly restores a variant.
