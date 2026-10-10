# ![Xiangqi](https://github.com/pychess/pychess-variants/blob/master/static/icons/xiangqi.svg) Xiangqi

![Boards](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Boards.png)

*Xiangqi* (象棋, pronounced like “*shyang-chee*”), or Chinese Chess is a classic board game native to China and is thought to be descended from Chaturanga, the same ancestor as Chess, although some have argued the opposite. The game is very popular in China and Vietnam, and it has been said that it is the most played board game in the world. The game itself is similar to chess, although it plays much differently. 

## Why learn Xiangqi?

If you enjoy Chess, Xiangqi is definitely worth trying. While slightly slower paced and longer than Chess, the game starts more open and is more geared towards fast-paced play leading to a quick endgame. Compared to Chess, Xiangqi is also far more tactical (as opposed to strategic). As with other chess variants, improving your skill in Xiangqi can also improve your skills in Chess (tactics, in particular) as well as open up new ways of thinking! [See here for more about that.](https://en.chessbase.com/post/why-you-need-to-learn-xiangqi-for-playing-better-chess)

## The Rules

The general rules are extremely similar to Chess, so this guide will focus on the few differences. The most striking difference is that pieces are on intersections instead of squares, which is mainly an aesthetic difference. Players take turns moving pieces on a board to checkmate the enemy king. The red player traditionally moves first, followed by black, although the order is not crucial as the board is symmetric. The only other main difference from chess is that stalemates are considered losses for the player who got stalemated (i.e. can’t move any pieces).
Regarding perpetual checks, the player that perpetually checks loses after three repetitions.

## The Board

The xiangqi board is a little different than other chess games. In addition to being played on the intersections, there are important sections of the board. First is the river, which splits the board in half. The river affects the movement of the elephant and pawn pieces. Second are the palaces, which are the 3 x 3 squares at each end of the board that has diagonal lines inside. The king and his advisors are confined to the palace.

## The Pieces

This guide will be based on the internationalized set. Traditional sets use Chinese characters, and many sites, including Wikipedia, already explain the rules as such. As it is now, knowledge of the Chinese characters will be required if you want to utilize all English resources or play in a real life setting. Compared to shogi which is the other major game using Chinese characters, xiangqi has fewer characters to learn, and several characters are pictographic, which also makes them easier to learn.

Xiangqi pieces traditionally have had different names: their Chinese translation and a Western equivalent. In this guide, we will use the names and abbreviations chosen by the Asian Xiangqi Federation (AXF), which uses a mixture of the two. Unfortunately, both names are very common, so you should be familiar with both.

### King

![Kings](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Kings.png)

The king (also known by its Chinese name, the **general**) can only move one step orthogonally. Additionally, it is confined to the palace.

*Special rule*: Kings are not allowed to face each other with no piece in between (“General face-off rule”). Consider them as being able to attack each other as rooks (also called “flying generals”). This is useful for setting up checkmates in the endgame.

![King and advisor movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/KingAdvisorDiagram.png)

### Advisor

![Advisors](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Advisors.png)

The advisor (also known by its Western name, the **guard**... less commonly a **minister**)  can only move one step along the diagonals of the palace. There are only five positions an advisor can take.

### Elephant

 ![Elephants](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Elephants.png)
 
 ![Elephant movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/ElephantDiagram.png)

The elephant (very rarely called by its Western name, the **bishop**) can move diagonally exactly two steps. There are two more restrictions: 1) The elephant can be blocked if there is a piece in between. 2) It cannot cross the river.

On a side note, the Chinese character for the red elephant means “minister,” but is still called an elephant in English.

### Horse

 ![Horses](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Horses.png)
 
 ![Horse movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/HorseDiagram.png)

The horse (also called by its Western name, the **knight**) moves almost exactly like a chess knight. However, instead of the usual “two steps orthogonally, then one to the side” teaching, it’s better to think of it as *one step orthogonally, then diagonally forward in either direction*, like a Y shape. The reason for this is that the knight **can be blocked** if a piece is adjacent to it. That will block off the two endpoints of that Y. Therefore, there can be situations where two horses are targeting each other, but only one can attack while the other is blocked. Strong moves take advantage of blocking the horse and limiting its movement.

