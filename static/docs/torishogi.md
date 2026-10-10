# ![Tori Shogi](https://github.com/pychess/pychess-variants/blob/master/static/icons/ToriShogi.svg) Tori Shogi

|   |   |
--- | ---
![International Set](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriIntl.png) | ![Traditional Set](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriKanji.png)

*Tori Shogi* (禽将棋/鳥将棋), Japanese for Bird Shogi, is a Shogi variant invented by Toyota Genryu in 1799, although traditionally attributed to his master Ōhashi Sōei. The game is played on a 7x7 board and is one of the oldest Shogi variants to use the drop rule. The game enjoys a relative degree of popularity to this day, including English-language books and tournaments.

## Rules

Tori Shogi rules are very similar to Shogi, so we will break it down to rules that are the same and rules that are different. The goal is to checkmate the opposing player's **Phoenix**, which is essentially the King.

* **Drops** - Captured pieces can be dropped back onto the board as your move.
* **Illegal drops** - The following drops are illegal:
  * **Dropped Swallows cannot immediately mate** - Dropping a Swallow to immediately mate the opposing Phoenix. In Pychess, this will cause the player to lose. 
  * **A swallow (equivalent of a pawn) cannot be dropped into a file containing *two* swallows of the same player**. This is different from Shogi, where the rule is only *one* pawn is allowed in each file.
  * **You may not drop a piece where it can't move, such as a Swallow on the last rank.**
* **Promotions** - Certain pieces can promote. This happens either by moving (not dropping) into the promotion zone or beginning a move from the promotion zone. The promotion zone is the last two ranks of the board. *Only two* pieces promote (unlike Shogi).
  * Promotions are compulsory, unlike in Shogi.
* **Repetition** - The rule for repetition (千日手 sennichite) in Tori Shogi is that if the same position occurs three times with the same player to play by repetition of moves, the player starting the sequence must vary the move. Otherwise, causing repetition is illegal and ends as a *loss*. For two positions to be considered the same, the pieces in hand must be the same, as well as the position on the board. Note that this is different than Shogi, where repetition leads to a draw.
* **Stalemate** is a loss for the player who cannot move their Phoenix. Note that this is technically not the actual rule: the real rule is an illegal move is a loss. Stalemate is a condition where the stalemated player can only make illegal moves.

*Sente/Gote* - In Pychess, sente/gote correspond to black/white. *Sente* means the first player, and in the default set, is indicated by the Phoenix having dark wings.

*Timer* - Tori Shogi uses a byo-yomi timer. Once the main clock expires, a player enters byo-yomi. If it is set at 30 seconds, then that player will only have 30 seconds to make his move from then for each of his/her moves or else lose the game on time.

## Intro to Pieces

All Tori Shogi pieces (except two) are new, and learning them may be daunting for new players. This guide will try to simplify this as much as possible. For starters, we will use the internationalized set\*. The symbols used in the international set are unique in that nearly every piece has a *mnemonic device in the shape of the bird/picture on the piece*, where the birds point to where they move. How does this work? Take a look at this *fake piece* below:

![A fake piece](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/FakeBird.png)

All the points and protrusions on this piece (heads, wings, etc) would point to the directions it moves. Now, on to the real pieces.

Two pieces are very straightforward as they are just renamed versions of the king and pawn from Shogi. The rest of the pieces are all unique. To make things simple, these new pieces' movements fall into two main patterns: 

1. **Pieces that move like a king (single-step movers)**
2. **Pieces whose moves resemble a Y-shape (right-side up or upside-down)**

