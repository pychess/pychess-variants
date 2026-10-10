# ![Mansindam](https://github.com/pychess/pychess-variants/blob/master/static/icons/mansindam.svg) Mansindam (Pantheon Tale)

_A variant that combines the Shogi's drop rule with strong pieces, and has no draws._

![Mansindam](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/board.png)

![Mansindam](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/promotions.png)

## Pieces
Every piece gains the additional ability to move as a non-royal King when promoted.
### Bo(步)/Pawn(P) 
![Pawn](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/pawn.png)

Moves one square orthogonally forward. Promotes to Guard. (Betza: fW)

### Cho(哨)/Guard(G)
![Guard](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/guard.png)

Moves one square orthogonally or diagonally. (Betza: WF)

### Gi(騎)/Knight(N)
![Knight](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/knight.png)

Moves like a standard Chess Knight, moving to the nearest squares that do not correspond to the same file, rank, or diagonal from its current position. Promotes to Centaur. It can pass pieces on the path as it moves. (Betza: N)

### Wi(衛)/Centaur(E)
![Centaur](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/centaur.png)

Moves like a Knight or Guard. (Betza: WFN)

### Gak(角)/Bishop(B)
![Bishop](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/bishop.png)

Moves any number of squares diagonally. Promotes to Archer. (Betza: B)

### Ma(馬)/Archer(H)
![Archer](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/archer.png)

Moves like a Bishop or Guard. (Betza: BW)

### Bang(方)/Rook(R)
![Rook](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/rook.png)

Moves any number of squares orthogonally. Promotes to Tiger. (Betza: R)

### Yong(龍)/Tiger(T) 
![Tiger](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/tiger.png)

Moves like a Rook or Guard. (Betza: RF)

### Ye(猊)/Cardinal(C)
![Cardinal](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/cardinal.png)

Moves like a Bishop or Knight. Promotes to Rhino. (Betza: BN)

### Seong(聖)/Rhino(I)
![Rhino](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/rhino.png)

Moves like a Bishop, Knight, or Guard. (Betza: BNW)

### Su(首)/Marshal(M)
![Marshal](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/marshal.png)

Moves like a Rook or Knight. Promotes to Ship. (Betza: RN)

### Myeong(名)/Ship(S)
![Ship](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/ship.png)

Moves like a Rook, Knight, or Guard. (Betza: RNF)

### Bun(奔)/Queen(Q)
![Queen](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/queen.png)

Moves like a Bishop or Rook. Does not promote. (Betza: RB)

### Cheon(天)/Angel(A)
![Angel](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/angel.png)

Moves like a Bishop, Rook, or Knight. Does not promote. (Betza: RBN)

### Yang(陽)=Eum(陰)
![King](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/king.png)

Moves one square orthogonally or diagonally. Does not promote. (Betza: K) When called without distinction between Yang and Eum, it is simply called Ok(玉)/King(K). (Therefore, in notation, Yang and Eum are written as 玉/K.)

## Rules

**Basics**
* The player with Yang is called White, and the player with Eum is called Black.
* White moves first and Black moves next. They move alternately until one player is defeated.
* Your piece cannot move to a square where a friendly piece exists. Conversely, if your piece moves to a square where an enemy piece exists, it captures the enemy piece and moves to that square.
* All pieces except the Knight cannot move by jumping over other pieces on their path. (That is, long-range pieces such as Bishop, Rook, etc. that move more than 2 squares in one direction cannot move further than the pieces in their path.)
* There is no passing a turn.
* There is no castling.
* There is no 50-move rule.
* Because it is different from Chess Pawns, there is no two square advance or en passant rule for Mansindam Pawns.

**The King**
* The state in which your King is attacked by opponent's piece is called Check.
* A situation in which there is no way to block or avoid an opponent's check is called a Checkmate. The player who gives checkmate wins.
* At any time, the King cannot move to a square attacked by the opponent's piece.

**Promotion**
* The 7th, 8th, and 9th ranks are called the Enemy camp.
* A piece is promoted when it moves to, from, or within the enemy camp.
* Promotion is mandatory. Therefore, a piece that can be promoted must be promoted.
* On a physical board, this is typically accomplished by flipping the piece upside down, as in Shogi.
* A promoted piece maintains its promoted state until it is captured by an opponent. If a promoted piece is captured by an opponent, the piece returns to the state it was in before promotion.

**Drops**
* Any piece you capture is called a Handpiece (held "in hand" in Shogi terminology).
* Handpieces are placed on a Piece stand (the square plate on which you place the captured piece).
* On your turn, you may place a handpiece on any empty square instead of moving a piece on the board. (This is called Drop.)
* You can only drop one piece on a turn. (Pieces must always be dropped in their pre-promotion state.)
* If you drop a piece in the enemy camp, it is not automatically promoted. Pieces are always dropped in their pre-promotion state. A piece dropped in enemy camp can be promoted only when it is moved after being dropped.
* You can deliver a check or checkmate to your opponent by dropping a piece.

**Pawn Drops**
* Unlike in Shogi, you can deliver checkmate by dropping a Pawn.
* Two or more of your own unpromoted Pawns cannot be placed on the same file. It is called Prohibition of Two Pawns.
* Pawns cannot be dropped to the last (9th) rank. (This rule was created to prevent this, because once a pawn is dropped on the last rank, it can no longer move.)

**Stalemate**
The player who can no longer move or drop pieces loses. (It is called Stalemate.)

**Campmate**
* The player whose King reaches last rank first wins. (It is called Campmate.)
* Obviously, when the King reaches the last rank, that square must not be attacked by an opponent's piece.

**Prohibition of Threefold Repetition**
Neither White nor Black can repeat the same situation three times. Even if it is not repeated in succession, if the same situation is repeated twice in one game, no one can repeat the situation again. (A player who can no longer block or avoid a perpetual check due to the prohibiion of threefold repetition rule also loses.)

**Resignation**
When you resign, you declare resignation by placing your King on your piece stand. You can resign only on your turn.

**Defeat**
Defeat is determined by the following cases.
* When checkmate is delivered to you
* When the opponent's King reaches the last rank (i.e. when campmate is delivered to you)
* When stalemate is delivered to you (i.e., when you cannot move or drop any pieces)
* When you declared resignation
* When you break one or more of all the rules above
* When you break the rules of the tournament (e.g. time forfeit)

**Full Chinese character name of each piece**
The Chinese character names of the pieces are related to each other.
* 步 : 步兵 ⇒ 哨 : 哨兵
* 騎 : 騎士 ⇒ 衛 : 衛士
* 角 : 角行 ⇒ 馬 : 龍馬
* 方 : 方行 ⇒ 龍 : 龍王
* 猊 : 猊下 ⇒ 聖 : 聖下
* 首 : 首相 ⇒ 名 : 名相
* 奔 : 奔王
* 天 : 天馬
* 陽 : 陽陰 / 陰 : 陰陽 = 玉 : 玉將
