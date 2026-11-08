# Board artwork

## Wooden 10×10 Shogi boards

These boards embed unchanged textures from
[Lishogi](https://github.com/WandererXII/lishogi), commit `bb2a645ef3`, under
`ui/@build/static/assets/images/boards/`:

- `Shogi10x10Wood.svg`: `oak.png` (Oak).
- `Shogi10x10Kaya.svg`: `kaya1.jpg` (Kaya wood).

Lishogi's [COPYING.md](https://github.com/WandererXII/lishogi/blob/bb2a645ef3/COPYING.md)
credits its board images to the Lishogi authors, nexxogen, and CouchTomato,
under GNU AGPL version 3 or later.

Each SVG adds an evenly spaced 10×10 grid over the raster wood grain. The
1100×1200 view box gives cells the same proportions as the plain 10×10 Shogi
board. Four star points sit at the intersections three cells from each edge:
(330, 360), (770, 360), (330, 840), and (770, 840).

Each raster texture is embedded so the board is self-contained when used as a CSS
background or exported to PNG. Grid lines and star points remain vector artwork
for sharp rendering at different board sizes.
