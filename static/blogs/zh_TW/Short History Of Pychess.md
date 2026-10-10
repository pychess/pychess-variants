<h1 align="center">現在，嶄新的旅程正要開始!</h1>

<div class="meta-headline">
    <div class= "meta">
        <span class="text">2021.02.27</span>
        <span class="text"><a href="/@/gbtami">@gbtami</a></span>
        <span class="text">公告</span>
    </div>
    <div class= "headline">Pychess簡史</div>
</div>
</br>

<p align="center">
    <img src="https://github.com/pychess/pychess-variants/blob/master/static/images/TomatoPlasticSet.svg" width="300" height="150">
</p>
一切都始於Lichess。我們都知道數十年來，這個開源網站不斷的演進，大大顛覆了西洋棋愛好者對下棋網站的想像。然而，還是有一些人不滿足，有些人想加入[S-chess](https://lichess.org/forum/lichess-feedback/seirawan-chess) 、[四狂象棋](https://lichess.org/forum/lichess-feedback/bughouse-team-up-with-a-friend) 、[自由擺置西洋棋](https://lichess.org/forum/lichess-feedback/placement-chess-varient) 和各式各樣的變體到網站上。

2018-2019年期間，許多人開始獨立的進行象棋變體的工作，而這些成果全都促成了Pychess的誕生。<br>

 - Igor Perelyotov 開始了一個[chessground](https://github.com/IgorPerelyotov/chessground/tree/dev/capablanca)的專案，讓它也可以支援卡帕布蘭卡。</br>

 - CouchTomato 在Reddit上發佈了第一款[國際版將棋棋子](https://www.reddit.com/r/shogi/comments/bn586v/modifiedredesigned_hidetchi_international_pieces/)。</br>

 - Fabian Fichter 將Stockfish改良成可以支援棋它象棋類遊戲的[Fairy-Stockfish](https://github.com/ianfab/Fairy-Stockfish)</br>

是時候把這些點子融合起來了:
Pychess於2019.04.19在Github寫下第一段程式碼，幾個星期後，我[在Lichess上發佈了這個計劃](https://lichess.org/forum/off-topic-discussion/lichess-survey-would-you-like-to-see-eastern-chess-variants-here-on-lichess#9)。最終，於2019.05.02我在Pychess上與Fabian玩了第一場人類vs人類的棋局。

<p style="background:var(--game-hover);padding-left:1em;padding-right:30%">
ubdip:
"我覺得你應該會好奇，剛剛其實就是我在你的新網站上跟你下棋 (我猜啦) 。 </br>
昨天也跟你的引擎下了一些快棋，他們都運作得非常好。當然，我不擅長西洋棋以外的棋，所以不管是象棋、將棋等等的我都贏不了。儘管Pychess尚處初生階段，它的使用者介面和功能都已非常完善。繼續加油!"</br>
</p>

<p style="background:var(--clock-hurry-bg);align:right;padding-left:30%;padding-right:1em">
gbtami:
"喔對，我也很好奇是到底哪個勇者? :) "
不過這第一場遊戲就讓我知道我還要再加一個聊天室功能。
無論如何，感謝你在Pychess起步時當它的第一個測試玩家!"
</p>
然後，Pychess開始慢慢進步，以下是新增的內容:
 - 2019.06.23 隨機走子機器人
 - 2019.06.29 遊戲資料儲存到mongodb資料庫
 - 2019.07.02 [@CouchTomato87](https://www.pychess.org/@/CouchTomato87)設計國際版日本將棋與中國象棋棋子
 - 2019.08.09 卡帕布蘭卡、雙狂象棋、標準西洋棋支援960隨機模式
 - 2019.08.12 雙狂卡帕布蘭卡
 - 2019.08.15 S-House
 - 2019.09.02 西洋大象棋
 - 2019.09.03 雙狂西洋大象棋
 - 2019.09.30 伺服器端可用fairyfishnet分析棋局
 - 2019.10.01 Gothic chess 和雙狂Goth
 - 2019.10.11 迷你將棋
 - 2019.11.02 分析面版
 - 2019.11.15 將軍棋, 迷你象棋
 - 2019.12.16 Glicko2 棋手評分系統
 - 2019.12.17 加入排行榜
 - 2019.12.20 Discord中繼機器人上線
 - 2019.12.28 京都將棋
 - 2020.01.28 幕府將棋
 - 2020.02.02 [@furumin999](https://www.pychess.org/@/furumin999)設計泰國象棋棋子
 - 2020.02.20 遊戲統計表
 - 2020.02.20 [@Ka_HU](https://www.pychess.org/@/Ka_HU)設計動物棋棋子
 - 2020.03.16 棋盤編輯器
 - 2020.03.23 將棋記譜由USI轉為UCI
 - 2020.03.29 韓國將棋
 - 2020.04.21 防禦泰國象棋
 - 2020.04.23 西征可汗
 - 2020.05.03 網站的翻譯開始
 - 2020.07.04 象棋 vs 西洋棋
 - 2020.08.09 支援本地分析棋局[Fairy-Stockfish WASM port](https://github.com/ianfab/stockfish.wasm)
 - 2020.08.14 跳跳西洋棋
 - 2020.09.15 滿州象棋、動物棋
 - 2020.10.30 盲棋模式
 - 2020.11.08 匯入棋局
 - 2020.11.17 隨機S-chess
 - 2021.01.31 互動式介面、支援行動版網頁
 - 2021.02.09 遊戲植入 iframe tag
</br>