### Chariot

 ![Chariots](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Chariots.png)
 
 ![Chariot movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/ChariotDiagram.png)

The chariot (also called by its Western name, the **rook**, and more rarely by its literal modern translation, car) moves exactly like a chess rook: any number of squares orthogonally. This is the most valuable piece in the game, excluding the king.

### Cannon

![Cannons](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Cannons.png)

![Cannon movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/CannonDiagram.png)

The cannon is a unique piece in xiangqi. It can move exactly like the chariot. However, to capture, it needs a piece (friend or foe) in between, called a screen.

### Pawn

![Pawns](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Pawns.png)

![Pawn movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/PawnDiagram.png)

The pawn (also called by its Chinese name, the **soldier**) moves and captures by moving forward one square. This is different than the chess pawn. The pointy hat in the internationalized piece is a reminder.

*Special rule*: After crossing the river, the pawn can move and capture sideways one space as well. The piece itself does not change to reflect this.

## Additional Rules - Perpetual checks and chases

* A player making perpetual checks with one piece or several pieces can be ruled to have lost unless he or she stops such checking.
* The side that perpetually chases any one unprotected piece with one or more pieces, excluding generals and soldiers, will be ruled to have lost unless he or she stops such chasing.
* If one side perpetually checks and the other side perpetually chases, the checking side has to stop or be ruled to have lost.
* When neither side violates the rules and both persist in not making an alternate move, the game can be ruled as a draw.
* When both sides violate the same rule at the same time and both persist in not making an alternate move, the game can be ruled as a draw.

## Notation

As of October 2021, Pychess uses the World Xiangqi Federation (WXF) notation, which is the most commonly used notation internationally. This is much different than the Standard Algebraic Notation (SAN) used in Chess. The standard format is as follows:

[single-letter piece abbreviation][former *file*][operator indicating direction of movement][new file, or in the case of purely vertical movement, number of ranks traversed]

For comparison, the SAN used in chess is:

[single-letter piece abbreviation][former *position*][capture indication][new position][check indication][analysis]

### Symbols

K = **K**ing  
A = **A**dvisor  
E = **E**lephant  
H = **H**orse  
C = **C**annon  
R = Cha**R**iot  
P = **P**awn

## WXF Notation

Files are described differently in WXF notation. 

**Files are numbered 1 to 9, from right to left.**

**Your opponent's files are also numbered from 1 to 9 from their viewpoint as well. Therefore, your cannon in file 2 faces the opponent's cannon in file 8.**

Pieces are described by their file and how they move. Either they move forward (+) or backwards (-). Again, this is relative to the player. Your opponent moving towards you is still + because they are advancing.

### Diagonal pieces and horses

Notation for these pieces is simple + or - and their *new file destination*.

For example, from the starting position, red's right horse on file 2 moving forward and to the left of the cannon would be H2+3. Moving to the edge instead is H2+1. If the elephant moved and did not block the horse, then moving sideways towards the palace is H2+4.

Advisors and elephants work the same way.

### Orthogonal movement

Moving forwards and backwards is **+ or -** followed by *the number of spaces*.

Red pawn on file 5 moving forward = P5+1.

Red chariot on file 1 moving 5 spaces backward is R1-5.

Moving *sideways* is **=** followed by *new file destination*. The typical starting move of moving your right cannon to the center would be 1. C2=5. Moving the left cannon to the center would be 1. C8=5.

Sometimes, some players would use a "." instead of "=".

### Disambiguation

If two pieces of the same type are on the same file, then a + or - to specify if it's the more advanced piece (+) or the piece that's at a lower rank (-). For example, if two chariots are on the same file but on opposite sides of the river, and you wanted to move to the farther one to the center, that would be R+=5.

Finally, if there are 3 or more pawns in the same file, then the pawns are numbered in order, with the pawn closest to you being numbered 1 and so forth. Then instead of using "P", pawns are referred to by their number. So if three pawns are all on file 5, and you wanted to advance the furthest pawn forwards, that would be "35+1".

## Where are resources where I can learn Xiangqi?

