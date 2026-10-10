# ![Synochess](https://github.com/pychess/pychess-variants/blob/master/static/icons/synochess.svg) Synochess

![Synochess](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Synochess.png)

Synochess is a chess variant designed in 2020 by Couch Tomato. The idea of the game was to create a variant where the western chess army can fight against the xiangqi or Chinese chess army in a fair manner. Given that the circumstances in xiangqi are much different (larger board, overall weaker pieces), this was difficult to achieve without significant boosts to the Chinese-style army. However, this was able to be achieved, without overall losing the feel of xiangqi when playing as the Chinese army. In this game, the white army represents the western chess side and is called the Kingdom, while the red army represents an amalgamation of xiangqi and janggi (Korean chess) and is called the Dynasty. All pieces on the Dynasty side resemble their counterpart in either xiangqi or janggi and should be familiar to those who have played those games.
The name Synochess is based off an earlier name, Sinochess, but it was changed as the Dynasty became less “Sino” (as in Chinese) and more a mixture of Chinese and Korean. Instead, the prefix syn- means together, and the game represents two different historic branches of chess coming together into one.
 
## General Rules
1.	Setup is as above. 
2.	The only pieces that the sides have in common are the kings, knights, and rooks (called chariots on the Dynasty side).
3.	The Kingdom (white) always moves first.
4.	The Dynasty (red) cannot castle.
5.	Kingdom pawns can only promote to their own pieces (queen, rook, knight, bishop). Dynasty soldiers do not promote.

There are five additional rules that new players must be especially aware of! (Aside from learning the new pieces)

1.	**King Faceoff** – As in Xiangqi, **Kings may not face each other (on a file OR rank) without intervening pieces**, as if they were two rooks facing each other. Keep this in mind, as pieces can be pinned in between, or also be supported by the allied king. Additionally, **the white king cannot castle through a king faceoff**.
2.	**Reinforcement Soldiers** – Red starts with two soldiers in hand. Instead of moving a piece on the board, the Dynasty player can drop a soldier onto an open square in rank 5 (Dynasty’s 4th rank), the same rank where the original soldiers start.
3.	**Campmate** – A king that reaches the final rank (without moving into check) wins the game.
4.	**Stalemate** – As in Xiangqi, stalemates are a loss (in Chess, they are a draw).
5.	**Perpetual check** – As in Xiangqi, perpetual checks (repeating the position three times, and all moves in between were checks) are a loss (in Chess, they are a draw).

## Dynasty Pieces
There are four new units unique to the Dynasty: 6 Soldiers (2 start in hand), 2 Cannons, 2 Elephants, and 1 Advisor. 
The Chariots are equal to the Rooks and use the same abbreviation (R) – the difference is purely cosmetic. Similarly, the Kings are the same, but just appear different. Despite the Horse being different in Xiangqi and Janggi, the Dynasty’s version is no different than the Kingdom's Knight and has the same name, moves, and appearance. 
The Dynasty does not have a piece as strong as the Queen; instead, it has more minor pieces than the Kingdom.
Details and diagrams of each piece are below. 

### King (K) and Chariot (R)
![King and Chariot](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/SynoRK.png)

As above, these pieces are purely cosmetic changes. The Chariot is essentially a Rook and uses the same symbol (R).
Keep in mind the King Faceoff rule above for the King.
The Chariot is the strongest piece of the Dynasty.

### Soldier (S)

![Soldier](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Soldier.png)

The Soldier can move either one space forward or one space sideways. It is the exact same as a Xiangqi soldier that has crossed the river and the exact same as a Janggi soldier from the start. The soldier, unlike the pawn, cannot promote.
Because the soldier cannot move backwards, it can only move sideways in the final rank. Avoid putting them in this situation unless it will lead to checkmate or campmate. Soldiers are strongest when paired side to side so that they can protect each other.

### Elephant (E)

![Elephant](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ElephantDynasty.png)
 
The Elephant is a leaping piece that moves diagonally one or two spaces. Because it is a leaper, it can jump over an intervening piece to move or capture on the second space. The piece is essentially a powered-up version of the Xiangqi elephant; it is the exact same as the elephant in another variant, Shako.

### Cannon (C)

![Cannon](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/CannonDynasty.png)
 
