# ![Spartan](https://github.com/pychess/pychess-variants/blob/master/static/icons/spartan.svg) 斯巴达象棋 | Spartan Chess

![Spartan](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Spartan.png)

斯巴达象棋(Spartan Chess)是由 Steven Streetman 设计的象棋类游戏，2010年收录在ChessVariants网站，具体的设计时间不详。该棋是使用不对称棋组的棋类中很受欢迎的一个棋种。平衡性方面，该棋在没有Fairy Stockfish等现代引擎作为辅助的那个年代依然做到不错的平衡。

斯巴达象棋的背景设定在历史上斯巴达与波斯之间的战争。黑方代表斯巴达军队，白方代表波斯军队。白方的棋组为国际象棋棋组，而斯巴达棋组则是完全不同的。最大的特点是斯巴达棋组有两个王。除此之外，棋子的行动方式也和国际象棋完全不同。
 
## 基本规则
1.  棋盘布置如上图。
2.	波斯方（白）的棋子和规则与国际象棋完全相同。斯巴达方（黑）的棋子见下面介绍。
3.	波斯方（白）先手。
4.	斯巴达方（黑）没有易位。
5.	斯巴达方的两个王同时被攻击的情况，即双重将军(duple-check)。这种情况黑方必须应将。黑方不能故意让两个王同时送吃。
6.	斯巴达方有两个王。因此白方的胜利条件略有不同。白方可以先吃掉其中一个王然后将死另外一个王获胜，或者同时攻击两个王，使得两个王都不可能解除将军。详细的规则见下面走法。
7.	双方的兵只能升变为各自棋组拥有的棋子。黑方兵可以升变为王，但仅可以在黑方只剩一个王的情况下才能这么做。
8.  没有吃过路兵。
9.  其余的规则如逼和、循环局面的判定与国际象棋相同。

## 斯巴达棋组介绍
斯巴达棋组有王2枚、将军1枚、统战官1枚、队长2枚、队副2枚、重步兵8枚。

下面的棋子图表中的图例意义如下：
* 圆点：棋子可以移动到的位置。在本文中，它们默认可以越子。
* 箭头：棋子可以沿该方向一直移动任意格数，直到被其他棋子阻挡为止。
* 颜色：绿色=走吃皆可，蓝色=只走不吃，红色=只能吃子不能走子

### 王 | King (K)

![King](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/SpartanKing.png)
 
王和国际象棋的国王完全相同。
主要的区别在于斯巴达方有两个王。不能使得场上的所有王同时被攻击。
**详细说明：**
当斯巴达方两个王都在场时，王不受将军规则的制约，可以送吃，只有一个王被将军时也不必应将。若两个王同时被将军（Duple-check），则必须应将，使得至少一个王脱离被攻击状态。若不能解除，则这一方落败。故意使得两个王同时被攻击是违规的。
当斯巴达方只有一个王在场时，则不能送吃，被将军时必须应将，如同国际象棋一样。

### 重步兵 | Hoplite (H)

![Hoplite](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/SpartanHoplite.png)
 
重步兵相当于斯巴达象棋的兵，它的走法和贝罗琳娜兵(Berolina Pawn)类似，即国际象棋兵的走吃互换版本，走子只能斜向前走一格，吃子只能向前走一格。在初始位置时，可以斜向前移动两格。
重步兵在初始位置斜向前移动两格时可以越子。
重步兵可以在抵达对方底线时升变为本方的任意其他棋子，包括王。但升变为王只能在自己只剩一个王的情况下进行。

### 将军 | General (G)

![General](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/SpartanGeneral.png)
 
将军可以直走任意格数，或斜走一格。这个走法和将棋的龙王一样。

### 统战官 | Warlord (W)

![Warlord](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/SpartanWarlord.png)
 
统战官可以斜走任意格数，或者像马一样行动。这与大主教(ArchBishop)是一样的。

### 队长 | Captain (C)

![Captain](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/SpartanCaptain.png)
 
队长可以直走1到2格，走法和吃法相同，而且直走2格时可以越子。

### 队副 | Lieutenant (L)

![Lieutenant](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/SpartanLieutenant.png)
 
队副可以斜走1到2格，走法和吃法相同，斜走2格时可以越子。还可以左右走1格，但不能吃子。

## 棋子价值 | Piece valuation

根据作者的文章，棋子价值估计如下：
统战官：8
将军：7
王（在双王的情况下）：5
队副：3
队长：3
重步兵：1

## 策略 | Strategy
针对双方的棋组，下面有一些各自的策略建议：

**斯巴达棋组**
* 封闭开局 - 因为斯巴达棋组的很多棋子都有越子走吃的能力，最好是避免兑换。
* 活用重步兵 - 重步兵比国际象棋的兵要灵活，使用它们去尽快抢占要点。
* 叠兵 - 前后相邻的重步兵是非常强的兵阵，建立多个叠兵阵型能起到有效的防御作用。
* 耐心开局 - 斯巴达棋组的单位整体偏慢，所以在出动子力时要有一定的耐心，慢慢调动子力。
* 重视王的进攻作用 - 当双王都在时，王也是不可忽视的战力，能够在进攻中发挥很大作用。尝试去利用王推进和辅助攻击。
* 活用双王的将军限制 - 您的双王在场的时间越长，您的进攻就越不受限制，因为您可以较少地照顾己方王的安全。
* 快速胜利 - 如果您的将军和统战官位置得当，您可能会利用它们在对局早期就实行一个快速且远距离的将杀。

**波斯方棋组**
* 开放式开局 - 国际象棋方拥有较多的远距离棋子，尽量多去进行兑换减少盘面棋子，让远距离棋子发挥威力。
* 消耗战 - 因为斯巴达有两个王，白棋很难快速取胜。和对方打消耗，逐渐积累优势再击垮斯巴达军队。
* 机动 - 寻找开放线，开放线能够使远距离棋子发挥很大作用。
* 击破重步兵 - 重步兵怕斜线攻击，尤其是左右的斜前方都有敌人的时候。
* 擒贼先擒王 - 瞄准对方的一个王进攻。用轻子去换掉对方的一个王，消除对方的双王优势。
* 反击 - 无论斯巴达方如何推进，您一定要寻求反击的机会，争取有利的兑换。寻找开放的侧翼并将车和后调动到那里。
