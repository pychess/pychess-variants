# ![Kyoto](https://github.com/pychess/pychess-variants/blob/master/static/icons/KyotoShogi.svg) 京都将棋 | Kyoto Shogi

![Kyoto Shogi](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Kyoto.png)

京都将棋（Kyoto Shogi）是5×5的将棋变体，但与本将棋又有一定差别。它由田宫克哉（Tamiya Katsuya）于1976年发明。京都将棋的主要差别是每次棋子行动之后，都必须翻面改变走法，而没有升级概念。京都将棋的名字实际上来源于棋子的谐音——香车（Kyo）的另一面是本将棋的成步（と金，To），即“香と”（Kyoto）。

## 规则

初始布局如上图。

与将棋不同，棋子每次行动之后，必须翻到另一面改变形态。每个棋子的正反两面都是对应的。在本站的系统之中，会以红色字提示即将变成的形态。![Example](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/KyotoIllustration.png)

如图，图中棋子为桂-金。当桂马行动之后必须立刻翻面变成金将。当金将再次行动之后，会翻面变成桂马。

- 和将棋一样，京都将棋也有打入，打入规则与将棋基本相同，但您可以任意选择以棋子的哪一面打入。
- 出现“千日手”（即连续三次循环局面）的情况下，判为平局。

## 棋子

京都将棋除王以外，棋子有四种，分别如下：

| 第一面 | 第二面 |
| --- | --- |
| と金  | 香车  |
| 银将  | 角行  |
| 金将  | 桂马  |
| 步兵  | 飞车  |

棋子在开局时以第一面摆放。您可能发现，将棋的八种棋子都用在了京都将棋中（不含升级棋）

### 玉将、王将

![Kings](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/KyotoK.png)

玉将走法为八方走一格。

### 步兵-飞车

| 步兵                                                                                                  | 飞车                                                                                                  |
| --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| ![Pawn](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/KyotoP.png) | ![Rook](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/KyotoR.png) |

步兵可以向前走一格。

飞车可以向前后左右走任意距离。

### 金将-桂马

| 金将                                                                                                  | 桂马                                                                                                    |
| --------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| ![Gold](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/KyotoG.png) | ![Knight](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/KyotoN.png) |

金将可以直走一格或斜向前走一格。.

桂马可以向前跳马步，如图，只能跳到两个位置。

### 银将-角行

| 银将                                                                                                    | 角行                                                                                                    |
| ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| ![Silver](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/KyotoS.png) | ![Bishop](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/KyotoB.png) |

银将可以斜走一格，或向前一格。

角行可以斜走任意格数。

### と金-香车

| Tokin                                                                                                | Lance                                                                                                |
| ---------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| ![Tokin](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/KyotoT.png) | ![Lance](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/KyotoL.png) |

と金的走法和金将相同。

香车只能向前走任意距离。

## 策略

2021年11月，日本电气通信大学的盐田雅弘和伊藤毅志发表了关于京都将棋的研究论文，标志着京都将棋已经得到弱解决（弱解决：在已经证明开局状态下先手胜/负/和的”超弱解决“的前提下，已经得出达到该结果的具体过程，但尚未达到”强解决“所要求的确定所有局面的结果）。他们经过11个小时的计算机模拟，证明先手拥有57手（29回合）以内的必胜策略。