The Cannon is a hopping piece. It is essentially a rook that requires an intervening piece (often called a “screen”) to hop over before it can move **or** capture along that line. **A cannon cannot hop over another cannon.** This version of the cannon is the exact same as the one in Janggi. Because it requires another piece to move or capture, the cannon loses value in the endgame.
 
### Advisor

![Advisor](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Advisor.png)

The Advisor moves and captures exactly like a king. Unlike the king, it can be captured. While there is no equivalent piece in Xiangqi or Janggi, there is no palace in Synochess. As such, the Advisor needed to be stronger to protect its king, and one might think of its movements as combining the strength of two Xiangqi advisors to cover all 8 squares.

 
## Piece valuation

Accurate piece values are unknown. However, these are the values used by Fairy Stockfish, noting that they are generic values, not necessarily specific to Synochess.

Kingdom piece	| Value (Early / Late) | Dynasty piece | Value (Early / Late)
-- | -- | -- | --
Pawn | 120 / 213	| Soldier | 200 / 270
Queen | 2538 / 2682	| Advisor | 700 / 900
Bishop | 825 / 915	| Elephant | 700 / 650
Knight | 781 / 854	| Cannon | 700 / 650
Rook | 1276 / 1380	| Knight | 781 / 854
 | | | Chariot | 1276 / 1380

For those who want a more simplified approach, this table may be an approximation.

Kingdom piece	| Value | Dynasty piece	| Value
-- | -- | -- | --
Pawn | 1 | Soldier | 2
Queen	| 9 | Elephant | 2.75
Bishop | 3 | Advisor | 2.75
Knight | 3 | Cannon | 3
Rook | 5 | Knight | 3
 | |  | Chariot | 5

## Strategy
The game is still young, so strategy is still being developed! Much of the data is currently based on Engine play. As with most games, a lot can be learned by playing against a high-level AI, losing, and seeing how you lost!

### Openings

Like Xiangqi, the first few moves of the opening are very limited before the game branches out. In a vast majority (~90%) of games, Stockfish opens up with 1. e3. If white does not start with e3, then b3 is the next most common. Other moves include g3, f3, and c3, but are extremely rare. All other openings for the first move are suboptimal. b3 is the most common second move for white. c3 is also played occasionally. For the third white move, there is much more variation, although Bb2 is by far the most common.
As for the Dynasty, the most common starting move is Nc6 (70%), or to a lesser extent, Nf6 (30%). No other moves are even attempted by Stockfish. The second move either involves advancing the other knight or moving a cannon to a center position (Ce6+ > Cd6) or advancing the other knight. From that point on, the moves branch significantly.

Therefore, the “standard Nc6 opening” is as follows:
1.	e3 Nc6
2.	b3 …Nf6/Ce6+/Cd6

The most common line developing the standard Nc3 opening is the following:

1.	e3 Nc6
2.	b3 Nf6
3.	Bb2 Ee7

For players who may prefer Nf6, the most common line for that is:

1.	e3 Nf6
2.	b3 Ce6+
3.	Be2 Nc6

As in Xiangqi, discovered attacks are very frequent. Make sure to keep an eye out for them!

Also like Xiangqi and perhaps even more so, using kings offensively is important. It is very easy to pin a piece in between the kings. For example, a single pawn in between cannot attack because it is pinned along that file.

The Dynasty player needs to play aggressively. It starts with an advanced position, but overall weaker pieces. It needs to seek trades that are in its favor. Soldiers are worth more than pawns, so the Dynasty should make the Kingdom work hard to remove a soldier. 

As the Dynasty, avoid moving the soldiers too much. Their initial formation is already in an optimal "soldier structure" (a pair of soldiers side-by-side). Slide them to open up or create attacks for your cannons and chariots. Use the reinforcements to replace lost soldiers. If you drop them too early, you only block yourself in.

### Kingdom (white) tips