As mentioned in the rules, **only two pieces promote**. The weakest piece in the game promotes to a very weak piece, while the strongest unpromoted piece in the game promotes to a far stronger piece. These two pieces will be discussed last, and both fall into the Y-shape class (both happen to be right-side up Y's).

\* *Note* - Unlike other East Asian variants on this site, Tori Shogi uses the internationalized set as a default. This is because of vastly increased complexity of the kanji in this game, the relative complexity of the moves (which would benefit from mnemonic devices as employed by the international pieces), and the fact that these pieces are not used in other variants as far as we know. The traditional kanji set is of course available as well.

## The Fundamental Pieces

These are the only two pieces without mnemonic devices in the birds, and these are the two pieces needed in almost every traditional chess variant. One is essentially the king, and the other is essentially a pawn, so the piece size and number should already be large clues as to which pieces these are.

### Phoenix

![Phoenix](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Phoenix.png)

The Phoenix (鵬, *ootori*) moves exactly like a chess king: one step in any direction. In the internationalized set, sente (marked as black) is the Phoenix with dark wings, while gote (marked as white) is the Phoenix with light wings.

### Swallow

![Swallow](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Swallow.png)

The Swallow (燕, *tsubame*) is the same as the Shogi Pawn (but different than the Chess Pawn). It moves and captures by moving forward one square. This is the weakest piece in the game, just like any other pawn.

(While there is no explicit mnemonic in the Swallow's design, the bird is oriented upwards.)

The Swallow is one of the two promotable pieces, and it promotes to the **Goose**.

## King-like Pieces

![King-like pieces](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/KinglikePieces.png)

These pieces are like the generals from Shogi, but even stronger. Why are they "king-like"? They move very much like a King (only step into any of the adjacent 8 squares) except missing a square or two, and they start right next to the Phoenix (this game's "king"). The key to these pieces is simply remembering which squares are their blind spots. On the international set, this is indicated by an open area in the side corresponding to the piece's blind spot.

### Falcon

![Falcon](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Falcon.png)

The Falcon (鷹, *taka*) moves like a king except *it cannot move straight backwards* (in the picture, this is the empty space between the talons and tail at the bottom of the piece). This is the most powerful unpromoted piece in the game, as its large coverage allows it to deliver checkmate very easily.

The Falcon is the other of the two promotable pieces, and it promotes to the **Eagle**.

### Crane

![Crane](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Crane.png)

The Crane (鶴, *tsuru*) moves like a king except *it cannot move sideways (left or right)* (on the picture, this is the empty space between the crane and the water it's standing on -- yes, treat the water as part of the mnemonic). While not as strong as the Falcon, the Crane is also a very strong piece.

## ⅄-shaped Pieces

![Upside-down Y pieces](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/UpsidedownYPieces.png)

The main feature of these pieces is that their move patterns resemble an upside-down Y (⅄). *One is weak and can jump (like a chess knight). The other(s) is stronger and is a ranging piece (i.e. can move as many steps as it wants in that direction).*

### Pheasant

![Pheasant](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pheasant.png)

The Pheasant (雉, *kiji*) moves either one space diagonally backward or can jump two spaces straight forward. *Jump* means that it can still go there even if there is a piece in the way. Essentially, this piece is the Tori Shogi equivalent of the Shogi knight because of the jump.

Sidenote: the red circle above the pheasant is the "rising sun" -- the green pheasant depicted here is the national bird of Japan.

### Quails (Left and Right)

|   |   |
--- | ---
![LeftQuail](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/LeftQuail.png) | ![RightQuail](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/RightQuail.png)

The Quails (鶉, *uzura*) start in the corners of the board and are two separate pieces called the **Left Quail** and the **Right Quail**. Their movements are mirror images of each other. Both Quails can move any number of spaces forward (like a Rook or Lance), but they can also move backwards diagonally in the direction away from their starting side of the board. For example, the *Left* Quail can move diagonally *right* (in the direction of its talons). Finally, they can also move one space diagonally backwards on the opposite side, towards the bird's tail.

The Quails are tied with the Falcon for being the strongest unpromoted piece in the game. However, unlike the Falcon, they cannot promote.

A note on the *kanji* set: Traditional sets just use the character for quail on the front and "left" or "right" on the back. As players playing online cannot physically peek under the pieces, we put the kanji for left (左) and right (右) above the kanji for quail.

## Y-shaped Pieces (Promoted Pieces)

![Promoted pieces](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PromotedPieces.png)

Finally, the last two pieces are the two promoted pieces, which also happen to share a similarity in that their move patterns resemble a Y. *One is weak and can jump (like a chess knight). The other is stronger and is a ranging piece (i.e. can move as many steps as it wants in that direction).* 

### Goose

![Goose](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Goose.png)

The Wild Goose (鴈, *kari*), or simply Goose, is the promoted form of the Swallow. It can jump exactly two spaces diagonally forward (left or right), or exactly two spaces straight backwards. Because of this unique pattern, the Goose can only reach a very limited number of spaces on the board (about one quarter of the board). 

### Eagle

![Eagle](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Eagle.png)

The Mountain Hawk Eagle (鵰, *kumataka*), or simply Eagle, is the promoted form of the Falcon. Its moves are broken down into three components:

1. It ranges in a Y-shape (wings and tail) -- It can move any number of spaces diagonally forward or straight backwards.
2. It can move like a king (one step in any of the 8 spaces around the piece) -- this technically makes it a "Y-shaped piece" AND a "king-like piece", but the Y-shape is the dominant part of this piece.
3. Finally, it can also move up to two spaces diagonally backwards (indicated by the Eagle's talons). This is not a jumping move; it can be blocked.

This is by far the strongest piece in the game.

## Notation

George Hodges originally created a notation system in 1976 that uses two-letter piece abbreviations. As we cannot use two-letters on Pychess, we use a modified version. The notation is otherwise the same as Shogi. We will still summarize the notation for players who are not familiar with Shogi notation. 

### Coordinates

One noticeable difference is that the board coordinates are switched from chess. First is the file, then the rank. In traditional Hodges style, the first space is 1a. However, in modern days, international players prefer to use numbers (Hodgkin style), so the first space is "1-1". This is also how coordinates are described in Japanese (although with the second number written in kanji).

The origin is the bottom left for the white player/gote. However, since most diagrams are oriented for the black player (sente, first player), these will seem to originate from the top right. As an example, the white phoenix is on square 4-1.

### Piece Abbreviations
Name | Hodges  | Pychess
------------ | ------------- | -------------
Phoenix | Ph | K 
Swallow | Sw | S
Falcon | Fa | F
Crane | Cr | C
Pheasant | Ph | P 
Left Quail | LQ | L
Right Quail | RQ | R 
*Goose* | +Sw | +S
*Eagle* | +Fa | +F

For the most part, the Pychess notation should make sense, as we use the first letter of the piece names. The only problem is two pieces start with a P, the Phoenix, and Pheasant. Therefore, the Phoenix is assigned to K, as it functions as the game's king. You may also think of it as a "Phoeni**K**s."

### Symbols

* Drops are indicated with a \*. For example, a Swallow drop on 3-3 is "S\*33"
* Moves that end in promotion add a + at the end. A Swallow promoting on 1-1 would be S11+.
* Checks and checkmates are not notated.

## Strategy

### Piece Values

Here are piece values used in a Tori Shogi app ([see here](https://happyclam.github.io/project/2019-01-03/torishogiapp)). These may not be the most accurate but can serve as a reference for comparing piece values.

Piece | Value 
------------ | -------------
Swallow | 1 
Pheasant | 3
Crane | 6
Quails | 7
Falcon | 7
*Goose* | 2
*Eagle* | 16

Pieces are worth slightly less in hand, except for the Swallow, which is slightly worth more in hand.

Note that while these are the values used in that particular Shogi app, **please take these numbers with a grain of salt**. it has been the author's experience that **cranes are actually worth more than quails**, especially as they are more capable of delivering checkmate. In most cases, it's worth it to trade your own quail to take a crane. This has also been confirmed by Stockfish analysis

### Openings

There are essentially four reasonable opening moves...

1+2: Take one of the opponent's swallows that are immediately opposing yours

3+4: Move one of your cranes diagonally, in front of one of your pheasants

Why is moving the crane straight one space bad? It stops defending the space in front of your pheasant, leading to an opportunistic swallow drop, followed by a pheasant capture.

![Weak spots](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriWeakSpots.png)

These spots are weak spots. Even if you do advance the crane, you want to remember those spots and defend it with the phoenix or falcon so that your crane does not have to babysit these squares!

As for other possibilities, moving a swallow to be captured by another swallow is a losing move. Pheasants can't move. Advancing the quails is not very advantageous (unless you are trying for a castle), and moving the phoenix is also a bit too passive compared to the top options above.

### Swallows

Swallows can be said to be the same as Shogi pawns, but they are also vastly different. The ability to have two swallows per file changes strategy completely. Because of this, swallows are practically the heart and soul of the game, and knowing how to play them is one of the key parts to learning Tori Shogi.

To keep things brief, there are three things to keep in mind regarding swallows:

**Doubled swallows** (i.e. one swallow behind another) are very powerful. If you're able to advance swallows far enough, putting a swallow in front (for offense) or behind (for defense) can lock down a file. The one caveat is that you can no longer drop swallows on this file, and it's also hard to move. These two swallows can act like a wall or barrier, and in some cases, may make mating even more difficult. Be careful not to overextend on doubled swallows.

Because swallows tend to fly on and off the board at a dizzying rate, **you can treat them almost as currency**. Sometimes you may have so much that you have a lot of flexibility for attack. The front lines of the board tend to be defined by opposing swallows with a gap in-between (no man's land). You can "spend" a swallow from your hand to essentially advance your line forward. You should do this when you have another piece (typically a crane or quail) to back up the advanced swallow.

When mounting a deep attack with swallows, if you manage to push one to the third to last rank (just behind the promotion zone), you can see the prize enemy bird in sight, but be careful! If you push your swallow *forward*, **you instead make a goose** because of forced promotion! To finish off the attack, you need to have a swallow ready to drop (and the ability to do so) to claim the bird on the other end.

![Don't make this mistake!](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriGooseMistake.png)

### Edge Attacks

Edge attacks are a great way of starting an attack. As mentioned above, you can "spend" a swallow to push your swallow up and eventually make your way to claim the enemy quail (remember to use a swallow *drop* in front of the quail to take it!). However, there is one caveat! The following image demonstrates the sequence when making a successful edge attack:


![Edge Sequence!](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriEdgeSequence.png)

With nowhere to go, the quail will now be captured by a swallow, a great tradeoff! *However*, that is **IF** the quail has nowhere to go. Remember, it can now go diagonally backwards! If a crane is sitting in the space in front of the pheasant, then yes, the quail is now yours. Should that square be empty, then a good response to that initial swallow drop is to simply ignore it! If the swallow advances and takes your swallow, you retake with the quail. Once he pushes the remaining swallow, you can simply retreat your quail to the next file, and the *edge attack is foiled* (see below).

![Edge Sequence!](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriFailedEdgeAttack.png)

So this means the best time to make an edge attack is when a piece is blocking the square in front of the pheasant. In a majority of cases, this will be the crane. A good response to the swallow drop initiating an edge attack is to simply pull back the crane, opening up a retreat square for the quail. Bringing this back to the initial tips for openings, this means that opening with the crane diagonally in front of the pheasant is not a flawless strategy, and it has its own drawbacks!

### Endgame

The endgame is the most important part of Tori Shogi. You can play a perfect early and midgame, but if you cannot convert into a checkmate, the opponent can convert your blunders into a quick checkmate! The goal in the endgame is to collect just enough pieces needed to checkmate the opponent's phoenix. You may not even need a material advantage. Simply taking advantage of the right positioning will do. Since there are so many ways the game can end, it would be impossible to cover different scenarios in this brief guide. I'll give you a few major tips though.

* **Cranes and Falcons** are the classic pieces for mating, similar to Shogi generals. Be familiar with using these pieces in tandem to deliver checkmate.
* **Geese** are very weak pieces, but they can be critical to checkmate as they are one of the few pieces that can attack forwards and diagonally. Try to get a goose two files away from the opponent's phoenix, then drop it back to position yourself for a strong crane/falcon drop.
* **Falcons** are key pieces for making an easy checkmate. One great way to use them is to not drop them to immediately check the phoenix (where it can simply run away), but to drop it next to a spot where it *can* check the phoenix the next turn. Doing so will result in promotion to an Eagle, which is a much more powerful chaser. What can make this even more effective is when you drop it so that the falcon also threatens another piece. So even if the opponent blocks the simultaneous promotion and check, you can still grab another piece and promote.
* **Pheasants and Quails** have backwards diagonal attacks too, remember that! They are most essential for ridding the phoenix of its defenders. Most importantly, remember the quail has an unlimited diagonal and can even be used to protect your own phoenix as you make your attack. Remember that as you go all in an attack, many pieces will be exchanged. If you fail to deliver checkmate, the opponent can use these new pieces against you. That's where the quails can be very useful.
* Do not forget that it is illegal to checkmate with a dropped Swallow. It *is* okay to check with a dropped swallow, leading to a checkmate by another piece the next turn though!

## Handicaps

Unlike chess and more similar to go, handicaps are a big part of teaching and should not be treated as one player giving pity to another. They are a great way to learn the game, and there are even standard strategies for different types. In Shogi, handicap games are fairly standard, and Tori Shogi should be no different.

While normal games have black (*sente*) starting, **white is the handicap giver and therefore goes first**. White is called *uwate* while black is called *shitate*. Despite the handicap, the material difference can be overcome because of drops. And since there are fewer powerful pieces, black/*shitate* loses a lot more when a piece a captured.

Common handicaps are as follows:

* One-piece: Left Quail
* One-piece: Falcon
* Two-piece: Falcon and Left Quail
* Three-piece: Falcon and both Quails

<iframe width="560" height="315" src="https://www.youtube.com/embed/5f9QKK7cm20" frameborder="0" allowfullscreen></iframe>
