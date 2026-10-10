# ![Chennis](https://github.com/pychess/pychess-variants/blob/master/static/icons/Chennis.svg) 网球棋

![Chennis](https://github.com/pychess/pychess-variants/blob/master/static/images/ChennisGuide/Chennis.png)

## 背景

网球棋（Chennis）是 Couch Tomato 于 2021 年推出的棋类游戏，最初的设想是制作一个京都将棋的变种。由于京都将棋已经被完全解决，网球棋的目的是创作一个更为平衡的游戏，同时引入不同的棋子使得国际象棋玩家更容易上手。为尽量减少将棋类棋子的出现，就需要更多的远距离棋子和更大的棋盘。然后，为了控制将杀的难度，给王增加了活动范围的限制。因为双方王的活动范围像一个网球场，因此定名为网球棋。由于引入了炮、限制了活动范围，某种意义上也可以说网球棋也借鉴了中国象棋，这意味着网球棋结合了许多流行棋类中的元素。在平衡方面，目前双方的胜率为先手（白）胜率约为 60%。

## 简介与基本规则

游戏分黑白双方，白棋先走。所有的棋子（王除外）都有两种形态，每次行动之后都必须变换成另一种形态。在游戏界面上，即将变换成的棋子会以红色/蓝色提示。

![Piece Swaps](https://github.com/pychess/pychess-variants/blob/master/static/images/ChennisGuide/Swap.png)

当你吃掉对方棋子时，那个被吃的棋子会返回你的手中，类似将棋的驹台。这些棋子可供打入，与将棋的打入相同。但是，你可以在打入时**自由选择以哪一形态进入棋盘**。例如：对于“车-兵”棋子，您可以任选它是当作车打入，还是当作兵打入。

### 棋盘

网球棋的棋盘为7x7，如下图：

![Chak](https://github.com/pychess/pychess-variants/blob/master/static/images/ChennisGuide/ChennisCourt.png)

所有棋子（王除外）可以在棋盘任意位置行动。棋盘分为四个区域，和双方王的行动范围有关：

**白方半场|White's Court**: 仅白王可在此区域行动。
**黑方半场|Black's Court**: 仅黑王可在此区域行动。
**球网区|Net**, 棋盘中间的 5 格区域。这是双方王的公共区域，双方的王均可在此区域行动。
**边线|Sidelines**, 棋盘两边的两列，双方的王均**不可**在此区域行动。

### 游戏胜败目标

获胜有以下两种方式：

**将杀 | Checkmate** - 攻击对方国王，且对方无法解除将军。
**困毙 | Stalemate** - 使对方无子可动，即使王未被攻击（与国际象棋的逼和不同）。

## 棋子

王和国际象棋的王完全相同，八方行动一格。王只能在自己的半场和球网区移动。注意：您可以在己方半场用王攻击对方位于球网区的王。

其余的棋子每方有4枚。它们分别是：

车-兵、象-卒、马-警卫、炮-士。

其中，车、马、象、兵的走法与国际象棋完全相同，但兵取消了向前两格的走法。

每个棋子的形态大致可以分为直走形态和斜走形态，一个棋子行动之后会切换成另一种形态。
下面是另外四个棋子的走法。

### 卒 | Soldier (S)

![Soldier](https://github.com/pychess/pychess-variants/blob/master/static/images/ChennisGuide/Soldier.png)

卒可以向前、左、右行动一格。它是象的对应形态。

### 警卫 | Mayor (M)

![Mayor](https://github.com/pychess/pychess-variants/blob/master/static/images/ChennisGuide/Mayor.png)

警卫走法和王一样，即八方行动一格。它是马的对应形态。

### 士 | Ferz (F)

![Ferz](https://github.com/pychess/pychess-variants/blob/master/static/images/ChennisGuide/Ferz.png)

士可以斜走一格。它是炮的对应形态。

### 炮 | Cannon (C)

![Cannon Move](https://github.com/pychess/pychess-variants/blob/master/static/images/ChennisGuide/CannonMove.png)

![Cannon Attack](https://github.com/pychess/pychess-variants/blob/master/static/images/ChennisGuide/CannonAttack.png)

炮的走法和中国象棋相同，即直行任意距离，隔一子吃子。它是士的对应形态。

## 棋子价值

准确的棋子价值难以计算。在这类具有打入设定的棋中，具体的局面往往比死板的棋子价值更为重要。在四个棋子中，通常认为马-警卫的组合作用更大，因为两种形态都很灵活。

## 策略

游戏推出时间较短，策略尚在研究中。

对于新玩家的一条建议：
**务必记住王的行动范围！**
**务必记住王的行动范围！**
**务必记住王的行动范围！**
*（重要的事情说三遍）*
您的王只能在己方半场和球网区行动，**不能走到边线**。这意味着边线的棋子可以近距离攻击王而不会受到王的反击。
