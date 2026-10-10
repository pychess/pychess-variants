
# ![Minishogi](https://github.com/pychess/pychess-variants/blob/master/static/icons/minishogi.svg) Minishogi

![Minishogi](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Minishogi.png)

Minishogi is essentially shogi on a 5x5 board. The game was invented (or rediscovered) around 1970 by Shigenobu Kusumoto of Osaka, Japan.

## Rules

As this game is based off shogi, please see the corresponding guide for basic shogi rules first if you are not familiar with them.

The starting setup is as above. Unlike standard shogi, there is no knight or lance. There is only one pawn, a bishop and rook, and one of each general. Promotion is only done in the last rank.

Rules from Shogi are summarized below:

*Drops* - The main exceptions to dropping a piece anywhere are with pawns. 
1) Pawns cannot be dropped in the same file as another one of your unpromoted pawns (promoted are okay). 
2) A pawn drop cannot checkmate, but checks are okay. 
3) The final exception applies to all minor pieces. You cannot drop a piece so that it can’t move, which usually means the last rank… or the last two ranks in the case of a knight.

*Perpetual check* - Repeating check resulting in the same position four times in a row is a loss to the player causing perpetual check. In chess, this results in a draw.

*Repetition* - Repeating the same position four times in a row is a loss to the first player (sente).

*Timer* - Shogi uses a byo-yomi timer. Once the main clock expires, a player enters byo-yomi. If it is set at 30 seconds, then that player will only have 30 seconds to make his move from then for each of his/her moves or else lose the game on time.

## Pieces

This guide will be based on the internationalized set. Traditional sets use Chinese characters, *kanji*, and piece sets come in either a full 2-kanji form, a 1-kanji abbreviated form. As it is now, knowledge of the kanji will be required if you want to utilize all English resources. 

In general, shogi pieces are much more restricted than chess pieces. Minor pieces (i.e. not the rook or bishop) often move forward and not so much backwards.

Regarding promoted pieces, most sets, including the ones used on this site, distinguish them by being colored red. There are two basic rules that will make learning all the pieces **much** less intimidating. All *minor* pieces move like a gold general when promoted. The gold general, therefore, cannot promote. Secondly, the two *major* pieces (rook and bishop), both gain the moves of a king on top of their original moves. The king does not promote.


### King

![BlackKings](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/BlackKings.png)

![WhiteKings](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/WhiteKings.png)

![KingDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/King.png)

The king moves exactly like a chess king: one step in any direction. In kanji piece sets, the king with a dot, 玉將 gyokushō, is the black player, while the king without, 王將 ōshō, is the white player. 

This is the only piece in the internationalized set to maintain its kanji form, 王. In these sets, the color black or white is also depicted in this piece. The wooden set uses a bar below the 王. 

### Rook

![Rooks](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Rooks.png)

![RookDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Rook.png)

The rook moves exactly like a chess rook: any number of squares orthogonally. The international piece depicts a chariot, which refers to the Japanese name “flying chariot.” In English, the name rook is based off the Persian word for chariot. This is the most valuable unpromoted piece in the game, excluding the king.

### Bishop

![Bishops](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Bishops.png)

![BishopDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Bishop.png)

The bishop moves exactly like a chess bishop: any number of squares diagonally. The international piece depicts a traditional hat worn by a Japanese official. The bishop is the second most valuable unpromoted piece in the game, excluding the king.

### Dragon King (Dragon, Promoted Rook)

![Dragons](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Dragons.png)

![DragonDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Dragon.png)

The dragon king is a promoted rook, which gains the king’s moves on top of a rook’s. This is the most valuable piece in the game, excluding the king.

### Dragon Horse (Horse, Promoted Bishop)

![Horses](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Horses.png)

![HorseDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Horse.png)

The dragon horse is a promoted bishop, which gains the king’s moves on top of a bishop’s. This is the second most valuable piece in the game, excluding the king.

Note: While some beginner chess players sometimes call the knight a horse, you can't make that mistake in shogi because they are two completely different pieces!

### Gold General (Gold)

![Golds](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Golds.png)

![GoldDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Gold.png)

While the movement pattern of the gold general may seem confusing at first, the easiest way to remember it is that it moves **one step orthogonally in any direction**… or any of the three squares in front. In the internationalized set, the protrusions of the helmet (including the golden circle symbol) also point in all its directions.

**All promoted minor pieces move exactly like a gold.**

### Silver General (Silver)

![Silvers](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Silvers.png)

![SilverDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Silver.png)

While the movement pattern of the silver general may seem confusing at first, the easiest way to remember it is that it moves **one step diagonally in any direction**… or any of the three square in front. In the internationalized set, the protrusions of the helmet also point in all its directions.

### Pawn

![Pawns](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawns.png)

![PawnDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawn.png)

The pawn moves and captures by moving forward one square. This is different than the chess pawn. The pointy hat in the internationalized piece is a reminder.

### Promoted minor pieces

![PSilvers](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PSilvers.png)

![Tokins](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Tokins.png)

Unlike the dragon king and dragon horse, these do not have special names. The exception is the pawn, which is sometimes called by its Japanese name, *tokin*. As above, they move just like the gold general. Note that the kanji versions are all different stylistic variants of the character for gold.


## Strategy

Due to the smaller board size, the rook and bishop are not as dominant as standard shogi. However, their promotions are still very much threatening.
