# ![Orda chess](https://github.com/pychess/pychess-variants/blob/master/static/icons/orda.svg) Orda Chess

![Orda](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Orda.png)

![Legend](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/OrdaLegend.png)

Orda Chess is a chess variant designed in 2020 by Couch Tomato. The idea of the game was to create a true asymmetric chess with two different armies. Ralph Betza’s Chess with Different Armies was an inspiration, but the goal was to be a little more streamlined with the theme here. In this case, the theme of the new army is knight-based movement, where most pieces have an element of knight movement. Given the knight (or horse) theme, this was modeled after the Mongol army and named the Horde. In fact, an orda was a military structure for the people of the Steppes, which also gave rise to the English word “horde.” The original chess army is named the Kingdom for contrast. The game itself is incredibly balanced by engine evaluation (even more than standard chess), with a near 50-50 win ratio for the Kingdom and Horde.
 
## General Rules
1.	Setup is as above. Despite new pieces, the placement of the Horde pieces mirrors their chess counterparts.
2.	The only pieces that the sides have in common are the pawns and the kings (the Horde king is called a khan).
3.	The Kingdom (AKA White) *always moves first*.
4.	The Horde (AKA Gold) cannot castle.
5.	As the Horde’s pawns start on the third rank, they do not have the option to move two spaces or be captured by en passant. Kingdom pawns retain the ability to move two spaces initially and to be captured via en passant.
6.	Pawns *on either side* can only promote to a queen or kheshig.
7.	An additional method of victory is available: called **campmate**. Campmate is achieved by moving one’s king into the final rank without moving into check.
8.	Other rules, including stalemate and repetition, are as in chess.

## Horde Pieces
There are four new units unique* to the Horde: 2 Lancers, 2 Horse Archers, 2 Kheshigs, and 1 Yurt (* exception being that the Kingdom can still obtain a Kheshig by promotion). The Kheshigs are the strongest piece (knight + king movement) and lead each flank, while the Yurt is a fairly weak piece, unlike the Queen. 
The Horde’s king is called the Khan and has a different symbol, but is essentially the same as the Kingdom’s King, also using the same abbreviation (K) – the change is purely aesthetic and thematic. 
The Horde's Lancer and Horse Archer are unique in that they capture differently than movement ("divergent" pieces, like the pawn). Remember that the Horde is horse-based, so the Lancer and Horse Archer both move like knights. They capture/check like rooks and bishops, respectively. The Kheshig is more traditional in that it captures where it moves; it combines the movements of the knight and king. Similarly, the Yurt also captures the same way it moves, which is like the silver general in Shogi.

**Horde** piece	| **Kingdom** “counterpart”	| Movement | Capture/Check
-- | -- | -- | --
Yurt | Queen | “Silver” | “Silver”
Horse Archer | Bishop | Knight | Bishop
Kheshig | Knight | Knight+King | Knight+King
Lancer | Rook | Knight | Rook

Details and diagrams of each piece are below. Green dots represent movement, red dots represent capture, and yellow represents both.
 
### Yurt (Y)

![Yurt](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Yurt.png)
 
The Yurt moves and captures one space diagonally or one space forward. This is the same as a silver general from Shogi or the bishop/khon from Makruk. There is only one yurt, starting in the queen’s spot, but unlike the queen, it is very much a minor piece, the weakest piece in the game aside from a pawn. It should not be underestimated though, because it is one of the few Horde pieces that can move and capture the same way. The other two are the Khan and Kheshig, which are the two most valuable pieces. Therefore, the yurt has the unique role of reliably supporting pawns and other pieces without fear of retaliation.
A yurt is a mobile home for Mongol and Turkic peoples in the steppes of Asia. Their limited mobility but importance for supporting the army is reflected in this piece.

### Kheshig (H)

![Kheshig](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Kheshig.png)
 
The Kheshig is a hybrid piece that moves and captures as a knight and king combined. This piece type is also generically called the centaur. The kheshig starts in the knight’s spot, but unlike the knight, is the strongest Horde piece. It can be thought of as the general that leads its own troops on each flank. It is generally preferred to keep the kheshigs safely behind during early to mid-game because of their extreme importance to the Horde in the endgame.
The kheshigs were the elite imperial guard for the Mongol royalty. Appropriately, it is incredibly difficult for the Kingdom to checkmate the khan without at least eliminating one of his kheshigs first.

### Horse Archer (A)

![Horse Archer](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Archer.png)
 
