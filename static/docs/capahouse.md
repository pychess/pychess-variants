# ![Capahouse](https://github.com/pychess/pychess-variants/blob/master/static/icons/CHouse.svg) Capahouse

Capahouse is a custom variant combining the rules of Capablanca chess with the drop rules of Crazyhouse. The same rules apply to both games. As this is considered a derivative of Capablanca chess, please check the Capablanca rules in its separate guide. Crazyhouse rules are as below for a reminder.

## Crazyhouse Rules

Drops can be performed with captured pieces, which would be done in lieu of moving a piece on the board. Drops are annotated with @. So for example, R@e4 means rook drop at e4. The rules for dropping pieces are as follows:

* Drops resulting in immediate checkmate are permitted. Unlike in shogi, this includes pawn drops.
* Pawns may not be dropped on the players' 1st or 8th ranks.
* Pawns that have been promoted and later captured are dropped as pawns.
* Dropped white and black pawns on the 2nd and 7th ranks, respectively, are permitted to make a two-square move as their first move after the drop.
* A dropped rook can't castle.

All other rules are as in Capablanca chess.

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

## Strategy

As in standard crazyhouse, the piece values don't align with the chess piece values, and as in standard crazyhouse, sacrificing material for fast development, attacks on the enemy King, or just for defence, is often wise. Sometimes it is better to reinforce defenders around one's King rather than try to save them. Here we may refer you to sources in standard crazyhouse strategy...
