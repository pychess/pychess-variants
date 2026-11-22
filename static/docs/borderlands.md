<style>
td { vertical-align: top; }
.tab_inline { display: inline; width: 50%; border: 1px solid; }
.region_name { vertical-align: bottom; font-weight: bold; }
.region_area { vertical-align: top; }
.zone_highlight { vertical-align: middle; min-width: 60px; }
.piece_title { vertical-align: middle; width:50%; }
.piece_title_nowrap { white-space: nowrap; }
.piece_movement { vertical-align: middle; }
.piece_values { vertical-align: middle; border: 1px solid; }
#region_table tr.line_t { border-style: solid; border-width: 1px 0px 0px 0px; }
#region_table tr.line_b { border-style: solid; border-width: 0px 0px 1px 0px; }
#region_table tr.line_tb { border-style: solid; border-width: 1px 0px 1px 0px; }
#region_table td { text-align: left; }

.board_row { display: flex; }
.board_column { flex: 50%; padding: 5px; }
</style>

# 🌄 Borderlands

![Borderlands](../static/images/BorderlandsGuide/BorderlandsPoster.png)

Borderlands is a chess variant created by dpldgr in 2025 for PyChess' Variant Design Contest.

Borderlands draws inspiration from many classic variants (Chess, Shogi, Xiangqi, and Courier Chess) and fuses them together in a unique and creative way. Pieces are in general more powerful than those found in the classic variants.

- Sliding pieces (Rooks, Bishops) and jump capturing pieces (Pao, Vao) are merged to create more powerful pieces (Archer, Slinger).
- Most pieces are promotable, giving incentive to keep them on the board as every piece can help win the game by cornering and capturing enemy Chiefs.
- There is a wide variety of pieces with different strengths and weaknesses.

## Historical Setting
Borderlands is not set in a specific place or culture. Rather, it serves as an abstract representation of warfare as it evolved during the early Classical Antiquity period (approximately 500–100 BCE), following the decline of chariot warfare. It reflects the tactical emphasis on infantry formations, skirmishers, and emerging combined-arms warfare typical of that era.

## General Rules
1.  White has the first move.
2.  All pieces are capturable and are permanently removed from play upon capture.
3.  There is no checkmate or stalemate.
4.  There is no castling.
5.  Pieces promote immediately upon reaching their Promotion Zone/Square.
6.  Warriors starting on the 3rd rank may make a double step on their first move, and may be captured en passant on the enemy's next move.

## Win Conditions
1. Capture both enemy Chiefs and the enemy immediately surrenders.

## Draw Conditions
1.  No Progress: 80 moves (40 by each player) without a capture or promotion.
2.  Impasse: the game is unable to progress due to neither side having a realistic chance of capturing both enemy Chiefs.

## Lose Conditions
1.  No Legal Moves: if a player cannot make a legal move they lose the game.
2.  Perpetual Check: (TODO: confirm this works for Chiefs).
3.  Move Repetition: repeating a position for the 5th time.

## The Board
The empty board and initial position for Borderlands are as follows:

<div class="board_row">
  <div class="board_column"><img src="../static/images/BorderlandsGuide/BoardEmpty.png" alt="Borderlands Empty Board" style="width:100%"></div>
  <div class="board_column"><img src="../static/images/BorderlandsGuide/BoardInitial.png" alt="Borderlands Initial Position" style="width:100%"></div>
</div>

### Regions and Squares
There are a number of important regions and squares in Borderlands:

