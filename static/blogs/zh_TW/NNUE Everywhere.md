<h1 align="center">在Pychess上使用Fairy-Stockfish</h1>

<div class="meta-headline">
    <div class= "meta">
        <span class="text">2022.08.04</span>
        <span class="text"><a href="/@/gbtami">@gbtami</a></span>
        <span class="text">公告</span>
    </div>
    <div class= "headline">NNUE 可使用於所有變體</div>
</div>
</br>
<p align="center">
    <img src="https://github.com/pychess/pychess-variants/blob/master/static/images/Weights-nn-62ef826d1a6d.png" width="300" height="150">
</p>
</br>

我第一次聽說神經網絡在國際象棋引擎編程中的應用是在 2015 年左右，當時 Matthew Lai 在 [CCC](http://talkchess.com/forum3/viewtopic.php?t=56913) 上發布了他的新引擎 Giraffe 的第一個版本。
後來他加入了谷歌 DeepMind 團隊，他們在 2017 年開發了傳說中的 [AlphaZero](https://arxiv.org/abs/1712.01815)，這是一種通用的強化學習算法，可以通過自我對弈精通國際象棋、將棋和圍棋。
這是一個巨大的轟動，但它需要 4 個第一代 TPU 才能運行，並且需要大量的 TPU 來訓練網絡，這意味著它並不夠大眾化。

開源開發人員立即開始從事類似的項目，並在 2018 年日本工程師 Yu Nasu 引入了一種非常強大的新方法 NNUE（ƎUИИ，Efficiently Updatable Neural Networks），用於 Shogi 引擎。

經過長時間的進化，在日本工程師 Nodchip 的幫助下，Stockfish 開發人員於 2020 年發布了 Stockfish 12 NNUE。

您可能知道 [Fairy-Stockfish](https://github.com/ianfab/Fairy-Stockfish) 從版本 13 開始對所有變體以及[WASM 端口](https://github. com/fairy-stockfish/fairy-stockfish.wasm）提供 NNUE 支持。
這為在服務器端的 pychess.org 引擎對弈和分析以及客戶端的瀏覽器分析中添加 NNUE 支持提供了可能性。

因此，我們在 pychess 上的每個變體都有超人類級別的引擎遊戲和分析。
首先訪問 https://fairy-stockfish.github.io/nnue/ 並下載您喜歡的變體所需的 .nnue 文件。然後在 Board settings 面板中選擇，然後重新加載 pychess 瀏覽器。
重新加載後，當您啟用本地引擎分析時，它將在面板標題中顯示：Fairy-Stockfish 14+ NNUE。

非常感謝 [@ubdip](https://www.pychess.org/@/ubdip) 對NNUE做出的貢獻，而Untitled_Entity 訓練了 Synochess 網絡，Belzedar 不知疲倦地訓練了幾乎所有其他網絡！


享受吧！
