# shogi-piece-images
SVG image of Shogi pieces licensed under CC BY-SA. You can find SVG files in the [dist](https://github.com/orangain/shogi-piece-images/tree/master/dist) directory.

<img src="https://orangain.github.io/shogi-piece-images/dist/0FU.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/0KY.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/0KE.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/0GI.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/0KI.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/0KA.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/0HI.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/0GY.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/0OU.svg">

<img src="https://orangain.github.io/shogi-piece-images/dist/0TO.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/0NY.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/0NK.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/0NG.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/0UM.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/0RY.svg">

<img src="https://orangain.github.io/shogi-piece-images/dist/1FU.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/1KY.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/1KE.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/1GI.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/1KI.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/1KA.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/1HI.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/1GY.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/1OU.svg">

<img src="https://orangain.github.io/shogi-piece-images/dist/1TO.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/1NY.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/1NK.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/1NG.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/1UM.svg"> <img src="https://orangain.github.io/shogi-piece-images/dist/1RY.svg">

## Build

Build SVG images in `dist` directory from `original` directory.

```
$ npm install
$ ./build.sh
```

## License

* SVG files in the `original` directory are created by [Hari Seldon](https://commons.wikimedia.org/wiki/User:Hari_Seldon), licensed under [Creative Commons Attribution-Share Alike 3.0 Unported](https://creativecommons.org/licenses/by-sa/3.0/deed.en). See `original/LICENSE`.
* Other SVG files in the `intermediate` and `dist` directory are created by Hari Seldon and modified by orangain, licensed under [Creative Commons Attribution-Share Alike 3.0 Unported](https://creativecommons.org/licenses/by-sa/3.0/deed.en).
* Source code is licensed under MIT License. See `LICENSE`.

## Additional one-kanji pieces

The Okisaki Shogi style shares the standard piece bodies and artwork in `ctk/`.
Its additional pieces use the empty base from `ctk/0_QUEEN.svg`:

- `ctk/0_JUMPING_HORSE_BLACK.svg` uses the 跳 glyph from
  `ctk/0_JUMPING_HORSE.svg`, recolored black for an unpromoted jumping horse.
- `ctk/0_OKISAKI_QUEEN.svg` uses the 妃 queen glyph from the
  [Okisaki Shogi piece table](https://en.wikipedia.org/wiki/Okisaki_shogi#Table_of_pieces),
  outlined from Noto Serif CJK JP Bold.

[Noto CJK](https://github.com/notofonts/noto-cjk) is distributed under the SIL
Open Font License 1.1. The queen is stored as an SVG path and needs no font at
runtime. Both pieces face the player in their canonical orientation; the piece
stylesheet rotates the image layer for enemy pieces.
