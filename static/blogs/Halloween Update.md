<h1 align="center">Halloween Update</h1>
<div class="meta-headline">
    <div class= "meta">
        <span class="text">2024.10.31</span>
        <span class="text"><a href="/@/gbtami">@gbtami</a></span>
        <span class="text">Announcements</span>
    </div>
    <div class= "headline">New variants and bug fixes</div>
</div>
</br>

<p align="center">
  <img src="https://github.com/pychess/pychess-variants/blob/master/static/images/witch.png" width="300" height="150">
</p>

We're pleased to announce that we've had another break from our variant moratorium to introduce FOUR new variants! You may have seen these on the site, but in case you haven't been paying attention, here they are!

[**Antichess**](https://www.pychess.org/variants/Antichess) - You may be familiar with this from Lichess. Lose all your pieces (or get stalemated) to win the game.

[**Antichess 960**](https://www.pychess.org/variants/antichess960) - Of course, it wouldn't be Pychess if we didn't have another spin on variants. This is Antichess but with randomized Chess960 positions.

[**Horde**](https://www.pychess.org/variants/horde) - Also from Lichess. Destroy the horde to win.

[**Horde 960**](https://www.pychess.org/variants/Horde960) - Same deal, with 960 rules for black.

[**RacingKings**](https://www.pychess.org/variants/racingkings) - Also from Lichess. Race your King to the eighth rank to win.

[**RacingKings 960**](https://www.pychess.org/variants/racingkings960) - Same deal, but with 1440 random start positions. (We use "960" as the synonym for "random".)

[**Shatranj**](https://www.pychess.org/variants/shatranj) - Shatranj is an old form of chess, as played in the Sasanian Empire. Its origins are in the Indian game of Chaturanga. Modern chess gradually developed from this game, as it was introduced to Europe by contacts in Muslim Al-Andalus (modern Spain) and in Sicily in the 10th century.

The main change on the server side is re-implementation of our arena tournament pairing.
It uses now [Edmonds' algorithm](https://en.wikipedia.org/wiki/Blossom_algorithm) for [maximum weight matching](https://en.wikipedia.org/wiki/Maximum_weight_matching) via [rustworkx](https://github.com/Qiskit/rustworkx) similar to Lichess.

We got some great contributions from our beloved users.
New piece sets for Shogi, Cannon Shogi by https://www.pychess.org/@/Watermelonely
New colorized piece set for Chak by https://www.pychess.org/@/ronin3b

As usual, some minor bugs have been fixed as well.

-gbtami
