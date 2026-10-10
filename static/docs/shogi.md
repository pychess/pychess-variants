# ![Shogi](https://github.com/pychess/pychess-variants/blob/master/static/icons/shogi.svg) Shogi

![Boards](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Boards.png)

*Shogi* (将棋), or Japanese Chess is a classic board game native to Japan and descended from Chaturanga, the same ancestor as Chess. In its modern form, it has been around since the 16th century. The game is very popular in Japan, where it is more played than western chess and there is a thriving professional scene. The game itself is similar yet very distinct from western chess, introducing the ability to drop captured pieces back onto the board. 

## Why learn Shogi?

If you enjoy Chess, Shogi is definitely worth trying. While slightly slower paced and longer than Chess, the game is also more dynamic and complex, leading to a very different experience. Shogi is between Chess and Go in terms of complexity, but don’t let that deter you. As with other chess variants, improving your skills in Shogi can also improve your skills in Chess as well as open up new ways of thinking! [See here for more about that.](https://chessbase.in/news/peter-heine-nielsen-on-shogi)

## Rules

The rules are similar to Chess, so this guide will focus on the differences. Shogi is played on a 9 x 9 board. Players take turns moving pieces on a board to checkmate the enemy king. The black player, or *sente* (先手 first player), moves first, followed by white or *gote* (後手 second player), which is the opposite of chess. These colors are just arbitrary and do not reflect the actual color of the pieces. 

A significant difference from Chess but similar to its Crazyhouse variant is that you can drop captured pieces onto the board as a move. There are a few restrictions to dropping, notably with pawns, but otherwise, pieces can generally be dropped anywhere. Additionally, almost all pieces can be promoted. Pieces are promoted upon entering the promotion zone / enemy camp (last three ranks) or moving a piece already in the enemy camp. The piece will then flip over. Captured promoted pieces are returned to their unpromoted side when added to your hand.

## Pieces

This guide will be based on the internationalized set. Traditional sets use Chinese characters, *kanji*, and piece sets come in either a full 2-kanji form or a 1-kanji abbreviated form. As it is now, knowledge of the kanji will be required if you want to utilize all English resources. 

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

While the movement pattern of the silver general may seem confusing at first, the easiest way to remember it is that it moves **one step diagonally in any direction**… or any of the three squares in front. In the internationalized set, the protrusions of the helmet also point in all its directions.

### Knight

![Knights](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Knights.png)

![KnightDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Knight.png)

Similar to a chess knight, but can only move to the two spaces in front, i.e. it can move forward two and sideways one. Like the chess knight, this piece can jump over pieces.

### Lance

![Lances](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Lances.png)

![LanceeDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Lance.png)

A lance can only move forward but in any number of squares (similar to a rook).

### Pawn

![Pawns](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawns.png)

![PawnDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawn.png)

The pawn moves and captures by moving forward one square. This is different than the chess pawn. The pointy hat in the internationalized piece is a reminder.

### Promoted minor pieces

![PSilvers](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PSilvers.png)

![PKnights](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PKnights.png)

![PLances](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PLances.png)

![Tokins](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Tokins.png)

Unlike the dragon king and dragon horse, these do not have special names. The exception is the pawn, which is sometimes called by its Japanese name, *tokin*. As above, they move just like the gold general. Note that the kanji versions are all different stylistic variants of the character for gold.


## Additional Rules

*Drops* - The main exceptions to dropping a piece anywhere are with pawns. 
1) Pawns cannot be dropped in the same file as another one of your unpromoted pawns (promoted are okay). 
2) A pawn drop cannot checkmate, but checks are okay. 
3) The final exception applies to all minor pieces. You cannot drop a piece so that it can’t move, which usually means the last rank… or the last two ranks in the case of a knight.

*Perpetual check* - Repeating check resulting in the same position four times in a row is a loss to the player causing perpetual check. In chess, this results in a draw.

*Repetition* - Similar to the above, repeating the same position (including pieces in hand) results in a draw.

*Timer* - Shogi uses a byo-yomi timer. Once the main clock expires, a player enters byo-yomi. If it is set at 30 seconds, then that player will only have 30 seconds to make his move from then for each of his/her moves or else lose the game on time.

## Notation

There are different notations used, including one in Japanese. We use a form of western notation (Hodges notation) similar to chess.

### Coordinates

One noticeable difference is that the board coordinates are switched from chess. Files are numbered, and ranks are alphabetized. The origin is the bottom left for the white player. However, since most diagrams are oriented for the black player (first player), these will seem to originate from the top right. As an example, the white king is on square 5a.

In the Hoskings notation, only numbers are used. Instead of 5e, someone might say 55 (5th rank, 5th file). This is similar to the Japanese style, which also uses numbers. 

### Pieces

K = king  
G = gold general  
S = silver general  
N = knight  
L = lance  
R = rook  
B = bishop  
P = pawn  
+R or D = dragon king  
+B or H = dragon horse  
+S, +N, +L, +P for the other promoted pieces, respectively.

### Symbols

* Drops are either indicated with a \* (Hodges) or ‘ (Hosking). Here we use \*, so a pawn drop on 5e would be P*5e.
* Moves that end in promotion add a + at the end. A pawn promoting on 1c would be P1c+.
* If you choose to not promote, instead an = goes at the end.
* Checks and checkmates are not notated.

## Resources for Learning Shogi

