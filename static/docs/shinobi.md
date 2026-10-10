# ![Shinobi chess](https://github.com/pychess/pychess-variants/blob/master/static/icons/shinobi.svg) Shinobi Chess

![Shinobi](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Shinobi.png)

Shinobi Chess is a chess variant designed in 2021 by Couch Tomato with help from Fables, fourth in the series of asymmetric games. The Western chess army (“the Kingdom,” black) has invaded the land of the Sakura Clan (pink/sakura). While having mostly weak pieces at the start, the Clan is very resourceful and can instantly recruit and summon allies to defend at a minute’s notice. The Clan starts with many pieces in hand and can drop them on its side of the board in lieu of moving a piece. Furthermore, they can promote upon reaching the far end of the board – these abilities are similar to the game of shogi, with the major exception that captured pieces do not go into a player’s hand, so each drop counts! The game itself was balanced by Fairy Stockfish selfplay.
 
## General Rules
1.	Setup is as above; the Clan player starts with additional pieces in hand.
2.	The Clan (pink/sakura) always moves first.
3.	Clan pieces in hand can only be dropped in the first four ranks (first half of the board).
4.	All minor Clan pieces promote upon reaching the **7th or 8th rank**. Similarly, Kingdom pawns now promote on the 7th rank instead of 8th.
5.	Pawns on either side can only promote to a Captain (see below).
6.	An additional method of victory is available: called **campmate**. Campmate is achieved by moving one’s king into the final rank without moving into check.
7.	**Stalemate** - loss for the player who can't move (rather than draw as in chess)
8.	**Perpetual check** - Repeating check resulting in the same position four times in a row is a loss to the player causing perpetual check. In chess, this results in a draw.
9.	**Repetition** - Similar to the above, repeating the same position results in a draw.
10.	The Clan cannot castle.
11.	Other rules, including Kingdom moves and en passant, are as in standard international chess.

## Clan Pieces

There are five new units unique to the Clan: the Ninja, the Dragon, Lances, Wooden Horses, and Monks. Captains are a new piece available to both sides, but only the Clan starts with one on the board. Do not be intimidated; all these pieces have movements that are very similar to the original chess pieces! The Ninja and Dragon are special pieces more unique pieces to the Clan, while the other new pieces are essentially weaker versions of their Kingdom counterparts. The Ninja, the Dragon, and Captains do not promote. 
The Clan also has access to the Kingdom pieces of the Rook, Bishop, and Knight after promotion.  The Clan’s king is called a Kage (K) and has a different symbol, but the change is purely aesthetic and thematic: it behaves like an orthodox King. Clan Rooks and Bishops look different, but the changes are also aesthetic.

### Captain (C)

![Captain](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ClanCaptain.png)

The Clan starts with one Captain in the Queen's spot. Additional Captains can be obtained by both sides by promoting their pawns at the 7th rank. The Captain has the same movement of a King. Of course, unlike the King, capturing a Captain does not end the game.

### Ninja (J)

![Ninja](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Ninja.png)

The Ninja is a hybrid piece that combines the movements of the bishop and the knight. In many variants, this is also known as the Archbishop. The Ninja is the Clan's strongest piece and is a very tricky piece that can easily penetrate defenses. The Ninja is also the only piece capable of checkmating on its own! The Ninja is slightly weaker than the Queen.

The Ninja does not promote.

### Dragon (D)

![Dragon](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Dragon.png)

The Dragon is a hybrid piece that combines the movements of the rook and king (or for purists, rook and ferz). This is identical to the Dragon King (promoted Rook) in Shogi. The Dragon is weaker than the Ninja but stronger than the Rook.

The Dragon does not promote.

### Lance (L)

![Lance](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Lance.png)

The Lance is like a Rook but can only move straight forward. This is identical to the Lance in Shogi. One Lance starts in hand and can be thought of as a droppable skewer. Because it can't retreat, make sure the drop counts! The Lances that start on the board are much less flexible and serve to control the board. The **Lance promotes to a Rook** upon reaching the 7th (optional) or 8th (mandatory) ranks. The Lance is valued less than the typical minor Kingdom piece; however, it has hidden value in its ability to promote to one of the strongest pieces in the game.

### Wooden Horse (H)

![Wooden Horse](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Horse.png)

The Wooden Horse (or Horse, for short) is like a Knight but can only move to the forward-most two spots. This is identical to the Knight in Shogi. One Horse starts in hand and can be thought of as a droppable fork. Because it can't retreat, make sure the drop counts! The Knights that start on the board can exert pressure similarly but must be moved carefully because they cannot retreat. The **Horse promotes to a Knight** upon reaching the 7th or 8th rank; promotion is mandatory. The Horse is valued less than the typical minor Kingdom piece; however, it has hidden value in its ability to promote to a Knight.

### Monk (M)

![Monk](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Monk.png)

The Monk moves one space diagonally, either forwards or backwards. In other variants, this is also known as a Ferz/Fers. Both Monks start in hand. **Monks may promote into a Bishop upon reaching the 7th or 8th ranks**. The Monk is weaker than the typical minor Kingdom piece; however, it has hidden value in its ability to promote to a Bishop.
 
## Strategy
The game is still young, so strategy is still being developed! Much of the data is currently based on Engine play.

Piece values are difficult to assess given the ability to promote pieces. Please note that Stockfish evaluation may be off at the beginning of the game because of these promotions. However, the game is balanced in terms of outcome.

### Openings

A full analysis has not been performed. However, Fairy Stockfish overwhelmingly opens with **1. J@c3 Nc6**. After that, there is more variance in the openings.
