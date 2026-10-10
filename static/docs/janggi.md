# ![Janggi](https://github.com/pychess/pychess-variants/blob/master/static/icons/Janggi.svg) Janggi

![Boards](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Boards.png)

*Janggi* (장기, pronounced like “*chahng-ghee*”), or Korean Chess, is a classic board game native to Korea. The game is derived from Xiangqi and is very similar to it.

## Rules: Board and Setup

There are two sides, one is colored red (called Han), and the other blue (called Cho). The blue side can also be colored green. These two sides represent the two sides in the Chu-Han Contention from Chinese history. Red pieces are written using regular-style hanja (chinese character), while blue pieces are written in cursive-style hanja.

Setup for all pieces except for the horse and elephant are as in the picture above. Like xiangqi, janggi is placed on a 9 x 10 board, where pieces are placed on intersections rather than squares. The 3x3 square with the X on each side is called the *Palace*. Unlike in most other chess variants, in janggi, players can choose the starting positions of the horses and elephants. There are four types to choose from:

1. Both elephants are inside (An Sang Charim, means 'Inner Elephant Setup')
2. Both elephants are outside (Bakkat Sang Charim, means 'Outer Elephant Setup')
3. Left elephant is inside, and right elephant is outside (Oen Sang Charim, means 'Left Elephant Setup')
4. Left elephant is outside, and right elephant is inside (Oreun Sang Charim, 'Right Elephant Setup')

Usually, 1 is called Wonang-ma (Mandarin Duck Horse), 2 is called Yang-gwima (Both Corner Horse), and 3 and 4 are called Gwima (Corner Horse).
If Cho and Han choose the same setup among 3 or 4, it is called Mat Sang (Elephants facing each other).
The reason it is called that is as follows.

The space in front of the King's starting point in a straight line is called Myeon (Face), and the space in front of the King's starting point in a diagonal line is called Gwi (Corner).
- In cases 3 and 4, one Horse can go to the Corner, so it is called Corner Horse, Gwima.
- In case 2, two Horses can go to the Corner, so it is called Both Corner Horse, Yang-gwima.
- In case 1, two Horses cannot go to the Corner, but if one Horse comes out to the center, they protect each other, so it is called Mandarin Duck Horse, Wonang-ma.
(Unlike reality, there is a Korean folklore that mandarin ducks are a couple that loves each other deeply. The name Mandarin Duck Horse may have originated from that folklore)

Red (Han) gives Blue (Cho) three rights in exchange for 1.5 points:
* Cho's right to choose setup later
* Cho's right to change setup before the game starts (This is rarely applied online, but Red still gets 1.5 points.)
* Cho's right to move first

For repetitions and other game-end scenarios:
* Perpetual check is a loss for the player checking after the third repetition
* Repetitions that are not perpetual are adjudicated by material counting after the third repetitions
* When the 50-move rule is reached (100 half-moves without capture), game is adjudicated by material counting

## The Pieces

This guide will be based on the internationalized set. Traditional sets use Chinese characters (hanja), and many sites, including Wikipedia, already explain the rules as such.

Several pieces have special moves utilizing the diagonals in either palace, which will be discussed below. In the diagrams, a lighter shade of green is used.

### King

![Kings](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Kings.png)

The **King** (also known by its Chinese name, the **general**) is restricted to the palace and can move within lines of the palace. This means that when the King is in the center, it has 8 possible moves. However, on any other spot in the Palace, it only has 3 moves.

*Special rule:* When a King faces the other King, this causes *bikjang*. The next player must then move his king out of the way or else the game is ended. See rules below regarding bikjang.

![King and advisor](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Palace.png)

### Advisor

![Advisors](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Advisors.png)

The **Advisor** (also known by its Western name, the **guard**) moves exactly like the King, which is one space along lines within the palace. Like the King, the Advisor is confined to the palace.

### Horse

 ![Horses](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Horses.png)
 
 ![Horse movement](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/HorseDiagram.png)

The **Horse** (also called by its Western name, the **knight**) moves almost exactly like a chess knight. However, instead of the usual “two steps orthogonally, then one to the side” teaching, it’s better to think of it as *one step orthogonally, then diagonally forward in either direction*, like a Y shape. The reason for this is that the horse **can be blocked** if a piece is adjacent to it. That will block off the two endpoints of that Y. Therefore, there can be situations where two horses are targeting each other, but only one can attack while the other is blocked. Strong moves take advantage of blocking the horse and limiting its movement.

### Elephant

 ![Elephants](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Elephants.png)
 
 ![Elephant movement](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/ElephantDiagram.png)

The **Elephant** is much different than its xiangqi counterpart. Movement is similar to the horse in that it moves in a Y-shaped pattern. While the horse moves one step orthogonally and then one step further diagonally, the elephant moves one step orthogonally and then *two* steps diagonally. The elephant, like the horse, can be blocked on any intervening point along this path.

### Chariot

 ![Chariots](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Chariots.png)
 
 ![Chariot movement](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/ChariotDiagram.png)

The **Chariot** (also called by its Western name, the **rook**) moves exactly like a chess rook: any number of squares orthogonally. This is the most valuable piece in the game, excluding the king.

*Palace move*: When in the palace, the chariot can also move along the diagonal lines.

### Cannon

![Cannons](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Cannons.png)

![Cannon movement](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/CannonDiagram.png)

The **Cannon** is slightly different than its xiangqi counterpart. It moves orthogonally like the chariot, but it needs an intervening piece (called a "screen") to hop over first. It can then capture the next piece along the same line. Unlike xiangqi, the Cannon cannot move without a screen.