[Hidetchi’s YouTube channel](https://www.youtube.com/playlist?list=PL587865CAE59EB84A) is an excellent place for beginner and intermediate players, alike. They are in English and very carefully break down the aspects of the game. Please note that like all other resources, you will need to be familiar with the kanji pieces in order to understand the videos (he also introduces the pieces in the beginner videos).

[81dojo.com](http://www.81dojo.com) is a site where you can play internationally against tougher players. However, it does not support correspondence play at this time.

## Strategy

### Piece Values

There is no standard piece value in shogi, unlike chess. However, it's important to keep in mind that values are not worth as much, as losing pieces isn't permanent and position is far more important. That said, there is a basic piece value system, but professional players have also made more specific values; Tanigawa and Satoh's are shown below.

Piece | Basic | Tanigawa | Satoh 
------------ | ------------- | ------------- | -------------
P | 1 | 1 | 1
L | 3 | 5 | 6
N | 3 | 6 | 6
S | 5 | 8 | 10
G | 5 | 9 | 11
B | 7 | 13 | 17
R | 8 | 15 | 19
*H* |  | 15 | 20
*D* |  | 17 | 22
*+P* |  | 12 | 
*+L* |  | 10 | 
*+N* |  | 10 | 
*+S* |  | 9 | 

### Opening Principles

In general, there are two types of opening styles: *static rook* and *ranging rook*. In *static* rook, the rook does not move. Attacks, therefore, are directed on the right side of the board. In *ranging* rook, the rook moves to the left side (typically 2nd to 5th file), shifting the offense to that side of the board.

This difference matters because opening moves (called *joseki*) are classified as one of these two and can drastically change what kind of game is played. Certain static rook openings are meant for enemy static rook openings, while others are directed against ranging rook players.

### Castles

Castles in shogi are defensive formations that take multiple steps to form. Knowledge of castles is essential because weak king defenses can be quickly exploited with drops in your own territory. It is also important to know each castle’s strengths and weaknesses.

As above, castles depend on static / ranging rook matchup. In static rook openings, kings castle to the left. In ranging rook openings, kings castle to the right. There are many, many castles, many of which are covered in Hidetchi’s videos (see below). Here are three of the most important ones to know:

**Yagura (AKA Fortress)**

![Yagura](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Yagura.png)

The Yagura castle is one of the most powerful *static rook* castles, used against static rook. A mnemonic that may be useful for remembering the positions of the generals is “S G | G B”, or perhaps remembering that the king is guarded by the gold general, a strong defensive piece. Yagura is strong at its front, but weak on its edge and side.

For development of the Yagura, remember that generals always move diagonally to be most efficient. There are different josekis for developing the castle, but keep in mind that at any point white can attack and that you may have to react in between your developmental moves. The 24-move standard joseki is as follows (Source: Hidetchi):

1. ☗P-7f
2. ☖P-8d
3. ☗S-6h
4. ☖P-3d
5. ☗P-6f
6. ☖S-6b
7. ☗P-5f
8. ☖P-5d
9. ☗S-4h
10. ☖S-4b
11. ☗G4i-5h
12. ☖G-3b
13. ☗G-7h
14. ☖K-4a
15. ☗K-6i
16. ☖P-7d
17. ☗G5h-6g
18. ☖G-5b 
19. ☗S-7g
20. ☖S-3c
21. ☗B-7i
22. ☖B-3a
23. ☗P-3f
24. ☖P-4d

**Mino Castle**

![Mino Castle](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Mino.png)

The Mino castle is a classic *ranging rook* castle, used against static rook. The king moves to the rook’s starting spot, the left gold moves up+right, and then the right silver moves up to form a “G G S” V formation. This castle is strong to the left but weak to the front and edge.

Example opening for black using a 4th file rook:

* P76
* B77 (protects the 86/8f square) 
* P66 (reject bishop exchange if white opens bishop up)
* R68 (fourth file rook)
* S78 
* K48 -> K38 -> K28
* S38 (silver up)
* G58 (gold up-right)
* P16 (creates escape route for the king)
* P46

After this point, you are free to exchange bishops and as many pieces as you want, including rooks to generate an attack.

**Anaguma**

![Anaguma](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Anaguma.png)

Anaguma (AKA “Bear in the hole”) is another *ranging rook* castle and one of the most impenetrable in the game. However, it takes a long time to form.

**Double Wing Attack**

Not a castle per se, but a *static rook* opening. Both sides advance their rook pawns, leading to an exchange. Part of the joseki is that the silvers must defend the bishop pawns before the enemy pawn reaches its target. Of note, this is AlphaZero’s favorite opening, accounting for more than half of its openings as black.

## Handicaps

Unlike chess and more similar to go, handicaps are a big part of teaching and should not be treated as one player giving pity to another. They are a great way to learn the game, and there are even standard strategies for different types. In Shogi, handicap games are fairly standard, and the most common setups are described below.

While normal games have black (*sente*) starting, **white goes first in handicap games**. White is called *uwate* while black is called *shitate*. Despite the handicap, the material difference can be overcome because of drops. And since there are fewer powerful pieces, black/*shitate* loses a lot more when a piece a captured.

Name | pieces omitted
-- | --
Lance | left lance
Bishop | bishop
Rook | rook
Rook–Lance | rook, left lance 
2-Piece | rook, bishop
4-Piece | rook, bishop, both lances
6-Piece | rook, bishop, both lances, both knights
8-Piece | rook, bishop, both lances, both knights, both silvers
9-Piece | rook, bishop, both lances, both knights, both silvers, left gold
10-Piece | rook, bishop, both lances, both knights, both silvers, both golds

<iframe width="560" height="315" src="https://www.youtube.com/embed/YH63AlxpXkg" frameborder="0" allowfullscreen></iframe>
