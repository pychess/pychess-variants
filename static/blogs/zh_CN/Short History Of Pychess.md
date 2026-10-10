<h1 align="center">现在，崭新的旅程正要开始!</h1>

<div class="meta-headline">
    <div class= "meta">
        <span class="text">2021.02.27</span>
        <span class="text"><a href="/@/gbtami">@gbtami</a></span>
        <span class="text">公告</span>
    </div>
    <div class= "headline">Pychess简史</div>
</div>
</br>

<p align="center">
    <img src="https://github.com/pychess/pychess-variants/blob/master/static/images/TomatoPlasticSet.svg" width="300" height="150">
</p>
一切都始于Lichess。我们都知道数十年来，这个开源网站不断的演进，大大颠覆了西洋棋爱好者对下棋网站的想像。然而，还是有一些人不满足，有些人想加入[S-chess](https://lichess.org/forum/lichess-feedback/seirawan-chess) 、[四狂象棋](https://lichess.org/forum/lichess-feedback/bughouse-team-up-with-a-friend) 、[自由摆置西洋棋](https://lichess.org/forum/lichess-feedback/placement-chess-varient) 和各式各样的变体到网站上。

2018-2019年期间，许多人开始独立的进行象棋变体的工作，而这些成果全都促成了Pychess的诞生。 <br>

 - Igor Perelyotov 开始了一个[chessground](https://github.com/IgorPerelyotov/chessground/tree/dev/capablanca)的专案，让它也可以支援卡帕布兰卡。 </br>

 - CouchTomato 在Reddit上发布了第一款[国际版将棋棋子](https://www.reddit.com/r/shogi/comments/bn586v/modifiedredesigned_hidetchi_international_pieces/)。 </br>

 - Fabian Fichter 将Stockfish改良成可以支援棋它象棋类游戏的[Fairy-Stockfish](https://github.com/ianfab/Fairy-Stockfish)</br>

是时候把这些点子融合起来了:
Pychess于2019.04.19在Github写下第一段程式码，几个星期后，我[在Lichess上发布了这个计划](https://lichess.org/forum/off-topic-discussion/lichess-survey-would-you-like-to-see-eastern-chess-variants-here-on-lichess#9)。最终，于2019.05.02我在Pychess上与Fabian玩了第一场人类vs人类的棋局。

<p style="background:var(--game-hover);padding-left:1em;padding-right:30%">
ubdip:
"我觉得你应该会好奇，刚刚其实就是我在你的新网站上跟你下棋 (我猜啦) 。 </br>
昨天也跟你的引擎下了一些快棋，他们都运作得非常好。当然，我不擅长西洋棋以外的棋，所以不管是象棋、将棋等等的我都赢不了。尽管Pychess尚处初生阶段，它的使用者介面和功能都已非常完善。继续加油!"</br>
</p>

<p style="background:var(--clock-hurry-bg);align:right;padding-left:30%;padding-right:1em">
gbtami:
"喔对，我也很好奇是到底哪个勇者? :) "
不过这第一场游戏就让我知道我还要再加一个聊天室功能。
无论如何，感谢你在Pychess起步时当它的第一个测试玩家!"
</p>
然后，Pychess开始慢慢进步，以下是新增的内容:
 - 2019.06.23 随机走子机器人
 - 2019.06.29 游戏资料储存到mongodb资料库
 - 2019.07.02 [@CouchTomato87](https://www.pychess.org/@/CouchTomato87)设计国际版日本将棋与中国象棋棋子
 - 2019.08.09 卡帕布兰卡、双狂象棋、标准西洋棋支援960随机模式
 - 2019.08.12 双狂卡帕布兰卡
 - 2019.08.15 S-House
 - 2019.09.02 西洋大象棋
 - 2019.09.03 双狂西洋大象棋
 - 2019.09.30 伺服器端可用fairyfishnet分析棋局
 - 2019.10.01 Gothic chess 和双狂Goth
 - 2019.10.11 迷你将棋
 - 2019.11.02 分析面版
 - 2019.11.15 将军棋, 迷你象棋
 - 2019.12.16 Glicko2 棋手评分系统
 - 2019.12.17 加入排行榜
 - 2019.12.20 Discord中继机器人上线
 - 2019.12.28 京都将棋
 - 2020.01.28 幕府将棋
 - 2020.02.02 [@furumin999](https://www.pychess.org/@/furumin999)设计泰国象棋棋子
 - 2020.02.20 游戏统计表
 - 2020.02.20 [@Ka_HU](https://www.pychess.org/@/Ka_HU)设计动物棋棋子
 - 2020.03.16 棋盘编辑器
 - 2020.03.23 将棋记谱由USI转为UCI
 - 2020.03.29 韩国将棋
 - 2020.04.21 防御泰国象棋
 - 2020.04.23 西征可汗
 - 2020.05.03 网站的翻译开始
 - 2020.07.04 象棋 vs 西洋棋
 - 2020.08.09 支援本地分析棋局[Fairy-Stockfish WASM port](https://github.com/ianfab/stockfish.wasm)
 - 2020.08.14 跳跳西洋棋
 - 2020.09.15 满州象棋、动物棋
 - 2020.10.30 盲棋模式
 - 2020.11.08 汇入棋局
 - 2020.11.17 随机S-chess
 - 2021.01.31 互动式介面、支援行动版网页
 - 2021.02.09 游戏植入 iframe tag
</br>