The Horse Archer, or simply abbreviated Archer, is a unique divergent piece that moves and attacks differently. The archer moves as a knight but captures as a bishop. Because the archer is not colorbound, its value is greater than its bishop counterpart.
Horse Archers were one of the two core components of the Mongol cavalry, functioning as the light cavalry. Their speed and prowess as mounted archers made them a unique threat. Their ability to quickly position themselves for a deadly skewer or fork makes them a dangerous threat for the Kingdom.
 
### Lancer (L)

![Lancer](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Lancer.png)
 
The Lancer is a unique divergent piece that moves and attacks differently. The lancer moves as a knight but captures as a rook. Because the lancer is not as mobile as the rook, its value is generally weaker than the rook, and this becomes more pronounced in the endgame, as it cannot move across the board as quickly as a rook can. Its value is still comparable to the horse archer.
Lancers were one of the two core components of the Mongol cavalry, functioning as the heavy cavalry. Despite being weaker than the rook, their ability to come into play much earlier in the game is an advantage that the Horde player should utilize.

 
## Piece valuation

Accurate piece values are unknown. However, these are the values used by Fairy Stockfish, noting that they are generic values, not necessarily specific to Orda chess.

Kingdom piece	| Value (Early / Late) | Horde piece | Value (Early / Late)
-- | -- | -- | --
Pawn | 120 / 213	| Pawn | 120 / 213
Queen | 2538 / 2682	| Yurt | 630 / 630
Bishop | 825 / 915	| Horse Archer	| 1100 / 1200
Knight | 781 / 854	| Kheshig | 1800 / 1900
Rook | 1276 / 1380	| Lancer | 1050 / 1250

For those who want a more simplified approach, this table may be an approximation.

Kingdom piece	| Value | Horde piece	| Value
-- | -- | -- | --
Pawn | 1	| Pawn | 1
Queen	| 9	| Yurt | 2
Bishop | 3 | Horse Archer | 4
Knight | 3 | Kheshig | 7
Rook | 5 | Lancer | 4

## Strategy
The game is still young, so strategy is still being developed! Much of the data is currently based on Engine play.

The Horde cannot castle. However, a very fundamental component of a majority of Horde openings is to move the Khan to g7. Reaching this spot in within the first four moves is ideal – in fact, Fairy Stockfish opened up with Kf7 in 56% of its games. The rest is variable. 
For the Kingdom, d4, g3, and b3 are the most common openings in that order.

A major Horde weakness is that the lancers and horse archers cannot sustain a threat on a piece. If you attack a lancer/archer, if they must retreat, they lose their attack. It's important for the Kingdom to take advantage of this.

### Openings

The following is based off an analysis of the first few moves played by Fairy-Stockfish against itself

White first move	| Percent of games (number) | White Win % | Gold Win % | Gold response
-- | -- | -- | -- | --
d4 | 38%	(47) | 45% | 38% | Kf7 ~= c5 >> Hb7
g3	| 24% (30)	| 33% | 43% | Kf7 >> d5
b3 | 14% (18) | 33% | 44% | Kf7 >> Lc7
e3 | 11% (14) | 50% | 50% | Kf7 ~50% of the time
d3 | 6% (8) | 25% | 25% | e5 ~=Kf7
Nf3 | 3% (4) | 25% | 50% | e5 always
e4 | 2% (3) | 33% | 67% | d5
c4 | 1% (1) | 100% | 0% | Kf7

Some particular lines have been also played for multiple games. Here are the four most common. We'll use the name "castle" for any variation where the Horde tucks away the khan to Kf7 as soon as possible. The last moves in parentheses are where variations start to significantly happen.

**Benko's Castle - Double Corner Opening** - Most common opening
1. g3 Kf7
2. e4 Kg7
3. (Bd3 or Nf3) ...

![Benko's Castle](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/BenkoCastle.png)

*Benko's Castle after 2... Kg7*

**Stockfish Defense - Closed Variation**
1. d4 c5
2. dxc5 *bxc5*
3. c4 Kf7
4. (Nc3) ...

**Stockfish Defense - Open Variation**
1. d4 c5
2. dxc5 *dxc5*

**Stockfish Defense - Queenside Push**
1. d4 c5
2. *e3* cxd4
3. exd4 b5
4. b3 Kf7
5. c4

![Stockfish Defense Queenside Push](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/QueensidePush.png)

*Stockfish Defense- Queenside Push after 5. c4*

<iframe width="560" height="315" src="https://www.youtube.com/embed/Ap4mGkR8HDA" frameborder="0" allowfullscreen></iframe>
