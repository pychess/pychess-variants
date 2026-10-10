# ![Ouk Chaktrang](https://github.com/pychess/pychess-variants/blob/master/static/icons/cambodian.svg) Ouk Chaktrang

![Ouk Chaktrang](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Makruk.png?raw=true)

*Ouk Chaktrang*, or Cambodian Chess, is the form of chess played in Cambodia. Its rules are similar to *Makruk*, the Thai Chess, with some special opening moves and slight differences. Ouk Chaktrang offers a taste of ancient Chess in its original form before the introduction of modern rules quickened the pace. The game is plenty of fun in its own right with its balance and dynamics. The slightly slower pace can provide a good way to cultivate patience and hone strategic thinking.

## Rules

The general rules are extremely similar to Chess, so this guide will focus on the few differences. The objective is the same: checkmating your opponent's king. The major differences are some pieces having different moves and the starting positions: the pawns start on the third rank, and the king is always on the left side of the player regardless of color. Stalemates are draws, as in chess.

## The Pieces

Cambodian piece names are in parentheses.

### King (*Khon*)

![King](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/King.png?raw=true)

The king moves one square orthogonally or diagonally.

### Queen (*Neang*)

![Queen](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Queen.png?raw=true)

Unlike the queen in chess, the queen is a relatively weak piece that only moves one square diagonally.

The queen is worth about 1.5 to 2 pawns in general. The queen is a good piece to lead the attacks, useful for harassing more valuable enemy pieces. On occasion, they can also be sacrificed in exchange for well-positioned enemy pawns, to make way for the invasion.

### Bishop (*Koul*)

![Bishop](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Bishop.png?raw=true)

The bishop moves one square diagonally or one square forward, just like the silver general in shogi.

The bishop is a powerful piece for controlling squares immediately in front of it, and for shouldering off enemy forces. It is also a good defender around its King.
 
The bishop is worth more than the queen, but generally not as much as a knight. The justification may be that isolated knights have little trouble escaping from an enemy king, while isolated bishops can fall.
 
Bishops can sometimes prove slow/awkward to maneuver or retreat. It is therefore advisable to have some friendly pieces nearby to support and rescue them. In the endgame, it's usually safer to get a lone king behind the enemy bishop, compared to staying in its front.

### Knight (*Ses*)

 ![Knight](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Knight.png?raw=true)

The knight moves exactly the same as in chess.

The knights are not "minor pieces" in Ouk Chaktrang. They are major forces. Centralize and utilize them.

### Rook (*Touk*)

 ![Rook](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Rook.png?raw=true)

The rook moves exactly the same as in chess.

In the absence of mighty chess queens, the rooks dominate the board. Lateral rook checks can be especially annoying. Aim for the seventh rank or even the sixth rank.

### Pawn (*Trey*)

|   |   |
--- | ---
![Pawn](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Pawn.png?raw=true) | ![ProPawn](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/ProPawn.png?raw=true)

The pawn moves and attacks the same as in chess. However, there is no double-step first move. Pawns promote and move like queens when they reach the sixth rank.

Since it is rare for one side to be up by two pieces, the promoted pawn is commonly present in most endgames, assisting the stronger side in delivering checkmate.
 
For the disadvantaged side, a promoted pawn is a good decoy which must be trapped and captured before the bare king can be forced into checkmate. It can either stay near the king for additional protection, or failing that, lead enemy pieces away from it. Scattering the enemy pieces in this fashion can cost them valuable time to reorganize, thus giving the defending side some extra chance to draw the game under counting rules (see below).

## Special opening moves

### The king's special move

