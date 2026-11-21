# Firi pieces

The Decimal Shogi and Okisaki Shogi styles reuse the existing Firi chess and
Shogi artwork in this directory, including the horse, queen, and elephant.

The following Chu Shogi assets were copied without changes from
[Lishogi](https://github.com/WandererXII/lishogi), commit `bb2a645ef3`, under
`ui/@build/pieces/assets/chushogi/firi/`:

- `0_CHARIOT.svg`, `1_CHARIOT.svg`: reverse chariot, used for Okisaki's two-way lance.
- `0_VERTICALMOVER.svg`, `1_VERTICALMOVER.svg`: vertical mover, used for Decimal's promoted lance.

These files have no individual license notice and fall under Lishogi's default
GNU AGPL version 3 or later, copyright 2019 onwards the Lishogi authors, as
stated in its [COPYING.md](https://github.com/WandererXII/lishogi/blob/bb2a645ef3/COPYING.md).

For these imported files, `0_` is gold and `1_` is silver. The styles match this
to the existing Firi colors: gold for White and silver for Black. The artwork
stays upright when the board is flipped, following the standard Shogi Firi set.

Promoted artwork follows each variant's actual result: Decimal's promoted lance
is a vertical mover and its promoted gold is a drunk elephant. Chu Shogi's own
promoted vertical mover and promoted elephant are different pieces and are not
used for those roles.