<table id="region_table" style="border-style: solid; border-width: 1px 0px; border-collapse: collapse;">
<tbody>
    <tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../static/images/BorderlandsGuide/WhiteTerritory.png" alt="White Territory"></td><td class="region_name">White Territory</td></tr>
    <tr><td class="region_area">Ranks 1-5</td></tr>
    <tr><td>All White pieces start the game within this region.</td></tr>
    <tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../static/images/BorderlandsGuide/WhiteIncursionZone.png" alt="White Incursion Zone"></td><td class="region_name">White Incursion Zone</td></tr>
    <tr><td>Ranks 6-7</td></tr>
    <tr><td>White Marauders must come into play in this region. Black Warriors initially guard every single square of it.</td></tr>
    <tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../static/images/BorderlandsGuide/WhitePromotionZone.png" alt="White Promotion Zone"></td><td class="region_name">White Promotion Zone</td></tr>
    <tr><td>Ranks 8-10</td></tr>
    <tr><td>All promotable White pieces (except the Lion) can promote anywhere within this region.</td></tr>
    <tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../static/images/BorderlandsGuide/WhiteLionsMovementZone.png" alt="White Lion's Movement Zone"></td><td class="region_name">White Lion's Movement Zone</td></tr>
    <tr><td>Ranks: 1-5<br/>Squares: d7, f7, e9</td></tr>
    <tr><td></td></tr>
    <tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../static/images/BorderlandsGuide/WhiteLionsPromotionSquare.png" alt="White Lion's Promotion Square"></td><td class="region_name">White Lion's Promotion Square</td></tr>
    <tr><td>Square: e9</td></tr>
    <tr><td>The White Lion promotes upon reaching this square, and is then able to freely roam the entire board.</td></tr>
    <tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../static/images/BorderlandsGuide/BlackTerritory.png" alt="Black Territory"></td><td class="region_name">Black Territory</td></tr>
    <tr><td>Ranks 6-10</td></tr>
    <tr><td>All Black pieces start the game within this region.</td></tr>
    <tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../static/images/BorderlandsGuide/BlackIncursionZone.png" alt="Black Incursion Zone"></td><td class="region_name">Black Incursion Zone</td></tr>
    <tr><td>Ranks 4-5</td></tr>
    <tr><td>Black Marauders must come into play in this region. White Warriors initially guard every single square of it.</td></tr>
    <tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../static/images/BorderlandsGuide/BlackPromotionZone.png" alt="Black Promotion Zone"></td><td class="region_name">Black Promotion Zone</td></tr>
    <tr><td>Ranks 1-3</td></tr>
    <tr><td>All promotable Black pieces (except the Lion) can promote anywhere within this region.</td></tr>
    <tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../static/images/BorderlandsGuide/BlackLionsMovementZone.png" alt="Black Lion's Movement Zone"></td><td class="region_name">Black Lion's Movement Zone</td></tr>
    <tr><td>Ranks: 6-10<br/>Squares: d4, f4, e2</td></tr>
    <tr><td></td></tr>
    <tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../static/images/BorderlandsGuide/BlackLionsPromotionSquare.png" alt="Black Lion's Promotion Square"></td><td class="region_name">Black Lion's Promotion Square</td></tr>
    <tr><td>Square: e2</td></tr>
    <tr><td>The Black Lion promotes upon reaching this square, and is then able to freely roam the entire board.</td></tr>
</tbody>
</table>

## The Pieces
### Names, Movement, Notations, Icons, & Promotions
The movement diagrams below follow these conventions:
<table style="border-collapse: collapse;">
<tbody>
    <tr><td width="15%"><img src="../static/images/BorderlandsGuide/RedCircle.png" alt="Red Circle"></td><td class="piece_movement" style="text-align: left;">Red Circle: can make both capturing and non-capturing moves to this square unimpeded.</td></tr>
    <tr><td width="15%"><img src="../static/images/BorderlandsGuide/BlueCircle.png" alt="Blue Circle"></td><td class="piece_movement" style="text-align: left;">Blue Circle: can make a capturing move to this square unimpeded.</td></tr>
    <tr><td width="15%"><img src="../static/images/BorderlandsGuide/TealLine.png" alt="Teal Line"></td><td class="piece_movement" style="text-align: left;">Teal Line: can make both a capturing and non-capturing sliding move, or jump a piece and capture in a manner similar to a Cannon.</td></tr>
</tbody>
</table>

<table style="border-collapse: collapse;">
<tbody>
    <tr><td width="25%"></td><td class="piece_title" width="50%" style="background-color:#d4c7e3;color:#000000">Chief (C)</td><td width="25%"></td></tr>
    <tr><td width="25%"></td><td><img src="../static/images/BorderlandsGuide/Chief.png" alt="Chief"><br/>Betza: K</td><td width="25%"></td></tr>
    <tr><td colspan="3">Chiefs are the most valuable pieces on the board. Capture both of the enemy Chiefs and your enemy immediately surrenders.</td><td></td><td></td></tr>
</tbody>
</table>
<table style="border-collapse: collapse;">
<tbody>
    <tr><td class="piece_title" style="background-color:#e6e6e6;color:#000000"><span class="piece_title_nowrap">Marauder (M)</span></td><td class="piece_title" style="background-color:#f7e6ae;color:#000000">Promoted <span class="piece_title_nowrap">Marauder (+M)</span></td></tr>
    <tr><td><img src="../static/images/BorderlandsGuide/Marauder.png" alt="Marauder"><br/>Betza: F</td><td><img src="../static/images/BorderlandsGuide/MarauderPromoted.png" alt="Marauder Promoted"><br/>Betza: K</td></tr>
    <tr><td colspan="2">The Marauder's role is to disrupt the enemy through any means necessary. They can very quickly slip behind enemy lines if there are small holes in the enemy's defenses.
