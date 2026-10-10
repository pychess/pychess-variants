<h1 align="center">S-Chess End-Game Tables</h1>
<div class="meta-headline">
    <div class= "meta">
        <span class="text">2024.11.27</span>
        <span class="text"><a href="/@/HGMuller">H.G.Muller</a></span>
        <span class="text">Blog</span>
    </div>
    <div class= "headline">Elephant vs Rook</div>
</div>
</br>

It is well known that the Queen-vs-Rook end-game in orthodox Chess is a general win. The number of draws that are not due to a forced tactical loss of the Queen ('fortress draws') is very small. The Elephant in S-Chess (which combines the move of Rook and Knight) does appreciably worse. By End-Game Tables produced by the [FairyGen](https://github.com/ceebo/fairygen) EGT generator show that a very large fraction of the positions are fortress draws there.

Neither Queen nor Elephant can safely attack a Rook with their orthogonal moves. So to gain the Rook the Queen must attack with its diagonal moves, the Elephant with its Knight jumps. The crucial difference is that the Queen can do this from any distance, while the Elephant must be close. That makes it impossible for the Elephant to fork King and Rook is the latter stay sufficiently far apart. And an 8x8 board is large enough to achieve that.

Since an Elephant alone cannot forcibly gain an isolated Rook or an isolated King, there is no way to progress if the Rook can cut off the strong King from its own. Like in the following position:

<img src="https://github.com/pychess/pychess-variants/blob/master/static/images/SchessEGT/KEKR.png" width="336" height="336">

It is always tricky to interpret EGT statistics, because (especially with strong pieces) most positions are not tactically quiet and lead to immediate loss of one of the pieces. So that you are not really looking at the material balance of interest. Generally won end-games can best be recognized by looking at the fraction of losses when the weak side has the move. Having the move strongly reduces the probability that you will suffer an unavoidable material loss, even though there will still be some forks and skewers.

In KQ-KR 46.3% of the black-to-move positions are lost; the remaining 54% are mostly immediate captures of Queen or King. (The probability that a white piece is attacked by the black King is already ~10%, and a Rook does about twice better.) In KE-KR only 11.6% of the positions are lost, while the fraction where you can immediately capture one of the two white pieces is independent of what these pieces are, and should thus be the same as in KQ-KR. So it appears that about three quarters of the quiet positions are draws.


