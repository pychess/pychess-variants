# ![Xiangfu](https://github.com/pychess/pychess-variants/blob/master/static/icons/Xiangfu.svg) 功夫棋 | Xiang Fu

![Xiangfu](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Xiangfu.png)
功夫棋（Xiang Fu）是首届 Pychess 设计大赛的冠军作品，作者为 Eventlesstew。
作者在网球棋（Chennis）的基础上，加入了中国功夫的元素。加入一个“擂台”区域，为双方将帅的行动范围，同时在外围使用远距离棋子配合作战。

## 规则

- 吃掉对方棋子之后收归己方所有，可打入在本方阵地最后两行。
- 棋盘中间的 5×5 区域为擂台，双方的将（帅）只能在该区域内行动。
- 每方有两个将（帅），必须同时被攻击才视为被将军，与斯巴达象棋一样。详细规则见下面走法部分。
- 无子可动和重复局面均为平局，而非落败。


## 棋子

### 将/帅 | Champion/King (K)

![King](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/XiangfuKing.png)

将帅的走法与国际象棋的王相同，为八方 1 格。
**双王规则：**
当一方的两个将（帅）都在场时，不受将军规则的制约，可以送吃，只有一个被将军时也不必应将。
若两个将（帅）同时被将军（Duple-check），则必须应将，使得其中的至少一个脱离被攻击状态。若不能解除，则这一方落败。
故意使己方的两个将（帅）同时被攻击是违规的。
当只有一个将（帅）在场时，则不能送吃，被将军时必须应将，如同国际象棋一样。

### 学徒/徒 | Pupil/Commoner (G)

![Commoner](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/XiangfuCommoner.png)

学徒，简称徒，走法也是八方 1 格。
学徒仅能由吃掉的对方的将（帅）之后转化而来，打入在场上后不视为王。

### 马兵/马 | Horse (N)

![Horse](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/XiangfuHorse.png)

马兵，简称马，走法和象棋的马完全相同。

### 战车/车 | Chariot (R)

![Rook](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/XiangfuRook.png)

战车，简称车，走法和象棋的车完全相同。

### 炮 | Cannon (C)

![Cannon](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/XiangfuCannon.png)

炮的走法和象棋的炮完全相同。

### 象兵/象 | Mahout/Elephant rider (M)

![Mahout](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/XiangfuMahout.png)

象兵，简称象，走法为八方走 2 格，不能越子。

### 武僧/僧 | Bishop (B)

![Bishop](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/XiangfuBishop.png)

武僧，简称僧，走法为斜走任意步数，不能越子。与国际象棋主教相同。

### 弩 | Crossbow (W)

![Crossbow](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/XiangfuCrossbow.png)

弩为斜走的炮。它可以斜走任意步数，吃子必须跳过一个棋子。