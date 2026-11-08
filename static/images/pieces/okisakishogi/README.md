# Okisaki Shogi pieces

Extracted from the `okisakishogi_` custom piece set uploaded to PyChess by
`brotopskeu_46227`. The SVG artwork is preserved as uploaded; filenames use
Chessground roles (`pn` means promoted knight, for example).

The `kanji` style uses the standard Shogi one-kanji pieces under
`../shogi/ctk/`, including their piece sizes, player-specific kings, red
promotion lettering, and the same CSS drop shadow as Decimal Shogi.

Two additional SVGs use the empty piece base from `../shogi/ctk/0_QUEEN.svg`:

- `n-ctk.svg`: the existing `0_JUMPING_HORSE.svg` glyph (跳), recolored black
  because the Okisaki jumping horse starts unpromoted.
- `q-ctk.svg`: the queen glyph (妃), outlined from Noto Serif CJK JP Bold.
  The character follows the [Okisaki Shogi piece table](https://en.wikipedia.org/wiki/Okisaki_shogi#Table_of_pieces).

The common piece artwork is credited in [the Shogi README](../shogi/README.md).
[Noto CJK](https://github.com/notofonts/noto-cjk) is distributed under the SIL
Open Font License 1.1. The queen is stored as an SVG path and needs no font at
runtime.

All artwork faces the player in its canonical orientation. The piece stylesheet
rotates the image layer for enemy pieces, including after the board is flipped.
