# ![Empire chess](https://github.com/pychess/pychess-variants/blob/master/static/icons/empire.svg) Empire Chess

![Empire](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Empire.png)

Empire Chess is a chess variant designed in 2020 by Couch Tomato, third in the series of asymmetric games (although available to play on Pychess later than the fourth game due to unique pieces that were not yet available). The mighty Empire (Gold army) has heard stories of a mighty lady with great powers on the battlefield and has proposed a marriage with its Duke. However, the king of the chess kingdom (black) married her instead. Humiliated, the Kaiser leads the imperial army to teach the Kingdom a lesson! 

The Imperial army is incredibly powerful, with all its pieces stronger than the Royal counterpart as they can all move like queens, but attack like the standard Royal counterparts; the only exception is the counterpart to the Queen, the Duke, which can only attack like a King. For those who have played Orda Chess, this is similar except replace knight movement with Queen movement. 

Another unique feature is the King-Kaiser Faceoff rule, adding more checkmate possibilities (this may be familiar to those who have played Xiangqi or Synochess). 

The game itself is incredibly balanced by engine evaluation (even more than standard chess), with a near 50-50 win ratio for the Kingdom and Empire.
 
## General Rules
1.	Setup is as above.
2.	The Empire (gold) always moves first.
3.  As Imperial pawns start on the third rank, they do not have the option to move two spaces or be captured by en passant. Royal pawns retain the ability to move two spaces initially and to be captured via en passant.
4.	Pawns on either side can only promote to a queen.
5.	**King-Kaiser Faceoff** - The King and Kaiser (the Imperial "king") cannot face each other on any open rank or file without intervening pieces, much like a rook attack. Additionally, the black king cannot castle through a king faceoff.
6.	An additional method of victory is available: called **campmate**. Campmate is achieved by moving one’s king into the final rank without moving into check.
7.	**Stalemate** - loss for the player who can't move (rather than draw as in chess)
8.	**Repetition** - loss for the player who repeats a board position 3 times. Typically this is done through chasing a king or piece.
8.	The Empire cannot castle.
9.	Other rules, including Kingdom moves and [en passant](https://en.m.wikipedia.org/wiki/En_passant), are as in standard international chess.

## Imperial Pieces

There are five new units unique to the Empire: two Soldiers, two Siege Towers, two Eagles, two Cardinals, and one Duke. All Imperial back-rank pieces move like queens but attack like their Royal counterparts. The exception is the Duke, which also moves like a Queen, but attacks like a King.  The Imperial "king" is called a Kaiser (K) and has a different symbol, but the change is purely aesthetic and thematic: it behaves like an orthodox King. 

In these images, green dots represent movement only, while yellow dots represent both movement and capture.

### Soldier (S)
![Soldier](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/EmpireSoldier.png)

The Soldiers replace the two middle Pawns. Soldiers both move and attack either one space forwards or one space to either side. These act as the bodyguards of the Kaiser; they're strongest when paired together. As Soldiers are not Pawns, they *don't* promote.

### Duke (D)

![Duke](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Duke.png)

The Duke is the counterpart to the Queen. It moves like a Queen, but attacks like a King only. This does not make it a weak piece. In the endgame, it is very capable of checkmating the King with help from any other piece, including the Kaiser itself (because of the King-Kaiser Faceoff rule).

### Siege Tower (T)

![Siege Tower](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Tower.png)

The Siege Tower, or Tower for short, moves like a Queen, but attacks like a Rook only. Effectively, this also means that it is a Rook that can also peacefully move like a Bishop. This is the Empire's strongest piece.

### Eagle (E)

![Eagle](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Eagle.png)

The Eagle moves like a Queen, but attacks like a Knight only. The value of an Eagle is very similar to that of a Knight and is consequently the weakest piece in the Empire (outside of Pawns and Soldiers).

### Cardinal (C)

![Cardinal](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Cardinal.png)

The Cardinal moves like a Queen, but attacks like a Bishop only. Effectively, this also means that it is a Bishop that can also peacefully move like a Rook. As this is not colorbound like the Bishop, this is not much weaker than the Siege Tower and is consequently the second strongest piece in the Empire. 

## Piece valuation

Accurate piece values are unknown. However, these are the values used by the version of Fairy Stockfish used to balance the game.

Royal piece	| Value (Early / Late) | Imperial piece | Value (Early / Late)
-- | -- | -- | --
Pawn | 120 / 213	| Pawn | 120 / 213
Queen | 2538 / 2682	| Duke | 1050 / 1150
Bishop | 825 / 915	| Cardinal	| 1225 / 1420
Knight | 781 / 854	| Eagle | 1000 / 1075
Rook | 1276 / 1380	| Tower | 1375 / 1480
 | | | Soldier | 200 / 270
## Strategy
The game is still young, so strategy is still being developed! 

<iframe width="560" height="315" src="https://www.youtube.com/embed/0HqKri2R5ls" frameborder="0" allowfullscreen></iframe>
