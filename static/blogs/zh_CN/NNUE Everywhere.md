<h1 align="center">在Pychess上使用Fairy-Stockfish</h1>

<div class="meta-headline">
    <div class= "meta">
        <span class="text">2022.08.04</span>
        <span class="text"><a href="/@/gbtami">@gbtami</a></span>
        <span class="text">公告</span>
    </div>
    <div class= "headline">NNUE 可使用于所有变体</div>
</div>
</br>
<p align="center">
    <img src="https://github.com/pychess/pychess-variants/blob/master/static/images/Weights-nn-62ef826d1a6d.png" width="300" height="150">
</p>
</br>

我第一次听说神经网络在国际象棋引擎编程中的应用是在 2015 年左右，当时 Matthew Lai 在 [CCC](http://talkchess.com/forum3/viewtopic.php?t=56913) 上发布了他的新引擎 Giraffe 的第一个版本。
后来他加入了谷歌 DeepMind 团队，他们在 2017 年开发了传说中的 [AlphaZero](https://arxiv.org/abs/1712.01815)，这是一种通用的强化学习算法，可以通过自我对弈精通国际象棋、将棋和围棋。
这是一个巨大的轰动，但它需要 4 个第一代 TPU 才能运行，并且需要大量的 TPU 来训练网络，这意味着它并不够大众化。

开源开发人员立即开始从事类似的项目，并在 2018 年日本工程师 Yu Nasu 引入了一种非常强大的新方法 NNUE（ƎUИИ，Efficiently Updatable Neural Networks），用于 Shogi 引擎。

经过长时间的进化，在日本工程师 Nodchip 的帮助下，Stockfish 开发人员于 2020 年发布了 Stockfish 12 NNUE。

您可能知道 [Fairy-Stockfish](https://github.com/ianfab/Fairy-Stockfish) 从版本 13 开始对所有变体以及[WASM 端口](https://github. com/fairy-stockfish/fairy-stockfish.wasm）提供 NNUE 支持。
这为在服务器端的 pychess.org 引擎对弈和分析以及客户端的浏览器分析中添加 NNUE 支持提供了可能性。

因此，我们在 pychess 上的每个变体都有超人类级别的引擎游戏和分析。
首先访问 https://fairy-stockfish.github.io/nnue/ 并下载您喜欢的变体所需的 .nnue 文件。然后在 Board settings 面板中选择，然后重新加载 pychess 浏览器。
重新加载后，当您启用本地引擎分析时，它将在面板标题中显示：Fairy-Stockfish 14+ NNUE。

非常感谢 [@ubdip](https://www.pychess.org/@/ubdip) 对NNUE做出的贡献，而Untitled_Entity 训练了 Synochess 网络，Belzedar 不知疲倦地训练了几乎所有其他网络！


享受吧！
