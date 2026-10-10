# ![Khans chess](https://github.com/pychess/pychess-variants/blob/master/static/icons/khans.svg) Khan's Chess

![Khans Chess](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Khans.png)

![Legend](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/KhansLegend.png)

Khan's Chess is a chess variant designed in 2023-2024 by Couch Tomato and is essentially a newer version of Orda Chess. Like Orda Chess, this is an asymmetric game where one army has knight movements but otherwise have different capture movements similar to the standard army. There were two main impetuses for creating Khan's Chess, both of which had to do with significant advancements in Fairy Stockfish since Orda's development several years earlier: 1) NNUE (neural network) evaluation demonstrated that at higher levels, Orda Chess was not as balanced as originally thought, and 2) the pawn setup for the Horde in Orda Chess did not fit the Mongol theme. To elaborate, pawns are slow defensive pieces that are very fitting for a medieval European soldier. Mongols were known for almost purely cavalry army and shock tactics. Fairy Stockfish had expanded its functionality to create more custom pieces, allowing for an exponentially larger amount of piece variety. After thorough testing, Khan's Chess took Orda Chess and replaced the pawn and yurt with two new pieces: the scout and khatun (a khatun is basically the khan's wife, a nice analogue to the queen). The new scouts also start on the second rank instead of the first. Regarding the balance, the game is overall fairly balanced based on high-level NNUE testing.

For those familiar with Orda Chess, please just refer to the two new pieces (scout and khatun) for the new rules.
 
## General Rules
1.	Setup is as above. Despite new pieces, the placement of the Horde pieces mirror their chess counterparts.
2.	The only pieces that the sides have in common are the kings (the Horde king is called a khan).
3.	The Kingdom (AKA White) *always moves first*.
4.	The Horde (AKA Gold) cannot castle.
5.	Pawns can promote to any piece as in chess. Scouts can only promote to a khatun.
6.	An additional method of victory is available: called **campmate**. Campmate is achieved by moving one’s king into the final rank without moving into check.
7.	**Stalemate** - loss for the player who can't move (rather than draw as in chess)
8.	Other rules, including repetition are as in chess.

## Horde Pieces
There are five new units unique to the Horde: 8 Scouts, 2 Lancers, 2 Horse Archers, 2 Kheshigs, and 1 Khatun. The Kheshigs are the strongest piece (knight + king movement) and lead each flank, while the Khatun is a fairly weak piece unlike the Queen. 
The Horde’s king is called the Khan and has a different symbol, but is essentially the same as the Kingdom’s King, also using the same abbreviation (K) – the change is purely aesthetic and thematic. 
The Horde's Lancer, Horse Archer, and Khatun are unique in that they capture differently than movement ("divergent" pieces, like the pawn). Remember that the Horde is horse-based, so the Lancer and Horse Archer both move like knights. They capture/check like rooks and bishops, respectively. The Khatun captures/checks like a king. The Kheshig is more traditional in that it captures where it moves; it combines the movements of the knight and king. 

The Scout also has divergent movement, but is better described below.

**Horde** piece	| **Kingdom** “counterpart”	| Movement | Capture/Check
-- | -- | -- | --
Khatun | Queen | Knight | King
Horse Archer | Bishop | Knight | Bishop
Kheshig | Knight | Knight+King | Knight+King
Lancer | Rook | Knight | Rook

Details and diagrams of each piece are below. Green dots represent movement, red dots represent capture, and yellow represents both.

### Scout (S)

![Scout](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Scout.png)
 
The Scout is moves like a knight, but only the forward FOUR squares (as above). Its attacks only one square forward. Because of its limited attack, it cannot create defenses as strong as pawns and is generally considered weaker. However, because it moves much faster, it can threaten promotion very quickly.

Scouts promote on the last rank (like pawns) and can only promote to khatuns.
 
### Khatun (T)

![Khatun](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Khatun.png)
 
The Khatun moves as a knight but captures as a king. This is the weakest of the back rank pieces, but is still very useful, especially on defense.

### Kheshig (H)

![Kheshig](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Kheshig.png)
 
The Kheshig is a hybrid piece that moves and captures as a knight and king combined. This piece type is also generically called the centaur. The kheshig starts in the knight’s spot, but unlike the knight, is the strongest Horde piece. It can be thought of as the general that leads its own troops on each flank. It is generally preferred to keep the kheshigs safely behind during early to mid game because of their extreme importance to the Horde in the endgame.
The kheshigs were the elite imperial guard for the Mongol royalty. Appropriately, it is incredibly difficult for the Kingdom to checkmate the khan without at least eliminating one of his kheshigs first.

### Horse Archer (A)

![Horse Archer](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Archer.png)
 
The Horse Archer, or simply abbreviated Archer, moves as a knight but captures as a bishop. Because the archer is not colorbound, its value is greater than its bishop counterpart.
Horse Archers were one of the two core components of the Mongol cavalry, functioning as the light cavalry. Their speed and prowess as mounted archers made them a unique threat. Their ability to quickly position themselves for a deadly skewer or fork make them a dangerous threat for the Kingdom.
 
### Lancer (L)

![Lancer](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Lancer.png)
 
The Lancer moves as a knight but captures as a rook. Because the lancer is not as mobile as the rook, its value is generally weaker than the rook, and this becomes more pronounced in the endgame, as it cannot move across the board as quickly as a rook can. Its value is still comparable to the horse archer.
Lancers were one of the two core components of the Mongol cavalry, functioning as the heavy cavalry. Despite being weaker than the rook, their ability to come into play much earlier in the game is an advantage that the Horde player should utilize.

