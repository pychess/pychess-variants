# ![Caparandom](https://github.com/pychess/pychess-variants/blob/master/static/icons/caparandom.svg) 任意制卡帕布兰卡象棋 | Caparandom

任意制卡帕布兰卡象棋（Capablanca 960）为卡帕布兰卡象棋的变种玩法，在原本的规则上结合菲舍尔任意制象棋的规则。您可以在游戏开始时勾选“960模式”来游玩此玩法。

请在开始游戏前熟悉卡帕布兰卡象棋和菲舍尔任意制象棋的相关说明。

*（译者注：尽管在卡帕布兰卡象棋中引入960规则，所有可能的局面数并非960种，但PyChess使用960称呼所有使用任意制的象棋玩法。因此不使用“卡帕布兰卡象棋 960”的直译而采用任意制作为前缀）*

## 任意制规则

除了兵还在原位以外，其余棋子的初始布局将由电脑随机产生。随机的过程遵循下列原则：

- 黑白双方的棋子必须呈对称排列，如同原本的对称特征。
- 两枚象不可位于同色格，必须一黑一白。
- 两枚车不能在王的同一侧，必须一左一右（可以不相邻）。

在任意制卡帕布兰卡象棋中，包括基本布局在内，棋盘初始排列一共有 4×4×8×7×6×5×4÷2=53760 种。

王车易位仍旧允许，即使王和车不在原本位置。进行的条件与原本规则基本一致：

- 王和车到达各自目的位置的路线不得有其他棋子阻隔。
- 进行易位的王和车必须都未动过。
- 王被将军时不能易位。
- 王移动时经过或到达的格子不能被对方攻击。
  不论王和车的初始位置在哪里，王车易位后二者所处位置是固定的——和国际象棋一样。
  当王与a线方向的车易位时，王移到 c1(c8)，车到 d1(d8)；当与j线方向的车易位时，王到 g1(g8)，车到 f1(f8)。

其余的规则与原本规则相同。

## 新棋子

### 大主教 | Archbishop

![Archbishop](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Princesses.png)

以上为本站大主教可能出现的各种棋子造型。其中老鹰为 S-chess 所用。

![Archbishop moves](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Archbishop.png)

大主教是一个复合棋子，它可以看成是马+象。在其他棋类里，也有称为“公主”(Princess)的。

它棋子的造型一般如图，把象的下半部分拼在马下面。本站有其他的造型可以选择，不同的棋也有不同的造型。

在走法上，它能单独对角格的王形成威胁。大主教的价值略低于首相和后。

### 首相 | Chancellor

![Chancellor](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Empresses.png)

以上是本站中首相可能会用的几种棋子造型。大象为 S-chess 所用。

![Chancellor moves](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Chancellor.png)

首相是一个复合棋子，它可以看成车+马。如同大主教，它的棋子造型就是马头拼上车的下半部分。其他的棋有不同的造型，本站也可以切换棋子造型。

首相的价值一般认为比大主教略高一些，但和后相等或略小。
