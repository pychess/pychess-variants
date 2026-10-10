# ![Seirawan](https://github.com/pychess/pychess-variants/blob/master/static/icons/schess.svg) S-chess (Seirawan Chess, SHARPER Chess)

S-chess was created by Yasser Seirawan and Bruce Harper in 2007. The game is played on an 8x8 board but adds a twist by adding two new hybrid pieces through the process of gating (introducing the pieces onto the board by replacing vacancies in the back rank). 

## Rules

Unlike the above variants, this is played on a standard 8 x 8 board. The **elephant** is the rook/knight hybrid, while the **hawk** is the bishop/knight hybrid. Both of these pieces instead start off the board, although they are not to be dropped as in Crazyhouse.

Instead, when a piece in a player’s first rank moves for the first time, these pieces may optionally come into the square evacuated by that piece. If all first rank pieces have moved or been captured, then any remaining elephant or hawk cannot be entered into play. For castling, the extra pieces can enter either of the original king or rook squares. The king cannot be in check during this process, similar to castling.

Pawns can also promote to elephants and hawks.

## New Pieces

### Hawk

![Hawk](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Hawk.png)

The hawk (H) is a compound piece combining the moves of the **bishop** and **knight**. In terms of fairy pieces, this is generically known as the princess, but also has other names in different variants.

The hawk is unique in that it is the only piece that can checkmate on its own, which you may be able to appreciate if you look at its movement/attack pattern.

The value of a hawk is considered slightly better than a rook, but less than the elephant and queen.

### Elephant

![Elephant](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ElephantSeirawan.png)

The elephant (E) is a compound piece combining the moves of the **rook** and the **knight**. In terms of fairy pieces, this is generically known as the empress, but also has other names in different variants. 

The value of an elephant is considered better than a hawk, but equivalent to or slightly less than a queen.

## Strategy

Per Yasser Seirawan, protecting the king is even more important in this game because a ranged attack by a back rank piece such as the queen, bishop, or rook, can immediately be supported by an incoming hawk or elephant, in some cases leading to checkmate!
[https://www.pychess.org/blogs/S-chess_ramblings](https://www.pychess.org/blogs/S-chess_ramblings) by catask is recommended for everyone.

Stream of Yasser Seirawan playing against JannLee:

<iframe width="560" height="315" src="https://www.youtube.com/embed/ujWzsxm18aQ" frameborder="0" allowfullscreen></iframe>
