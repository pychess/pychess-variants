<h1 align="center">Fairy-Stockfish on PyChess</h1>

<div class="meta-headline">
    <div class= "meta">
        <span class="text">2022.08.04</span>
        <span class="text"><a href="/@/gbtami">@gbtami</a></span>
        <span class="text">Announcements</span>
    </div>
    <div class= "headline">NNUE Everywhere</div>
</div>
</br>
<p align="center">
    <img src="https://github.com/pychess/pychess-variants/blob/master/static/images/Weights-nn-62ef826d1a6d.png" width="300" height="150">
</p>
</br>

The first time I heard about neural network usage in chess engine programming was around 2015 when Matthew Lai announced the first release of his new engine Giraffe on [CCC](http://talkchess.com/forum3/viewtopic.php?t=56913).
Later he joined the Google DeepMind team, and they developed the legendary [AlphaZero](https://arxiv.org/abs/1712.01815) in 2017, a general reinforcement learning algorithm that masters chess, shogi, and Go through self-play.
It was a huge sensation, but it needed 4 first generation TPUs to run and an enormous amount of TPUs to train the net, meaning it was not available for the masses.

Open source developers started to work on similar projects immediately, and in 2018 Yu Nasu introduced a very powerful new approach, NNUE (ƎUИИ, Efficiently Updatable Neural Networks), which was used in Shogi engines later.

After long debates, with the help of Japanese programmer Nodchip, Stockfish developers released Stockfish 12 NNUE in 2020.

As you may know [Fairy-Stockfish](https://github.com/ianfab/Fairy-Stockfish) gradually added NNUE support to all variants starting from version 13 and finally to its [WASM port](https://github.com/fairy-stockfish/fairy-stockfish.wasm) as well.
This opened up the possibility to add NNUE support to pychess.org engine play and analysis on server side and in browser analysis on client side.

What does all this mean? We have superhuman level engine play and analysis on pychess site in every variant!
How does it work? First go to https://fairy-stockfish.github.io/nnue/ and download .nnue files you need for your favorite variants. Then use the Board settings panel to select it, and reload the pychess browser tab.
After the reload when you enable local engine analysis it will show: Fairy-Stockfish 14+ NNUE in the panel header.

Huge thanks to [@ubdip](https://www.pychess.org/@/ubdip) to make this possible, Untitled_Entity who trained the Synochess net, and Belzedar who trained almost all the other nets tirelessly!


Enjoy!
