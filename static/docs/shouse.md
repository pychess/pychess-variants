# ![S-House](https://github.com/pychess/pychess-variants/blob/master/static/icons/SHouse.svg) S-House

S-House is a custom variant combining the rules of S-Chess (AKA Seirawan or SHARPER chess) with the drop rules of Crazyhouse. The same rules apply to both games with the exception that the Elephant and the Hawk may be entered initially into the game on any vacant square, as a separate move, in the same manner as normal drops in Crazyhouse. As this is considered a derivative of S-chess, please check the rules in its separate guide. Crazyhouse rules are as below for a reminder.

## Crazyhouse Rules

Drops can be performed with captured pieces, which would be done in lieu of moving a piece on the board. Drops are annotated with @. So for example, R@e4 means rook drop at e4. The rules for dropping pieces are as follows:

* Drops resulting in immediate checkmate are permitted. Unlike in shogi, this includes pawn drops.
* Pawns may not be dropped on the players' 1st or 8th ranks.
* Pawns that have been promoted and later captured are dropped as pawns.
* Dropped white and black pawns on the 2nd and 7th ranks, respectively, are permitted to make a two-square move as their first move after the drop.
* A dropped rook can't castle.

## Clarifications

The elephant and hawk are also counted as pieces in hand, so they can be dropped on the board starting from the beginning.

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

As in standard crazyhouse, the piece values don't align with the chess piece values, and as in standard crazyhouse, sacrificing material for fast development, attacks on the enemy King, or just for defence, is often wise. Sometimes it is better to reinforce defenders around one's King rather than try to save them. Here we may refer you to sources in standard crazyhouse strategy...