<p/>
Marauders start the game in hand, and must come into play by being dropped into their Incursion Zone, and can often promote on their next move.<p/>
They can move like a Ferz (F). Upon promotion, Marauders gain the ability to make one step orthogonally (W).</td><td></td></tr>
    <tr><td class="piece_title" style="background-color:#e6e6e6;color:#000000"><span class="piece_title_nowrap">Falcon (F)</span></td><td class="piece_title" style="background-color:#f7e6ae;color:#000000">Promoted <span class="piece_title_nowrap">Falcon (+F)</span></td></tr>
    <tr><td><img src="../static/images/BorderlandsGuide/Falcon.png" alt="Falcon"><br/>Betza: W</td><td><img src="../static/images/BorderlandsGuide/FalconPromoted.png" alt="Falcon Promoted"><br/>Betza: K</td></tr>
    <tr><td colspan="2">They can move like a Wazir (W). Upon promotion, Falcons gain the ability to make one step diagonally (F).<p/></td><td></td></tr>
    <tr><td class="piece_title" style="background-color:#e6e6e6;color:#000000"><span class="piece_title_nowrap">Elephant (E)</span></td><td class="piece_title" style="background-color:#f7e6ae;color:#000000">Promoted <span class="piece_title_nowrap">Elephant (+E)</span></td></tr>
    <tr><td><img src="../static/images/BorderlandsGuide/Elephant.png" alt="Elephant"><br/>Betza: WAD</td><td><img src="../static/images/BorderlandsGuide/ElephantPromoted.png" alt="Elephant Promoted"><br/>Betza: KAD</td></tr>
    <tr><td colspan="2">Elephants are jumping pieces. They can move like a Wazir, Alfil, or Dabbaba (WAD). Upon promotion, Elephants gain the ability to move like a King (K).<p/></td><td></td></tr>
    <tr><td class="piece_title" style="background-color:#e6e6e6;color:#000000"><span class="piece_title_nowrap">Horse (H)</span></td><td class="piece_title" style="background-color:#f7e6ae;color:#000000">Promoted <span class="piece_title_nowrap">Horse (+H)</span></td></tr>
    <tr><td><img src="../static/images/BorderlandsGuide/Horse.png" alt="Horse"><br/>Betza: NF</td><td><img src="../static/images/BorderlandsGuide/HorsePromoted.png" alt="Horse Promoted"><br/>Betza: NK</td></tr>
    <tr><td colspan="2">Horses are jumping pieces. They can move like a Knight or Ferz (NF). Upon promotion, Horses gain the ability to move like a King (K).<p/></td><td></td></tr>
    <tr><td class="piece_title" style="background-color:#e6e6e6;color:#000000"><span class="piece_title_nowrap">Slinger (S)</span></td><td class="piece_title" style="background-color:#f7e6ae;color:#000000">Promoted <span class="piece_title_nowrap">Slinger (+S)</span></td></tr>
    <tr><td><img src="../static/images/BorderlandsGuide/Slinger.png" alt="Slinger"><br/>Betza: BcpB</td><td><img src="../static/images/BorderlandsGuide/SlingerPromoted.png" alt="Slinger Promoted"><br/>Betza: BcpBW</td></tr>
    <tr><td colspan="2">Slingers are long range pieces able to attack from afar along diagonal lines. They can move like a Bishop (B) or capture like a Vao (cpB). Upon promotion, Slingers gain the ability to move like a Wazir (W).<p/></td><td></td></tr>
    <tr><td class="piece_title" style="background-color:#e6e6e6;color:#000000"><span class="piece_title_nowrap">Archer (A)</span></td><td class="piece_title" style="background-color:#f7e6ae;color:#000000">Promoted <span class="piece_title_nowrap">Archer (+A)</span></td></tr>
    <tr><td><img src="../static/images/BorderlandsGuide/Archer.png" alt="Archer"><br/>Betza: RcpR</td><td><img src="../static/images/BorderlandsGuide/ArcherPromoted.png" alt="Archer Promoted"><br/>Betza: RcpRF</td></tr>
    <tr><td colspan="2">Archers are long range pieces able to attack from afar along orthogonal lines. They can move like a Rook (R) or capture like a Pao (cpR). Upon promotion, Archers gain the ability to move like a Ferz (F).<p/></td><td></td></tr>
    <tr><td class="piece_title" style="background-color:#e6e6e6;color:#000000"><span class="piece_title_nowrap">Warrior (W)</span></td><td class="piece_title" style="background-color:#f7e6ae;color:#000000">Promoted <span class="piece_title_nowrap">Warrior (+W)</span></td></tr>
    <tr><td><img src="../static/images/BorderlandsGuide/Warrior.png" alt="Warrior"><br/>Betza: fWfceFifmnD</td><td><img src="../static/images/BorderlandsGuide/WarriorPromoted.png" alt="Warrior Promoted"><br/>Betza: NK</td></tr>
    <tr><td colspan="2">Warriors can move like both a Chess Pawn (fmWfceFifmnD) and a Shogi Pawn (fW). Warriors starting on the 3rd rank may make a double step on their first move, and may be captured en passant by an enemy Warrior on the enemy's next move. Upon promotion, the Warrior's movement changes.<p/>A Promoted Warrior can move like a Knight or Ferz (NF).<p/></td><td></td></tr>
    <tr><td class="piece_title" style="background-color:#e6e6e6;color:#000000"><span class="piece_title_nowrap">Lion (L)</span></td><td class="piece_title" style="background-color:#f7e6ae;color:#000000">Promoted <span class="piece_title_nowrap">Lion (+L)</span></td></tr>
    <tr><td><img src="../static/images/BorderlandsGuide/Lion.png" alt="Lion"><br/>Betza: KNAD</td><td><img src="../static/images/BorderlandsGuide/LionPromoted.png" alt="Lion Promoted"><br/>Betza: KNAD</td></tr>
    <tr><td colspan="2">Lions start the game as a defensive piece restricted to their side's Territory, and have a very limited path to promotion (via the Lion's Incursion Squares) that is easily defended against. Upon promotion, Lions gain the ability to roam the entire board.<p/></td><td></td></tr>
