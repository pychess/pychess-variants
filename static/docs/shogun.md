# ![Shogun](https://github.com/pychess/pychess-variants/blob/master/static/icons/shogun.svg) Shogun Chess

![Shogun](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ShogunPromotionsMedival.svg)

Shogun Chess is a chess variant designed in 2019-2020 by Couch Tomato. While the game itself is a blend of western chess and shogi rules, the original idea for the game was a way to introduce the hybrid pieces (commonly known as the archbishop and chancellor) in a way different from what other variants have done. For example, keeping an 8x8 instead of enlarging the board to not diminish the value of the minor pieces, or introduce them in a board that is not as cluttered as in S-chess. The idea evolved to introduce these pieces through the means of promotion from the minor pieces and the rook at an earlier rank than the 8th rank. Later, drops were also introduced into the rules as a means to increase the offensive options to offset the defensive nature introduced by the need to protect against the threat of promotion. Unique pawn and knight promotions as well as even a queen demotion were added to complete the theme and symmetry.

The name was originally tentatively "General's Chess," based on what was then the name of the pawn's promotion, now currently the name of the knight's promotion. However, with the drops and promotion zones based off shogi, the Japanese word for "general," shogun sounded more appropriate. The sho in shogun being the same as the one in shogi pays tribute to that as well.

## General Rules

  1. Setup is exactly the same as chess.

  2. New pieces are as defined in the image above, and their moves are described in detail below. Of note, promoted sides are colored differently. Also, the queen *starts* as a promoted piece despite having a new unpromoted form (the Duchess). See details about drops below. For the sake of terminology, a rook will now be considered a "minor piece," while the queen, mortar, archbishop, and general (but NOT the captain) are considered "major pieces." 

  3. The three farthest ranks are the promotion zone. Every starting (or dropped) piece except the king and queen may promote by moving into the promotion zone **or moving from within the promotion zone**. 

  4. However, only one of *each* **major** piece (queen, mortar, archbishop, or general) can be out on each side at a time. For example, if a player has an archbishop in play, then a bishop cannot promote into an archbishop until the current one is captured.

  5. As in crazyhouse and shogi, captured pieces may be dropped back into the board as your own piece. Pieces can be dropped anywhere within the first 5 ranks (in other words, anywhere but the promotion zone). Note that unlike crazyhouse, **pawns can be dropped on the first rank**.

  6. When promoted pieces are captured, they revert to their unpromoted side. This is the only way that a queen becomes a duchess.

Additional minor rules for clarification:
* Dropped rooks cannot castle, as in crazyhouse.
* Pawns dropped on the first rank can still double step when reaching the second rank.
* Pawns cannot promote if capturing by en passant. 

(Note that images were designed for computer play. Over the board pieces are not available but would require shogi-like designs of two-sided directional pieces to be viable.)

*Timer* - Shogun chess uses a byo-yomi timer. Once the main clock expires, a player enters byo-yomi. If it is set at 30 seconds, then that player will only have 30 seconds to make his move from then for each of his/her moves or else lose the game on time. The reason for using byo-yomi instead of the Fischer increment is that the endgame takes longer than the beginning, so byo-yomi guarantees time for each move.

## Pieces

### Archbishop (A)

![Archbishop](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/shogunDestination_w+B.svg)

The archbishop is a hybrid piece seen in multiple other chess variants. In this game, it promotes from bishop and gains the move of a knight. Because of its unique moves, it is the only piece that can checkmate on its own.

### Mortar (M)

![Mortar](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/shogunDestination_w+B.svg)

The mortar is a hybrid piece seen in multiple other chess variants, often with other names such as the chancellor or marshall. In this game, it promotes from the rook and gains the move of a knight. 

### General (G)

![General](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/shogunDestination_w+N.svg)

The general is a hybrid piece, often known as a centaur. In this game, it promotes from the knight and gains the moves of a king.

### Captain (C)

![Captain](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/shogunDestination_w+P.svg)

The captain is the only promotion of the pawn and moves exactly like a king. As a non-royal piece, capturing a captain does not win the game. Also, unlike the rest of promoted pieces, there can be multiple captains, as it is not a major piece.

### Duchess (F)

![Duchess](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/shogunDestination_wF.svg)

The duchess is the only demoted form of the queen and only comes into play after capturing a queen, where it then becomes a duchess in hand. The duchess moves only one space diagonally (same movement as what's often called the "ferz," hence the abbreviation used). As a reminder, a duchess cannot promote to a queen when that player already has a queen on the board (polygamy is illegal in Shogun chess).

## Strategy

The game is still young, so strategy is still being developed! 

With the 6th rank promotions, it is important to protect your own 3rd rank. This is something that a beginner can easily overlook.

General strategy-wise, many players will be tempted to play this as crazyhouse. However, the game diverges quite quickly from crazyhouse due to the drop zone restriction. While players in crazyhouse will often take advantage of weaknesses in the opponents' camps to deliver devastating drops, the gameplay in shogun chess is more defensive. In shogun chess, your army needs to maneuver itself in a way to breach the opponents' camp; even the slightest breach can result in a piece promotion. Therefore, strategy relies more on chess tactics than crazyhouse tactics for this purpose, as well as for the purposes of delivering checkmate.

The ability to drop pawns on the first rank (unlike in crazyhouse) allows a player to build a much stronger castle. To crack this, focus on gaining material and promoted pieces, then push at the weak point.

<iframe width="560" height="315" src="https://www.youtube.com/embed/WRk3ZbX2bpA" frameborder="0" allowfullscreen></iframe>