*EXCEPTION*: The cannon cannot use another cannon as a screen. Additionally, it can't capture the opponent's cannons.

*Palace move*: When in the palace, the cannon can also move along the diagonal line. Practically speaking, the cannon must be on one corner, where it can move or attack the opposite corner if a non-cannon piece is in the center (as in the diagram).

### Pawn

![Pawns](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Pawns.png)

![Pawn movement](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/PawnDiagram.png)

The **Pawn** (also called by its Chinese name, the **soldier**) moves and captures by moving forward or sideways one square. This is different than the xiangqi pawn, which needed to cross the river first to move sideways.

*Palace move*: When in the palace, the pawn can also move forwards along the diagonal lines.

## Notation

Janggi notation works much differently than other variants. First of all, coordinate numbering. From blue's perspective, ranks are numbered from 1 to 10 going down from top to bottom. However, the 10th rank is called 0. Files are numbered 1 to 9 from left to right. Describing a piece location is the opposite of chess. A location is described by *rank* then *file* (in all other variants, it's file, then rank). So for example, the blue chariot in the bottom left corner is at **01**. The intersection above it is **91**. The blue king is located at **95**.

Describing moves does not have a standardized international version. We use a modified version of the Korean way. In Korean, the syntax is (starting location)(piece name in Korean)(ending location). Here on Pychess, we use (English piece abbreviation)(starting location)-(ending location). Like in chess, captures are denoted with x instead of -, check has a + at the end, and checkmate is #.

For example, the left chariot moving three spaces up is denoted by R01-71. "R" refers to the chariot. For piece abbreviations, see below.

### Abbreviations

K = **K**ing  
A = **A**dvisor  
E = **E**lephant  
H = **H**orse  
C = **C**annon  
R = Cha**R**iot  
P = **P**awn

## Rules: Gameplay

Like chess, the goal is to checkmate the other king.

Unlike most other chess variants, you may pass in Janggi. Therefore, stalemate is impossible. **To pass in Pychess, Ctrl+Click on your King, or simply click the pass button on the right.**

Unlike Xiangqi, the kings may face each other on the same file in Janggi. This creates a situation called **bikjang** ("laughing generals"). The next player to move has two choices: make a move to break bikjang (for example by moving the king or moving a piece in between), or pass the turn, causing the game to end in a draw. For tournaments that don't allow draws, the value of the pieces on the board are counted up, and the player with the higher value wins.

Piece | Value 
------------ | ------------- 
Chariot | 13
Cannon | 7
Horse | 5
Elephant | 3
Advisor | 3
Pawn | 2

Because blue (Cho) starts the game, they start with an advantage and thus red (Han) also receives 1.5 points (*deom*) as a compensation. The .5 is added to avoid ties.

Currently, Pychess uses tournament style and does not allow draws. Therefore, games are settled by points when bikjang occurs.

Additionally, it's possible to cause bikjang and check at the same time. In this case, bikjang takes priority.

Repetition is illegal; however, the way this is handled is variable. Repetition is not handled in Pychess, so in the event of repetition, the players should adjudicate the outcome between themselves.

## Differences from Xiangqi

Aside from the rules above...

* There is no river in Janggi. Consequently, pawns and elephants move differently. Pawns can move sideways from the start. The Elephant moves completely differently.
* Visually, pieces are on octagons rather than circles. Piece sizes also vary based on value. Kings (generals) are named after the two sides rather than being called "general." Boards use x's instead of crosses for starting pieces.
* The Kings start in the middle of the palace instead of the back of the palace.
* Cannons are different in that they both move and capture the same way (by jumping over a piece first). They also have additional restrictions.
* The Palace affects all piece movement except the Horse and Elephant. Kings and advisors moves along the lines instead of only orthogonally or diagonally. Chariots, cannons, and pawns can move along the diagonals.



## Strategy

[These videos by Amphibian Hoplite](https://www.youtube.com/playlist?list=PL9corMEVRvP-HUJcF7I670pEqV3XNbkKM) are an excellent start for English players. Available resources in English are otherwise fairly limited.

[Here](https://www.youtube.com/watch?v=pX_ZDjeqlJs) is another video by Kolo (AKA Galdian) that also goes over opening principles.

### General Concepts

* Pawn structure is very important. Because pawns can move sideways, they're strongest when protecting each other in pairs. A line of three pawns is a poor formation (because they're stretched out thin). Also because of this, it's not advised to advance pawns if possible.

![Bad Pawn Formations](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/BadPawns.png)

* Regarding the choice of horse-elephant positioning in setup, one way to think about it is how your elephants are positioned, and this has significant implications for the opening. An elephant on the outer position is able to move toward the center between two pawns. However, an elephant in the inner position is blocked by the pawns (although it does protect them).
* Continuing from this, the positioning of your elephant determines which **edge file to open up**. For example, when playing a setup where the left elephant can advance (and the opponent's opposite elephant is also on the outside), you want to move your left edge pawn to the side, opening up the chariot's file. The reason for this is that now the opponent's edge pawn cannot move, so if you attack the cannon file pawn with your elephant, if his edge pawn defends, he would lose his chariot. Note that if the opponent instead had two inner elephants, then you would instead open up the opposite edge.

![Activating the elephant and chariot](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/ActiveElephant.png)

<iframe width="560" height="315" src="https://www.youtube.com/embed/KDkF2dEt41g" frameborder="0" allowfullscreen></iframe>