![King's Jump](https://github.com/pychess/pychess-variants/blob/master/static/images/OukGuide/kingleap.png)

During its first move, the king can jump like a knight to the second row. This move cannot capture and cannot be performed while in check.

![Rook's Aiming](https://github.com/pychess/pychess-variants/blob/master/static/images/OukGuide/rookaim.png)

Furthermore, if an enemy rook moves into the same rank or file as the king, "indirectly attacking" it, it *permanently* loses this ability. The king can no longer jump even if the rook moves away afterwards.

### The queen's special move

![Met's Jump](https://github.com/pychess/pychess-variants/blob/master/static/images/OukGuide/metleap.png)

During its first move, the queen can jump two squares forward. This move cannot capture.

## Counting Rules

To prevent the games from going on forever, there are rules that will declare the game a draw if it does not end in a certain number of moves, similar to Chess's 50-move rule. The maximum number of moves allowed will be called the **limit**.

During the endgame, one of the players will most likely have some advantage and be the one trying to win, *chasing* the other's king into checkmate, while the other player try to *escape* with a draw. For the purpose of this rule document the player with advantage will be called the **chasing player**, while the one with disadvantage will be called the **escaping player**.

In real over-the-board games, the escaping player verbally counts their moves. On PyChess, the current count and the limit are shown on the escaping player's side.

The chasing player has to win before the count **reaches** the limit. Otherwise, the game is declared a draw.

### Board's Honor Counting

When one of the players **has three or less pieces** left, that player may start the board's honor counting. The count **starts from 1**, and the counting **limit is 64**.

The player may choose to stop counting at any time, but if either player wants to start counting again, the count will restart from 1. While the escaping player is counting, the chasing player may declare the game a draw at any time. If the player who does the counting somehow checkmates the other player and did not stop counting, the game is declared a draw.

### Piece's Honor Counting

When there are **no unpromoted pawns left** on the board, and one of the players has **only the king left**, that player may start the piece's honor counting. The escaping player also **has the option to not start** the piece's honor counting and continue the board's honor counting instead. On PyChess, the system will automatically choose the way that will reach the limit in less number of moves.

The count **starts from the number of pieces left** on the board, including both kings, plus one. The counting **limit is based on the material advantage** of the chasing player, determined by the minimum number among these conditions:
* If there are two rooks: 8
* If there is one rook: 16
* If there are two bishops: 22
* If there are two knights: 32
* If there is one bishop: 44
* If there is one knight: 64
* If there are only (any number of) queen and promoted pawns: 64

Once the piece's honor counting is started, the limit is set in stone, and it will not change no matter what, even if the pieces on the board get captured afterwards.
For example, if White has two rooks against a lone black king, the piece's honor counting will go from 5 to 8. If Black then captures one of the white rooks, the count does not restart, nor is the limit recalculated. The game is still drawn after Black counts to 8.

## Strategy
 
The pace is rather slow, with most pieces stepping only one square at a time. It's a good idea to organize and group together the pieces. Move them in formation as a group to provide mutual support. Do not try to open up the game on too many fronts. Coordination is key.

## Tactics
 
**Rooks are the only pieces that can pin or skewer pieces. The rest of the tactics mostly consist of forks.**

Most Ouk Chaktrang games will actually reach the bitter (near) end.
When one side has only a bare King remaining, there are certain "counting rules" (see above) which come into effect and put pressure on the stronger side. Such requirements offer the weaker side an incentive to play out the whole game. Therefore it is crucial to master all the basic checkmates against a lone King. There just isn't much point in playing these games if one can't finish off the bare King at the end.
 
Because there is no promotion to heavy pieces, it becomes harder to force a checkmate after the existing pieces have left the board. Plan accordingly and leave yourself with enough firepower.
 
Please allow yourself enough time on the clock, as many of those mates require precision.

[https://thechesspolyglot.netlify.app/2020/04/21/knf-v-k/](https://thechesspolyglot.netlify.app/2020/04/21/knf-v-k/) by Illion is recommended for everyone.

## Reference

[The Ouk Chaktrang Championship, Pre-South East Asia Game 32nd 2023 in Cambodia](https://docs.google.com/document/d/1adppJ66vonM27UYwC-KyldXl7oZ_5Pb0/edit?usp=sharing&ouid=116281580550740302191&rtpof=true&sd=true)
<iframe width="560" height="315" src="https://www.youtube.com/embed/WmMw97hp8C0" frameborder="0" allowfullscreen></iframe>
