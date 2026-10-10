# ![Orda Mirror](https://github.com/pychess/pychess-variants/blob/master/static/icons/ordamirror.svg) Orda Mirror

![Orda Mirror Board](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/OrdaMirror.png)

Orda Mirror is a chess variant designed in 2020 by Couch Tomato and is a derivative variant of Orda Chess. Orda Mirror takes the Horde army from Orda Chess and pits them against each other, turning into a Horde vs Horde mirror match. However, the Horde armies in Orda Mirror are not completely identical to the one in Orda Chess; the Yurt is replaced with the new Falcon, a piece that moves like a queen, but attacks like a knight (all other Horde pieces *move* like a knight). This gives some long range flexibility that the Horde was otherwise missing while preserving the horse motif.
 
## General Rules
1.	Setup is as above.
2.	White moves first.
4.	Neither side can castle.
6.	Pawns can promote to any Horde piece.
7.	An additional method of victory is available: called **campmate**. Campmate is achieved by moving one’s king into the final rank without moving into check.
8.	Other rules, including stalemate and repetition, are as in chess.

## Horde Pieces
There are four new units unique to the Horde: 2 Lancers, 2 Horse Archers, 2 Kheshigs, and 1 Falcon (the Falcon being unique to Orda Mirror). The Kheshigs are the strongest piece (knight + king movement) and lead each flank. 
The Horde’s "king" is called the Khan and has a different symbol, but is essentially the same as a classic King, also using the same abbreviation (K) – the change is purely aesthetic and thematic. 
The Horde's Lancer and Horse Archer capture differently than movement ("divergent" pieces, like the pawn). Remember that the Horde is horse-based, so the Lancer and Horse Archer both move like knights. They capture/check like rooks and bishops, respectively. The Falcon replaces the Queen. Unlike the other two pieces, it retains the movement of the Queen, but instead *captures/checks* like a knight. The Kheshig is more traditional in that it captures where it moves; it combines the movements of the knight and king. 

**Horde** piece	| Classic counterpart	| Movement | Capture/Check
-- | -- | -- | --
Falcon | Queen | Queen | **Knight**
Horse Archer | Bishop | **Knight** | Bishop
Kheshig | Knight | **Knight**+King | **Knight**+King
Lancer | Rook | **Knight** | Rook

Details and diagrams of each piece are below. Green dots represent movement, red dots represent capture, and yellow represents both.
 
### Falcon (F)

![Falcon](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Falcon.png)
 
The Falcon is a unique divergent piece that moves and attacks differently. It moves as a queen but captures as a knight.

### Kheshig (H)

![Kheshig](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Kheshig.png)
 
The Kheshig is a hybrid piece that moves and captures as a knight and king combined. This piece type is also generically called the centaur. The kheshig starts in the knight’s spot, but unlike the knight, is the strongest Horde piece. It can be thought of as the general that leads its own troops on each flank.

### Horse Archer (A)

![Horse Archer](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Archer.png)
 
The Horse Archer, or simply abbreviated Archer, is a unique divergent piece that moves and attacks differently. The archer moves as a knight but captures as a bishop. Because the archer is not colorbound, its value is greater than the bishop.
 
### Lancer (L)

![Lancer](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Lancer.png)
 
The Lancer is a unique divergent piece that moves and attacks differently. The lancer moves as a knight but captures as a rook.

## Strategy
The game is still young, so strategy is still being developed! Much of the data is currently based on Engine play.

Piece valuation is difficult and not optimally known at this point. It is suspected that the minor pieces (Falcon, Archer, Lancer) are actually all fairly similar in value. The Kheshigs are the sole major pieces and will often be the main instrument of delivering checkmate.

<iframe width="560" height="315" src="https://www.youtube.com/embed/Ap4mGkR8HDA" frameborder="0" allowfullscreen></iframe>
