# ![Yokai Shogi](https://github.com/pychess/pychess-variants/blob/master/static/icons/YokaiShogi.svg) Yokai Shogi

![Yokai Shogi Board](https://github.com/pychess/pychess-variants/blob/master/static/images/YokaiShogiGuide/YokaiBoard.png)

*Yokai Shogi* (妖怪将棋) is a Shogi variant invented by Couch Tomato in May 2026. The goal was to create a modern Shogi variant that still encapsulates the feel of Shogi but plays differently and also faster. The theme was also established early using Yokai, popular Japanese spirits/monsters/demons entrenched in folklore, mythology, and pop culture. There is also quite a bit of inspiration from Tori Shogi especially with mirrored pieces, but unlike Tori Shogi, Yokai Shogi is played on a standard 9x9 board. One thing that distinguishes Yokai Shogi from many other variants is the use of divergent pieces, pieces that move and capture differently (like the pawn in Chess).

## Rules

The general rules are identical to standard Shogi. The goal remains to checkmate the opponent's "king," called the "onmyoji" in this game (which is purely aesthetic). Like Shogi, captured pieces can be dropped, and like Shogi, the last 3 ranks represent the promotion zone (where pieces can promote when either starting or ending the move in the promotion zone).

## Pieces

Unlike Shogi, there are quite a few pieces that don't promote. This includes the pieces that have mirror versions of themselves, and the Nurikabe, a piece that starts in hand rather than on the board.

All pieces that are capable of promoting are typically represented by their head. Once they promote, they appear as a full (or almost full) Yokai.

Half of the pieces' drawings employ implicit movement guides. The Yokai will typically point to where they can go. Other pieces use explicit movement guides. For example, the Kitsune and Tanuki both have symbols behind the characters showing where they can attack. Yurei and Tengu also employ little symbols to tip you off to their movement.


### Onmyoji (K)

![Onmyoji](https://github.com/pychess/pychess-variants/blob/master/static/images/YokaiShogiGuide/Onmyoji.png)

The Onmyoji (king) moves exactly like a chess king: one step in any direction. Onmyoji were court practitioners; in fantasy, they are often associated with exorcising demons.

### Pawn (P) and Kasa-Obake

![Pawn](https://github.com/pychess/pychess-variants/blob/master/static/images/YokaiShogiGuide/Pawn.png)

The Pawn moves and captures by moving forward one square, just like the shogi pawn. The pawn in Yokai Shogi is a fictional yokai, representing a Shogi piece that has become sentient as a yokai.

The Pawn promotes to the Kasa-Obake, a popular Yokai representing a living umbrella with one eye and one leg. This moves like a gold general in Shogi. The shape of the umbrella also matches the gold general's movement.

### Crimson Oni (C) and Azure Oni (A)

![Onis](https://github.com/pychess/pychess-variants/blob/master/static/images/YokaiShogiGuide/Onis.png)

Onis are Japanese demons, often coming in pairs. ("Azure" and "Crimson" are used to use different notation since R is used by the right Kappa. Feel free to call them "red" and "blue" too). Both Onis move one square in every direction except sideways and diagonally back. The directions they can't move to are shown by the side that lacks a weapon. The blue oni cannot move left or down-left, and the red oni cannot move right or down-right. These do not promote.

### Left Kappa (L) and Right Kappa (R)

![Kappas](https://github.com/pychess/pychess-variants/blob/master/static/images/YokaiShogiGuide/Kappas.png)

Kappas are aquatic demons; in this game, there are two of them that have mirror movement like the Onis. Both Kappas can move any number of squares forward (like a Shogi lance). The left Kappa can move like a bishop that can only go to the right. They can also move one square diagonally in the opposite direction. Likewise, the right Kappa can move like a bishop that can only go to the left and one square diagonally to the right.  Think of these like Silver Generals from standard shogi that have extended range in 3 of their 5 directions. These do not promote. 

### Yurei (Y) and Vengeful Spirit

![Yurei](https://github.com/pychess/pychess-variants/blob/master/static/images/YokaiShogiGuide/Yurei.png)

Yurei are ghosts; they can move up to two squares forward or sideways. If a piece is blocking them, then they still move past that piece (like a ghost) but cannot capture on that second square. Upon promotion, they become a Vengeful Spirit that gains the ability to also move two squares backward. On top of that, they gain the ability to jump anywhere within 2 squares (including a knight jump away) without capturing. 

### Tengu (G) and Dai-tengu

![Tengu](https://github.com/pychess/pychess-variants/blob/master/static/images/YokaiShogiGuide/Tengu.png)

Tengu are flying goblin-like or crow-like demons. They can jump to any of the four squares reachable in front of them as a chess knight jump. Upon promotion, they become a Dai-tengu that moves exactly like a chess knight.


### Kitsune (F) and Nine-tailed Fox

![Kitsune](https://github.com/pychess/pychess-variants/blob/master/static/images/YokaiShogiGuide/Kitsune.png)

Kitsune are supernatural versions of foxes. They can move but not capture as a Rook (any number of squares orthogonally), but can capture as a Bishop (any number of squares diagonally).

Upon promotion, they become the more powerful Nine-tailed fox. They gain King movement (can move or capture any square adjacent to them) on top of their original movement.

### Tanuki (T) and Bake-danuki

![Tanuki](https://github.com/pychess/pychess-variants/blob/master/static/images/YokaiShogiGuide/Tanuki.png)

Tanuki are supernatural versions of their real life versions (tanuki/raccoon dog). They can move but not capture as a Bishop (any number of squares diagonally), but can capture as a Rook (any number of squares orthogonally).

Upon promotion, they become the more powerful a more powerful Tanuki (bake-danuki is just a Youkai name for a shapeshifting tanuki). They gain King movement (can move or capture any square adjacent to them) on top of their original movement.

### Nurikabe (N)

![Nurikabe](https://github.com/pychess/pychess-variants/blob/master/static/images/YokaiShogiGuide/Nurikabe.png)

Nurikabe are barrier monsters. They start in each player's hand and can only move sideways any number of squares. They cannot promote.


## Additional Rules

*Drops* - The main exceptions to dropping a piece anywhere are with pawns. 
1) Pawns cannot be dropped in the same file as another one of your unpromoted pawns (promoted are okay). 
2) A pawn drop cannot checkmate, but checks are okay. 
3) The final exception applies to all minor pieces. You cannot drop a piece so that it can’t move, which usually means the last rank… or the last two ranks in the case of a knight.

*Perpetual check* - Repeating check resulting in the same position four times in a row is a loss to the player causing perpetual check. In chess, this results in a draw.

*Repetition* - Similar to the above, repeating the same position (including pieces in hand) results in a draw.


## Notation

Notation follows that of Shogi; see the document for details. Piece symbols are in parentheses above.

## Strategy

The game is still relatively new, so strategy is far from being developed. However, here are a few tips to get you started:

* The 'animals' (Tanuki and Kitsune) are not nearly as strong as their standard Shogi counterparts. Pay attention to the fact that once they make a capture, they can't go back the same way they came. Consequently, their value isn't particularly high until later in the game when you can promote, at which point they become some of the strongest pieces in the game.
* Similarly, the other yokai are also very strong and not nearly as weak as their standard Shogi counterparts. Aside from pawns, there are no real "weak" pieces and the value depends on the stage of the game. Early on, these pieces may be even more valuable than animals because of their greater flexibility.
* Be mindful of where Nurikabe drops can happen, both where you can find an opening to attack or where the opponent may find an opening in your rank.
