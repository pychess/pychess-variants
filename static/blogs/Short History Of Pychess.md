<h1 align="center">And Now for Something Completely Different</h1>

<div class="meta-headline">
    <div class= "meta">
        <span class="text">2021.02.27</span>
        <span class="text"><a href="/@/gbtami">@gbtami</a></span>
        <span class="text">Blog</span>
    </div>
    <div class= "headline">Short history of pychess</div>
</div>
</br>

<p align="center">
    <img src="https://github.com/pychess/pychess-variants/blob/master/static/images/TomatoPlasticSet.svg" width="300" height="150">
</p>
Everything started with Lichess. We all love how Lichess has grown and gives us everything that chess players can imagine. However, some people still want more. There were requests to add [S-chess](https://lichess.org/forum/lichess-feedback/seirawan-chess), [Bughouse](https://lichess.org/forum/lichess-feedback/bughouse-team-up-with-a-friend), [Placement chess](https://lichess.org/forum/lichess-feedback/placement-chess-varient) and countless other chess variants to the site.

Around 2018-2019 several people started to work independently on interesting projects, and they all inspired the birth of the Pychess-Variants server.<br>

 - Igor Perelyotov created a [chessground fork](https://github.com/IgorPerelyotov/chessground/tree/dev/capablanca) to support Capablanca chess</br>

 - CouchTomato announced his first version of an internationalized [Shogi piece set on Reddit](https://www.reddit.com/r/shogi/comments/bn586v/modifiedredesigned_hidetchi_international_pieces/)</br>

 - Fabian Fichter forked Stockfish to implement several chess variants in [Fairy-Stockfish](https://github.com/ianfab/Fairy-Stockfish)</br>

It was time to put these ingredients to the pot and start cooking.
Pychess's initial commit on GitHub happened on 2019.04.19. A couple of weeks later, I [announced the project on Lichess](https://lichess.org/forum/off-topic-discussion/lichess-survey-would-you-like-to-see-eastern-chess-variants-here-on-lichess#9). And finally, I played the very first human-human game on Pychess with Fabian on 2019.05.02.

<p style="background:var(--game-hover);padding-left:1em;padding-right:30%">
ubdip:
"Just in case you are curious, it was me playing against (I guess) you on your new server just a few minutes ago.</br>
I yesterday also tried a few bullet games against the engines, and it worked very nicely (although I of course stood no chance in any variant) no matter whether it was xiangqi, shogi, or the like. Although it is of course in an early stage, the UI and functionality already are quite nice, so keep up the good work."</br>
</p>

<p style="background:var(--clock-hurry-bg);align:right;padding-left:30%;padding-right:1em">
gbtami:
"Yes, I was really curious who was that brave man :)
This first ever game immediately showed me that a basic chat window is a must.
Anyhow thx for trying it in this very early stage!"
</p>
And then the server slowly started to evolve.
 - 2019.06.23 Random-Mover BOT
 - 2019.06.29 Games saved to mongodb database
 - 2019.07.02 Internationalized Shogi and Xiangqi piece sets by [@CouchTomato87](https://www.pychess.org/@/CouchTomato87)
 - 2019.08.09 960 option for Capablanca, Crazyhouse and Standard
 - 2019.08.12 Capahouse
 - 2019.08.15 S-House
 - 2019.09.02 Grand chess
 - 2019.09.03 Grandhouse
 - 2019.09.30 Server side analysis via fairyfishnet
 - 2019.10.01 Gothic chess and Gothhouse
 - 2019.10.11 Minishogi
 - 2019.11.02 Analysis chart
 - 2019.11.15 Shako, Minixiangqi
 - 2019.12.16 Glicko2 ratings
 - 2019.12.17 Leaderboards
 - 2019.12.20 Discord-Relay BOT
 - 2019.12.28 Kyotoshogi
 - 2020.01.28 Shogun chess
 - 2020.02.02 Makruk pieces by [@furumin999](https://www.pychess.org/@/furumin999)
 - 2020.02.20 Crosstables
 - 2020.02.20 Dobutsu pieces by [@Ka_HU](https://www.pychess.org/@/Ka_HU)
 - 2020.03.16 Board editor
 - 2020.03.23 Switch from USI Shogi to UCI Shogi
 - 2020.03.29 Janggi
 - 2020.04.21 Makpong
 - 2020.04.23 Orda chess
 - 2020.05.03 Translations of Pychess site started
 - 2020.07.04 Synochess
 - 2020.08.09 Local, in browser analysis via [Fairy-Stockfish WASM port](https://github.com/ianfab/stockfish.wasm)
 - 2020.08.14 Hoppel-Poppel
 - 2020.09.15 Manchu, Dobutsu
 - 2020.10.30 Blindfold mode
 - 2020.11.08 Import games
 - 2020.11.17 S-chess960
 - 2021.01.31 Responsive layout/mobile support
 - 2021.02.09 Embed games via iframe tag
</br>
