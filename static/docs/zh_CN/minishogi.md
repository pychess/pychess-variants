# ![Minishogi](https://github.com/pychess/pychess-variants/blob/master/static/icons/minishogi.svg) 迷你将棋|Mini Shogi

![Minishogi](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Minishogi.png)

迷你将棋（或称5五将棋）是缩小版的将棋，使用5x5的棋盘，于1970年由琉球的楠本重信发明。

## 规则

由于此变体基于日本将棋，如果不熟悉将棋规则请先查看[将棋](https://www.pychess.org/variants/shogi)的规则。

初始配置如上，没有桂马与香车，且只有一个步兵。

升变区由三行变更为底线一行。

***

## 将棋的棋子(桂马、香车在此省略)：

### 玉将、王将

![BlackKings](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/BlackKings.png)

![WhiteKings](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/WhiteKings.png)

![KingDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/King.png)

正式场合，先手方使用玉将。后手使用王将。

玉将可以向八个方向行走一格，与国际象棋的王完全相同。将死对方王将者获胜。

### 飞车

![Rooks](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Rooks.png)

![RookDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Rook.png)

飞车，简称飞，移动和象棋的车一样。可以直走任意格数。它是将棋最强的未升变棋子。

其升变后为龙王。

### 龙王

![Dragons](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Dragons.png)

![DragonDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Dragon.png)

龙王，简称龙，由飞车升级而来，走法除了直走任意格数以外，还可以斜走一格。它是场上最强的棋子。

### 角行

![Bishops](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Bishops.png)

![BishopDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Bishop.png)

角行，简称角，可以斜走任意步数，和国际象棋象一样。它是将棋第二强的未升变棋子。

其升变后为龙马。

### 龙马

![Horses](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Horses.png)

![HorseDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Horse.png)

龙马，简称龙，由角行升级而来，除了斜走任意格数以外，还可以直走一格。龙马是场上第二强的棋子。

### 金将

![Golds](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Golds.png)

![GoldDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Gold.png)

金将，简称金，可以向前、左前、右前、左、右或后行走一格，如中文「甲」字。
金将无法升变。

银将、桂马、香车、步兵升变后的走法都等同金将，唯一的区别是称呼不同。**

### 银将

![Silvers](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Silvers.png)

![SilverDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Silver.png)

银将，简称银，可以斜角方向或正前方行走一格。

升变后叫「成银」或简称「全」

### 步兵

![Pawns](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawns.png)

![PawnDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawn.png)

步兵，简称步，走法为直行一格。

升变后叫「と金」(Tokin)或「成步」，简称「と」(To)

## 升变\|成驹

![PSilvers](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PSilvers.png)

![Tokins](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Tokins.png)

棋子在**进入敌阵**、**离开敌阵**、**在敌阵内行动**之后，均可升级。在迷你将棋中，敌阵即对方底线。一般情况，升级是可选的，即可以保持不升级状态等更合适的时机或利用原棋子走法；但若一个棋子不升级就再也不可能移动（步兵抵达对方底线），则必须升级。

大子(飞车、角行)升变后各自成为「龙王」、「龙马」，其余轻子升变后皆为金将。

## 持驹打入\|持ち驹

持驹打入是将棋最特别的规则。棋手可以在轮到自己时，将俘获（吃掉）的敌方棋子放回棋盘成为己方棋子，称为持驹打入，简称打入。当一枚已升级的棋子被吃时，它的升级会被取消，打入时只能用原本的形态打入。

关于打入的详细规则，请查看[将棋页面](https://www.pychess.org/variants/shogi)。

## 其他规则

**长将** - 将棋容许连将但是不能重复同样的手法长照（长将），若双方重复循环同样的方式照将、应照达四次时，则照将方违规，判负。

**千日手** - 双方重复循环同样的着法，使得局面没有进一步变化达四次时，则视为和局。

***

## 策略

由于棋盘较小，飞车与角行相对就不像将棋中那么强。但在它们升变之后，依旧有很大的主宰力。