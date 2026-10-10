# ![Caparandom](https://github.com/pychess/pychess-variants/blob/master/static/icons/caparandom.svg) Caparandom

**Caparandom**, originally named **Capablanca Random Chess (CRC)**, was designed by **Reinhard Scharnagl**. It combines the 10×8 board and compound pieces of Capablanca Chess with randomized starting positions. All normal Capablanca Chess rules apply except for the randomized back rank and the corresponding castling rules.

PyChess uses Scharnagl's canonical numbering of the 48,000 basic CRC back-rank arrangements. After applying the current start-position criteria below, **12,130 positions** are available for random games. The historical exclusion of positions resembling the Gothic Chess setup is not applied.

This variant can be played by checking the **Chess960** option when creating a Capablanca Chess game.

## Starting Position Rules

The ten pieces on each player's back rank are arranged identically and must satisfy all of these conditions:

* The **queen and archbishop** are placed on opposite-color squares.
* The two **bishops** are placed on opposite-color squares and may not be adjacent.
* The **king** is placed between the two rooks.
* Every **pawn is protected** by at least one piece on the back rank in the initial position.

The pawn-protection condition uses the normal moves of the pieces, including the knight component of the compound pieces: the archbishop moves as bishop + knight, and the chancellor moves as rook + knight.

Every basic arrangement has a canonical **CRC position number from 1 to 48,000** in Scharnagl's numbering scheme. Only the 12,130 positions satisfying the criteria above are selected for new PyChess games.

## Castling

Castling follows the Chess960 principle: the king and rook finish on fixed squares regardless of where they started.

* **Queenside (c-side) castling, 0-0-0:** the king finishes on the **c-file** and the rook on the **d-file**.
* **Kingside (i-side) castling, 0-0:** the king finishes on the **i-file** and the rook on the **h-file**.

As usual, castling is only legal if neither the king nor the involved rook has moved, the required path is clear, and the king does not start in, pass through, or finish in check.

All other rules are as in Capablanca Chess.

## New Pieces

### Archbishop

![Archbishop](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Princesses.png)

Various symbols used for the archbishop. (Note that the hawk is only for Seirawan Chess).

![Archbishop moves](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Archbishop.png)

The archbishop (A) is a compound piece combining the moves of the **bishop** and **knight**. In terms of fairy pieces, this is generically known as the princess, but also has other names in different variants.

The piece is often symbolized with a combination of a knight and bishop; most variants often do not specify how the piece should look otherwise (which is why we offer different piece sets to choose from).

The archbishop is unique in that it is the only piece that can checkmate on its own, which you may be able to appreciate if you look at its movement/attack pattern.

The value of an archbishop is considered slightly better than a rook, but less than the chancellor and queen.

### Chancellor

![Chancellor](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Empresses.png)

Various symbols used for the chancellor. (Note that the elephant is only for Seirawan Chess).

![Chancellor moves](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Chancellor.png)

The chancellor (C) is a compound piece combining the moves of the **rook** and the **knight**. In terms of fairy pieces, this is generically known as the empress, but also has other names in different variants.

The piece is often symbolized with a combination of a knight and rook; most variants often do not specify how the piece should look otherwise (which is why we offer different piece sets to choose from).

The value of a chancellor is considered better than an archbishop, but equivalent to or slightly less than a queen.

## References

* [Capablanca Random Chess — The Chess Variant Pages](https://www.chessvariants.com/contests/10/crc.html)
* [Capablanca-Random-Chess — Wikipedia (German)](https://de.wikipedia.org/wiki/Capablanca-Random-Chess)