[Xiangqi in English] (http://www.xqinenglish.com/) is a good place for beginners. The website owner, Jim Png Hau Cheng, has also written several books, the  “Xiangqi Primer” series, which may be a worthwhile investment for serious learners.

[Club Xiangqi](https://www.clubxiangqi.com/) is a site where you can play against tough players.

## Strategy

### Piece Values

Consensus piece values are as below.

Piece | Value 
------------ | ------------- 
K | Infinite
R | 9
H | 4
C | 4.5
P | 1 before river or at last rank, 2 after river
A | 2
E | 2.5

### General Principles

* Similar to the knight and bishop in chess, the horse and cannon have opposing values based on the state of the board. 
  * The horse is more defensive and less powerful in the early game because of too many pieces restricting its movement. It becomes much more powerful in the endgame when there are few pieces in its way (this is the opposite of the chess knight).  
  * The cannon is more offensive and more potent in the early game because of the pieces it can use as screens. In the endgame, when the board is empty, its power decreases significantly. 
* As above, use pieces to block the horse and elephants!
* Do not think of an elephant as a bishop; they do not at all have similar roles despite their similar movement and starting position. It is strictly a defensive piece. Its offensive utility may be as a screen for a cannon.
* *Discovery attacks* are far more prevalent in xiangqi than in chess or shogi because of the blockable pieces. Be ready to use them or defend against them.
* *Double checks* are also more common, especially with the chariot and cannon in tandem.

### Opening Principles

The following information is courtesy of [Shakki.info](http://www.shakki.info/english/openings.html).

The most common opening move is the central cannon, which is a pretty obvious move because it opens aggression down the central file. About 70% of games start this way, so it's probably the best way to start learning the game.

![Cannon opening](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/CannonOpening.png)

There are four very popular defenses, and a fifth will also be mentioned.

**1. Screen horses / Two horse defense**

![Screen horses](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Screen_Horses.png)

This is the most common defense. The goal of course is to have both horses protecting the center pawn. There are multiple variations.

**2. Fan Gong Ma / "Sandwich Horses"**

One horse is developed as normal, but before the other is developed, the cannon moves into a "palcorner cannon" position (cannon at the same side palace corner), then finally moves the second horse into place. Black will later connect the elephants to complete the defense. It's a relatively new opening.

![Fan Gong Ma](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Fan_Gong_Ma.png)

**3. Same Direction Cannon**

Black moves the cannon from the same side that red moved his. Red capturing the defenseless center pawn is considered a move by amateurs because it loses time and black gets the initiative.

**4. Opposite Direction Cannon**

Like the above, except the opposite cannon. The modern practice is to move the black cannon later through "Delayed Opposite Direction Cannon".

**5. Three Step Tiger**

![Three Step Tiger](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Three_Step_Tiger.png)

Black develops his chariot quickly by moving his cannon to the edge of the board. A typical sequence would be advancing the horse first, then the cannon to the edge, then finally followed by chariot to the cannon's file.

Any other defenses are considered rare.

Aside from the cannon opening, Red has other options as well. These are called "soft openings" because it doesn't open with an immediate threat.

**Pawn Opening** - Advancing the 2nd or 4th pawn. This is a flexible opening allowing Red to adjust to Black's move. Black usually does not answer with the central cannon because Red could then play any of the central cannon openings with colors reversed and the pawn move would be an extra advantage.

**Elephant Opening** - Advancing an elephant to the palace instead of a cannon. This is a solid defensive opening, where the king is protected.

**Horse Opening** - Advancing a horse towards the middle. From there, Red can play the Two horse defence, Fan Gong Ma or Three Step Tiger openings with the colors reversed.

Red can also play his cannon to the front corner of the palace ("Palcorner Cannon") or to the opposite corner ("Crosspalace Cannon"). These moves are also useful developing moves.  

Other red opening moves are very rare.

<iframe width="560" height="315" src="https://www.youtube.com/embed/5EDG5RP8OZ8" frameborder="0" allowfullscreen></iframe>

<iframe width="560" height="315" src="https://www.youtube.com/embed/boT1qyDA5RA" frameborder="0" allowfullscreen></iframe>