* **Opening pawn moves – keep them single-step!** – This is more based on an analysis of Stockfish patterns, but your first moves should favor single-step pawn moves rather than double-step ones. This is likely because it’s important to have a solid pawn backbone to take down the pesky Dynasty soldiers.
* **AVOID initiating an exchange for the cannon** – The cannon, while very menacing in the early game, depreciates rapidly throughout the game. In fact, killing the other pieces effectively kills the cannons (if there are no screens, it can’t move effectively), eventually leaving it open to be killed by another piece easily. 
* **Protect the queen!** – The queen is valued even more than in standard chess because it is the one big trump card that the Kingdom has over the Dynasty. If it has to be exchanged, make sure that one of the enemy chariots go down with it.
* **Trade, trade, trade** – This follows the last two tips. If you keep trading, while keeping your queen alive and also not making too many exchanges for cannons, you will be on top. The Dynasty has a complex piece coordination, and that can get broken down the fewer pieces they have. The Kingdom wants a simple, open game, while the Dynasty wants to take advantage of its early open files and soldier screens.

### Dynasty (red) tips

* **Know the pieces' moves!** – This may seem obvious, but a lot of beginners forget that soldiers can move sideways. 
* **Soldier structure – DO NOT MOVE YOUR SOLDIERS** – This may seem counterintuitive compared to regular chess pawns, but soldiers really shouldn’t be moving as part of your development OR for most attacks. The starting positions of your starting four soldiers are actually the strongest formation already. They each defend each other and prevent white from placing pieces anywhere on the 5th file. As such, each pair is probably even worth more than the average minor piece. Keep them there and use them as screens for your cannons to cramp and redirect white’s development as much as possible. Also, despite the words "DO NOT MOVE" in bold capital letters, if you have to, then you obviously have to.
* **Reinforcement soldiers – Use sparingly** – As above, the original pawn structure is already optimal. Adding reinforcements without any need actually damages your structure and ruins your tempo. Use reinforcements when white is about to attack a soldier with a pawn supported by another piece. If instead there is a one-for-one soldier exchange, you can drop a reinforcement afterwards to repair your structure.
* **Trade your cannons ASAP!** – As mentioned in the Kingdom tips above, cannons depreciate rapidly throughout the course of the game. Yes, they can be used for some devastating tactics, but the Dynasty player must acknowledge there is a small window for that (early to midgame). It’s recommended to trade off one of your cannons within the early game (first several moves). This allows the second cannon to move more freely.
* **Activate your chariots** – This tip is similar to basic xiangqi strategy. The Dynasty starts with open chariot files – make sure to use them to get the chariots in the game. Once the enemy rooks come out, this advantage disappears quickly.

### Tactics

**Fool's Mate**

If you are white, avoid this situation. Always eye the cannons.

![Fool's Mate](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/FoolsMate.png)

In this position Ce6+ forces Be5 which leads to Ce4#, in others it could be just mate, or at least force white to block the check with a piece and lose it.

This is part of why 1. e3 is a standard opening. And if not 1. e3, then 2. e3. Afterwards, if a cannon does attack, it can be blocked by a bishop or knight, which will remain pinned for a while. 1. e4 is not recommended because it's actually an empty threat (the pawn is pinned from attacking because of facing kings).

**Queenslayer**

This is an extremely deadly tactic that may end in an inevitable loss for white if not caught. The situation is where a chariot has an open file (which it already starts with), and the cannon has an open path to the first rank square (b1 or g1). That square may or may not contain a knight, but if it's empty, the knight cannot cover it for this to work.

![Queenslayer](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Queenslayer.png)

Once this position happens, the chariot can take the pawn, forcing the rook to retake the chariot. This now exposes the b1/g1 square to the cannon, which will either threaten AND pin the queen if attacking queenside (b1) or skewer the queen by check on the kingside (g1). Either way, the queen is lost. It should noted that the Queenslayer is not an opening line. It's a *tactic* for a certain situation when red's soldiers are shifted to open up the chariot and cannon files. Intentionally aiming to recreate this position by shifting soldiers open will likely be counterproductive for red.

Moveover, this trap can go wrong in 2 ways.

![QueenslayerGoneWrongb1](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/QueenslayerGoneWrongb1.png)

With no pawn on d3 blocking the path of the bishop white can save their queen by going Bb5+. No matter if red takes the bishop or moves the king out of check their cannon no longer hits b1, so white can just recapture the chariot.

![QueenslayerGoneWrongg1](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/QueenslayerGoneWrongg1.png)

Here red tries the same trick on the kingside. After Rxh2, Rxh2 Cxg1+ it seems the queen is lost as white is in check and defending by moving either the king or the bishop would allow Cxd1, except if white goes Bxb5+ red has to get out of check and white has time to move the queen out of the way.
