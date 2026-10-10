# ![Capahouse960](https://github.com/pychess/pychess-variants/blob/master/static/icons/Capahouse960.svg) Capahouse 960

Capahouse 960 is a custom variant combining the rules of Capablanca chess, Crazyhouse, and Chess 960. As this is considered a derivative of Capablanca chess, please check the Capablanca rules in its separate guide. Crazyhouse and 960 rules are as below for a reminder.

This variant can be played by checking the "Chess960" option when creating a Capahouse game.

## Crazyhouse Rules

Drops can be performed with captured pieces, which would be done in lieu of moving a piece on the board. Drops are annotated with @. So for example, R@e4 means rook drop at e4. The rules for dropping pieces are as follows:

* Drops resulting in immediate checkmate are permitted. Unlike in shogi, this includes pawn drops.
* Pawns may not be dropped on the players' 1st or 8th ranks.
* Pawns that have been promoted and later captured are dropped as pawns.
* Dropped white and black pawns on the 2nd and 7th ranks, respectively, are permitted to make a two-square move as their first move after the drop.
* A dropped rook can't castle.

## 960 Rules

The starting bottom ranks are randomized, but two rules must be followed:

* The bishops must be placed on opposite-color squares.
* The king must be placed on a square between the rooks.

Castling is the other major rule to take note of. Basically, regardless of where the rooks are, if you castle, the end position will be the same as if the rooks were in standard position. For example, a queenside castle will result with the king on the c file and the rook on the d file (notation: 0-0-0).

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

## Clarifications

A king may not castle with a dropped rook.
