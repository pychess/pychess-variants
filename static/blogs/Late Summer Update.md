<h1 align="center">Late Summer Update</h1>
<div class="meta-headline">
    <div class= "meta">
        <span class="text">2024.08.11</span>
        <span class="text"><a href="/@/gbtami">@gbtami</a></span>
        <span class="text">Announcements</span>
    </div>
    <div class= "headline">New variants and bug fixes</div>
</div>
</br>

<p align="center">
  <img src="https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Aliceroom3.jpg" width="300" height="150">
</p>

We are happy to announce the availability of two new variants here on Pychess: [**Alice Chess**](https://www.pychess.org/variants/alice) and [**Fog of War**](https://www.pychess.org/variants/fogofwar).

Our FAQ declares "We can't even consider adding variants that aren't supported by Fairy-Stockfish." How this can happen then at all?
But this saying had an extra (hidden) sentence from the very beginning: if a variant has a py and js lib that provides everything we need (valid move generation, FEN/UCI/SAN/PGN handling, game termination detection, etc-etc) that can be OK as well.
I remember the time when Xiangqi was not in FSF, and we used [moonfish](https://github.com/walker8088/moonfish) lib and [ElephantEye](https://github.com/xqbase/eleeye).
But explaining all of this would take too long, so we just say "it needs FSF support" in short. Handling external py/js libs for a variant instead of just use pyffis/ffish.js complicates the code base, of course, but Alice Chess and Fog of War worth it I think.

Before I was thinking Alice Chess is not possible to add, but later I realized that it is almost standard chess. Regarding the move generation, you just have to check on the "other board" that your move target square is empty.
So we can use FSF move generation then filter out invalid moves using [python-chess](https://github.com/niklasf/python-chess) and [chessops](https://github.com/niklasf/chessops) lichess libs.

Fog of war was asked for several times before, but the answer was always no, because FSF doesn't support it as well. But after looking at its rules, it is just a simple (king) extinction variant and FSF can play it! She just can look through to the fog :)
And the "fog" part of this variant affects the client side FEN rendering only, so we just have to implement hiding the pieces in fog somehow.

[**Alice Chess**](https://www.pychess.org/variants/alice) is a chess variant invented in 1953 by V. R. Parton which employs two chessboards rather than one, and a slight (but significant) alteration to the standard rules of chess. The game is named after the main character "Alice" in Lewis Carroll's work Through the Looking-Glass, where transport through the mirror into an alternative world is portrayed on the chessboards by the after-move transfer of chess pieces between boards A and B.
The rules of this variant are simple.

- A move must be legal on the board where it is played.
- A piece can only move or capture if the corresponding destination square on the other board is vacant.
- After moving, the piece is transferred to the corresponding square on the other board.

[**Fog of War**](https://www.pychess.org/variants/fogofwar) is a chess variant invented by Jens Bæk Nielsen and Torben Osted in 1989 under the name of Dark Chess. A player does not see the entire board – only their own pieces and the squares that they can legally move to.

The rules of Fog of War chess are mostly the same as standard chess. The only (and crucial) difference is the absence of checks in this variant. The game only ends when one of the kings is captured.

Lots of minor bugs have been fixed, and some minor features like blocking users and seek rating intervals were added as well.

-gbtami
