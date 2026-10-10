# ![Chennis](https://github.com/pychess/pychess-variants/blob/master/static/icons/Chennis.svg) Chennis

![Chennis](https://github.com/pychess/pychess-variants/blob/master/static/images/ChennisGuide/Chennis.png)

## Background

Chennis is a game designed by Couch Tomato in 2021 primarily designed as a variant of Kyoto Shogi. Since Kyoto Shogi is a solved game, the goal was to create a more balanced game as well as something more accessible to international chess players. To use less shogi-like pieces, more long-range pieces were needed and thus a larger board. And to keep the king easy enough to mate, restrictions were created. These restrictions coincidentally resulted in a tennis court-shaped board, and hence Chennis was born! Due to the use of cannons and restricted king areas, the game can also be said to feature elements of Xiangqi, making it a game that combines multiple historical chess variants. In terms of balance, the game is approximately 60-40, in favor of white, which achieves what it sets out to do from the initial design.

## Introduction and General Rules

There are two sides, designated white and black, respectively. White moves first. Each piece (other than the king) has *two sides*; after each move, the piece changes to its counterpart piece (typically marked as red on the white pieces and marked as blue on the black pieces).

![Piece Swaps](https://github.com/pychess/pychess-variants/blob/master/static/images/ChennisGuide/Swap.png)

When you capture a piece, it goes into your hand. On a future turn, you can drop that piece onto the board on any open square *as either side of the piece*. For example, for the Rook-Pawn combo, you can drop it as a rook or as a pawn.

### Board

Chennis is played on a 7x7 board as shown below:

![Chak](https://github.com/pychess/pychess-variants/blob/master/static/images/ChennisGuide/ChennisCourt.png)

Pieces that are not the king can move anywhere on the board. There are four types of regions, which determine where the kings can move:

**White's Court**: Only the white king can move in this region.

**Black's Court**: Only the black king can move in this region.

**Net**, a 5 square region in the middle that actually belongs to both courts, so both kings can move in this region.

**Sidelines**, the edges files; *neither* king can move in these areas.

### Goals of the Game

There are three ways to win:

**Checkmate** - Put the king in check with no legal moves.

**Stalemate** - A player with no legal moves loses (unlike in Chess, where it is a draw). 

**Resignation** - Your opponent resigns.

## Pieces

The King (K) is the same as in any form of chess and can move on square in any direction as long as it's within the legal area (see above). Keep in mind that a king can mate another king that's at the net.

There are four piece pairs:

Rook-Pawn  
Bishop-Soldier  
Knight-Mayor  
Cannon-Ferz

The rook, pawn, knight, and bishop move exactly as in chess. If you are not familiar with these pieces, please check out a chess guide. The only exception is that the pawn does not have the two step move as in chess.

In general, each pair has opposite movement: Diagonally-attacking pieces turn into orthogonally-attacking pieces and vice-versa.

### Soldier (S)
![Soldier](https://github.com/pychess/pychess-variants/blob/master/static/images/ChennisGuide/Soldier.png)

The Soldier moves one space forwards or one space sideways. It turns into a Bishop after moving.

### Mayor (M)
![Mayor](https://github.com/pychess/pychess-variants/blob/master/static/images/ChennisGuide/Mayor.png)

The Mayor moves exactly like the king (one space in any direction). It turns into a Knight after moving.

### Ferz (F)
![Ferz](https://github.com/pychess/pychess-variants/blob/master/static/images/ChennisGuide/Ferz.png)

The Ferz moves exactly one space diagonally. It turns into a Cannon after moving.

### Cannon (C)
![Cannon Move](https://github.com/pychess/pychess-variants/blob/master/static/images/ChennisGuide/CannonMove.png)

![Cannon Attack](https://github.com/pychess/pychess-variants/blob/master/static/images/ChennisGuide/CannonAttack.png)

The Cannon moves like a rook (any number of squares orthogonally), but to capture, it needs to hop over an intervening piece. This is the same as the cannon in Xiangqi. It turns into a Ferz after moving.

## Piece valuation

Accurate piece values are unknown. In general, for dropping games such as Chennis, the situation is more important than strict piece evaluation. However, the Knight-Mayor is generally considered the best piece combo because both sides are flexible.

## Strategy 

Strategy is still being developed as the game is quite new.

For beginners, I can't stress enough to remember where the king can move. That means pieces can be dropped on the sideline and threaten the king without retaliation from the king.

<iframe width="560" height="315" src="https://www.youtube.com/embed/_Mis4iWRHws" frameborder="0" allowfullscreen></iframe>

