
# ![Minixiangqi](https://github.com/pychess/pychess-variants/blob/master/static/icons/Minixiangqi.svg) Minixiangqi

![Minixiangqi](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Minixiangqi.png)

Minixiangqi is essentially xiangqi on a 7x7 board. The game was invented in 1973 by Shigenobu Kusumoto of Osaka, Japan.

As this game is based off xiangqi, please see the corresponding guide for basic xiangqi rules first if you are not familiar with them.

## Rules

The starting setup is as above. Unlike standard xiangqi, there is no river, advisors, or elephants. 

Additionally, unlike Xiangqi, **pawns start with the ability to move sideways**.

As in Xiangqi, stalemate is a **loss** for the player who cannot move.

Also as in Xiangqi, each side has a 3x3 box with diagonal lines called the *Palace.* The King cannot leave the Palace.

## Additional Rules - Perpetual checks and chases

* A player making perpetual checks with one piece or several pieces can be ruled to have lost unless he or she stops such checking.
* The side that perpetually chases any one unprotected piece with one or more pieces, excluding generals and soldiers, will be ruled to have lost unless he or she stops such chasing.
* If one side perpetually checks and the other side perpetually chases, the checking side has to stop or be ruled to have lost.
* When neither side violates the rules and both persist in not making an alternate move, the game can be ruled as a draw.
* When both sides violate the same rule at the same time and both persist in not making an alternate move, the game can be ruled as a draw.

## The Pieces

Please note that the diagrams used are from the Xiangqi guide, where there is a river. There is no river, so you can just ignore it in the images.

### King

![Kings](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Kings.png)

The king (also known by its Chinese name, the **general**) can only move one step orthogonally, and it cannot leave the palace.

*Special rule*: Kings are not allowed to face each other with no piece in between (“General face-off rule”). Consider them as being able to attack each other as rooks (also called “flying generals”). This is useful for setting up checkmates in the endgame.

### Horse

 ![Horses](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Horses.png)
 
 ![Horse movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/HorseDiagram.png)

The horse (also called by its Western name, the **knight**) moves almost exactly like a chess knight. However, instead of the usual “two steps orthogonally, then one to the side” teaching, it’s better to think of it as *one step orthogonally, then diagonally forward in either direction*, like a Y shape. The reason for this is that the knight **can be blocked** if a piece is adjacent to it. That will block off the two endpoints of that Y. Therefore, there can be situations where two horses are targeting each other, but only one can attack while the other is blocked. Strong moves take advantage of blocking the horse and limiting its movement.

### Chariot

 ![Chariots](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Chariots.png)
 
 ![Chariot movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/ChariotDiagram.png)

The chariot (also called by its Western name, the **rook**, and more rarely by its literal modern translation, car) moves exactly like a chess rook: any number of squares orthogonally. This is the most valuable piece in the game, excluding the king.

### Cannon

![Cannons](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Cannons.png)

![Cannon movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/CannonDiagram.png)

The cannon is a unique piece in xiangqi. It can move exactly like the chariot. However, to capture, it needs a piece (friend or foe) in between, called a screen.

### Pawn

![Pawns](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Pawns.png)

![Pawn movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/PawnDiagram.png)

The pawn (also called by its Chinese name, the **soldier**) moves and captures by moving forward one square *or one square sideways in Minixiangqi*. The ability to move sideways is in Minixiangqi as there is no river like in Xiangqi.

## Strategy

The king starts completely immobile and trapped by pieces. This makes the cannon able to checkmate very early if you are not careful. Early moves should try to give the king some breathing room.