</tbody>
</table>

### Piece Values
<table  style="border-collapse: collapse; border: 1px solid;">
<tbody>
    <tr><td class="piece_values"><b>Piece</b></td><td class="piece_values"><b>Notation</b></td><td class="piece_values"><b>Value</b></td><td class="piece_values"><b>Piece</b></td><td class="piece_values"><b>Notation</b></td><td class="piece_values"><b>Value</b></td></tr>
    <tr><td class="piece_values">Promoted Lion</td><td class="piece_values">+L</td><td class="piece_values">7.49</td><td class="piece_values">Chief</td><td class="piece_values">C</td><td class="piece_values">3.40</td></tr>
    <tr><td class="piece_values">Promoted Archer</td><td class="piece_values">+A</td><td class="piece_values">6.16</td><td class="piece_values">Slinger</td><td class="piece_values">S</td><td class="piece_values">3.36</td></tr>
    <tr><td class="piece_values">Promoted Warrior</td><td class="piece_values">+W</td><td class="piece_values">5.87</td><td class="piece_values">Elephant</td><td class="piece_values">E</td><td class="piece_values">3.21</td></tr>
    <tr><td class="piece_values">Promoted Horse</td><td class="piece_values">+H</td><td class="piece_values">5.48</td><td class="piece_values">Lion</td><td class="piece_values">L</td><td class="piece_values">3.11</td></tr>
    <tr><td class="piece_values">Promoted Elephant</td><td class="piece_values">+E</td><td class="piece_values">4.87</td><td class="piece_values">Promoted Marauder</td><td class="piece_values">+M</td><td class="piece_values">2.31</td></tr>
    <tr><td class="piece_values">Archer</td><td class="piece_values">A</td><td class="piece_values">4.77</td><td class="piece_values">Warrior</td><td class="piece_values">W</td><td class="piece_values">1.34</td></tr>
    <tr><td class="piece_values">Promoted Slinger</td><td class="piece_values">+S</td><td class="piece_values">4.16</td><td class="piece_values">Marauder</td><td class="piece_values">M</td><td class="piece_values">0.88</td></tr>
    <tr><td class="piece_values">Promoted Falcon</td><td class="piece_values">+F</td><td class="piece_values">4.01</td><td class="piece_values">Falcon</td><td class="piece_values">F</td><td class="piece_values">0.79</td></tr>
    <tr><td class="piece_values">Horse</td><td class="piece_values">H</td><td class="piece_values">3.48</td><td class="piece_values"></td><td class="piece_values"></td><td class="piece_values"></td></tr>
</tbody>
</table>

<img src="../static/images/BorderlandsGuide/PieceValues.png" alt="Piece Values">

## Strategy
TODO.

How to Play Borderlands video:
TODO

Gameplay Sample 1:
<iframe width="560" height="315" src="https://www.youtube.com/embed/PdsT9i2PIjA" frameborder="0" allowfullscreen></iframe>
Gameplay Sample 2:
<iframe width="560" height="315" src="https://www.youtube.com/embed/IpMFoFIdPUY" frameborder="0" allowfullscreen></iframe>
