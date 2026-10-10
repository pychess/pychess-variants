# 常见问题

## Pychess

<details><summary>什么是 Pychess？</summary>

Pychess是一个收录各种象棋类游戏的网站，您可以在此游玩各种象棋类游戏，包括各地的传统象棋与现代较新的变体，以及原创的棋类游戏。
关于详细内容，请点击[这里](https://www.pychess.org/about)。</details>

<details><summary>为何取名为 Pychess？</summary>

Py 取自 Python，本站使用的程序语言。 </details>

<details><summary>这和国际象棋软件 Pychess 有何不同?</summary>

两者都致力于象棋类游戏，且开发者是同一人([gbtami](https://www.github.com/gbtami))。除此以外并没有其他的相同之处。此网站的全名其实是「Pychess Variants」，但常常简称 Pychess。
关于 Pychess 软件的信息，请点击[这里](https://pychess.github.io/)</details>

<details><summary>Pychess 与 [Lichess](https://lichess.org/) 有什么关系?</summary>

Pychess 网页的设计参考了 Lichess ，对于 Lichess 用户而言比较熟悉。事实上，Pychess 与 Lichess 并没有官方的关系。但 Pychess 使用 Lichess 的用户帐号以方便管理。
</details>

<details><summary>什么是 Fairy-Stockfish?</summary>

Stockfish 是最强的国际象棋引擎之一，而 [Fairy-Stockfish](https://github.com/ianfab/Fairy-Stockfish)是由[Ianfab](https://www.github.com/ianfab)改良 Stockfish 而成，能够分析各种棋类游戏。 </details>

<details><summary>8 级的 Fairy-Stockfish 就是最强的吗?</summary>

这仅仅是**网站**上最强的等级，但并不是 Fairy-Stockfish 的最高水平。要达到最高水平需要更多的计算量与时间，而 Pychess 上的 Fairy-Stockfish 被限制在几秒内就要完成移动。 </details>

<details><summary>我找到了一个Bug，如何反馈?</summary>

您可以在 github 上发表[issue](https://github.com/pychess/pychess-variants/issues/new)，毕竟我们所有的工作都在 github 上进行。
如果可以的话，请尽可能附上网址与详细说明。如果你不会用 github，你可以在我们的 Discord 服务器上发布，就会有人将其放上去。 </details>

## 游戏相关

<details><summary>Pychess 上收录了哪些游戏?</summary>

关于收录的游戏，请点击[游戏介绍页](https://www.pychess.org/variants).</details>

<details><summary>XX棋要怎么玩?</summary>

关于游戏玩法，请点击[游戏介绍页](https://www.pychess.org/variants)。同时，您也可以在下棋时点选左上角该棋类的名称，就会前往该棋类的介绍页面。 </details>

<details><summary>为什么 Pychess 选择这些棋?</summary>

通常会加入各地流行的传统棋类，也有加入一些较常见的国际象棋变体和 Pychess 社区玩家发明的变体。然而，有一部分棋类游戏是无法收录的。原因是 Pychess 依靠 Fairy-Stockfish 作为引擎， 我们的代码也是由它来运作，因此 Fairy-Stockfish 无法支持的变体是无法收录的。 </details>

<details><summary>Pychess 会加入沙特兰兹（国际象棋的前身）吗?</summary>

~~沙特兰兹的原始规则已经失传了，而且尚有许多十分相似的棋(例如:泰国象棋)，因此不会收录。如果你想玩，可以去其他的网站。~~ 
经过一些讨论，我们已经在2024年的秋季更新中加入沙特兰兹。尽管我们认为它已经有很多相似的变体在本站收录。
</details>

<details><summary>可以新增XX棋吗?</summary>

这要看该棋是否有足够的受欢迎度。当然如果 Fairy-Stockfish 不能支持，则该棋无法收录。你也可以直接在我们的 Discord 和 github 上问问。 </details>

## 界面

<details><summary>我要如何调整设定?</summary>

点选右上角齿轮状按扭(使用者名称旁边)并点选 "棋盘配置".</details>

<details><summary>我要如何改变棋盘和棋子外观?有通用的国际棋子吗?</summary>

同上，点选"棋盘设定"。所有的变体都有对应的国际棋子。 </details>

<details><summary>我要如何在棋盘上划记?</summary>

点右键可以在目标棋子上划圈，拖动可以产生箭头。预设都是绿色的，你可以按Shift或Ctrl来改成红色，而按Alt则会变蓝。 </details>

<details><summary>时间设定的"5+3"是什么意思?</summary>

这些是游戏时间设置，"5+3" 代表每人有 5 *分钟*, 每动一步则加 3 *秒*。你也当然也可以自由设定游戏计时。 </details>

<details><summary>"5+3(b)"那个(b)又是?</summary>

b 代表倒数计时，这与加时不同，只有特定变体会有(例如:将棋和朝鲜象棋)。当双方的时间用完时(在此范例里是 5 分钟)，则进入读秒，双方每步必须在设定时间内走棋，否则判负。在此范例中，就是每步 3 秒。通常倒数计时是 10 秒或 30 秒。 </details>

<details><summary>Ramdom-Mover是做什么的?</summary>

勾选Random-Mover可以使电脑随机走子。主要是用来让玩家熟悉游戏规则。熟悉规则之后，建议您与 Fairy-Stockfish （较低等级的）对局以增进棋感。 </details>

## 帐号与社区

<details><summary>如何登录网站?</summary>

您需要有一个 Lichess 帐号。如果你没有，请至 [Lichess](https://lichess.org/signup)注册。 </details>

<details><summary>这会使我的 Lichess 密码外泄吗?</summary>

请放心，这是不可能的。本站的登录基于 OAuth 协定且你的密码不会给予 Pychess, 就像你可以用你 Google/QQ/微信 的帐号登录其他网站一样。 </details>

<details><summary>为什么我不能在大厅聊天中发送消息?</summary>

大厅聊天仅供活跃的 Pychess 玩家使用。要在其中发言，你的帐号必须注册满 24 小时、至少完成 10 盘棋，并且其中至少 5 盘是在标准国际象棋以外的变体中进行的积分棋。你仍然可以阅读大厅聊天；此限制不影响对局聊天或锦标赛聊天。</details>

<details><summary>如何跟网站的开发者联系?</summary>

你可以试试大厅的聊天功能，虽然他们可能不会随时上线。更好的方式是用[Discord](https://discord.gg/aPs8RKr)，通常都会看得到。您可以使用加速器获得稳定的 Discord 连接。 </details>

<details><summary>此网站是如何维持运作的?</summary>

全靠赞助! 你也可以[成为赞助者](https://www.pychess.org/patron) 来支持我们并让 Pychess 网站变得更好!</details>

<details><summary>我可以加入 Pychess 的行列吗?</summary>

当然! Pychess 完全开源，在[Github](https://github.com/pychess/pychess-variants)上你可以尽情创作修改，也可以加入我们[Discord](https://discord.gg/aPs8RKr)来和大家一起合作!</details>