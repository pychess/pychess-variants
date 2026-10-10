# ![Shogi](https://github.com/pychess/pychess-variants/blob/master/static/icons/shogi.svg) 将棋 | Shogi

![Boards](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Boards.png)

将棋*（しょうぎ，Shogi）*是一种盛行于日本的棋类游戏。最早的将棋从平安时代的平安将棋开始，经历镰仓时代、室町时代发展出不同棋盘大小、不同子力数量的变种。现代的将棋（本将棋）是16世纪中期由小将棋改造而来。在日本，将棋跟围棋并列为两大最受欢迎的棋，而且都设有段位与职业赛头衔。与国际象棋不同的是，将棋拥有独特的“持驹打入”规则。

## 为何要学将棋?

如果您喜欢国际象棋，将棋是您非常值得一试的棋种。虽然将棋的棋子移动较慢，但是它的战场节奏更加多变复杂，是一种全新的游戏体验。在复杂度上，将棋和围棋相当，但这并不意味着将棋很难。熟悉将棋也有助于您提升其他棋种的对局思路。

关于更多的信息，[请点击这里(英文)](https://chessbase.in/news/peter-heine-nielsen-on-shogi)

## 规则

将棋同样属于擒王棋，所以基本的规则与其他擒王棋类似。

将棋的棋盘为9×9的棋盘，玩家轮流行动，先将死对方王（玉将/王将）的一方获胜。在系统中，先手方称为Black，后手方称为White，尽管棋子颜色并不展示它的所属方——将棋棋子通过棋子的朝向区分所属。系统中棋子的颜色是为了区分容易混淆的棋子（金与银）和重子（角与飞）。

将棋的特有规则：**持驹打入**。在将棋中，当你吃掉对方棋子之后，对方的棋子会置入您的**驹台**（棋盘外的区域），可以在轮到自己走棋时，放回在棋盘上作为自己的子力。您可能发现，双狂象棋(Crazyhouse)也采用了类似的规则。

在棋子升变方面，将棋拥有“本阵”与“敌阵”的概念，即靠近本方的3行离本方最远的3行。棋子在**进入敌阵**、**离开敌阵**、**在敌阵内行动**之后，均可升级（称为成，成る，naru，对应选择不升变则为不成，成らず，narazu）。除王和金将以外，所有棋子均可升级。现实中将棋子翻到背面表示升级。若吃掉对方的升级棋子，则必须以原形态打入。

## 棋子

本文将展示本站可用的四种棋子的造型：符号棋子（2种）、双字驹、单字驹。在实际的将棋中，使用较多的是双字棋驹。正面为黑色，反面为红色。在记谱上，多使用简称的单字驹

将棋共有八种棋子（包含升级棋则有十四种）。大驹——飞车和角行——升级增加王将的走法，而小驹的升级均为金将（尽管名字不同）。

下面简单介绍一下每个棋子及其走法。

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

### 桂马

![Knights](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Knights.png)

![KnightDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Knight.png)

桂马，简称桂，如图所示，和国际象棋的马类似，但是桂马只能跳到向前的两格。
桂马的跳跃可以越子。

升变后叫「成桂」或简称「圭」

![Lances](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Lances.png)

![LanceeDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Lance.png)

香车，简称香向前走任意步数，不能跨过别的棋子。

升变后叫「成香」或简称「杏」

### 步兵

![Pawns](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawns.png)

![PawnDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawn.png)

步兵，简称步，走法为直行一格。

升变后叫「と金」(Tokin)或「成步」，简称「と」(To)

## 升变\|成驹

![PSilvers](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PSilvers.png)

![PKnights](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PKnights.png)

![PLances](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PLances.png)

![Tokins](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Tokins.png)

上述四个图片分别为银、桂、香、步的升变造型。它们的升变通常没有双字驹的造型，统一采用单字简称。它们的单字简称均为“金”以表示走法与金将相同，采用不同字体区分不同的棋子。

升级条件如上文所说，棋子在**进入敌阵**、**离开敌阵**、**在敌阵内行动**之后，均可升级。一般情况，升级是可选的，即可以保持不升级状态等更合适的时机或利用原棋子走法；但若一个棋子不升级就再也不可能移动（桂马到达对方底线或二线，步兵、香车抵达对方底线），则必须升级。

大子(飞车、角行)升变后各自成为「龙王」、「龙马」，其余轻子升变后皆为金将。

|     | 升变前   | 升变后   |
| --- | ----- | ----- |
| 大子  | 飞车、角行 | 龙王、龙马 |
| 轻子  | 其他棋子  | 金将    |

## 持驹打入\|持ち驹

*注：不要将此术语误写作“持驹打人”。*

持驹打入是将棋最特别的规则。棋手可以在轮到自己时，将俘获（吃掉）的敌方棋子放回棋盘成为己方棋子，称为持驹打入，简称打入。当一枚已升级的棋子被吃时，它的升级会被取消，打入时只能用原本的形态打入。

打入有以下限制：

* 刚打入的棋子即使落在敌阵亦不能马上升级，**一定要在移动一步之后才可升级**。
* 不能把棋子打入在一些不可能再移动的位置。例如步兵、香车都不能落在敌阵的底线；桂马不能落在敌阵的底线及二线。

对步兵的打入有一些额外限制:

1. **同筋二步**: 同一列上不能存在两个以上的步兵。若某列已有无方未升变步兵，则步兵不能在该列打入。 (若原本的兵已升变，则不算入此限制)。 「同筋二步」在日本的将棋职业赛中是为最常见的犯规行为。自1977年迄今，在日本的将棋职业赛中已有44次「同筋二步」的记录。

2. **打步诘**: 指用**打入步兵**的方式使对方王将无法脱逃而**被将死**，若触犯则直接判负。打步诘必须要「打」、「步」、「诘」三个条件同时成立。以下的三种情形均为允许的：
- 走步诘：移动步兵，将死对方王将

- 打其他棋子诘：打入非步兵的棋子，将死对方王将

- 打步将：打入步兵，将军对方王将但没将死

## 其他规则

**长将** - 将棋容许连将但是不能重复同样的手法长照（长将），若双方重复循环同样的方式照将、应照达四次时，则照将方违规，判负。

**千日手** - 双方重复循环同样的着法，使得局面没有进一步变化达四次时，则视为和局。

***

## 记谱

我们使用西式记谱(类似西洋棋)的记谱法。关于将棋特有的记谱法，请自行搜索相关内容。

### 坐标

以阿拉伯数字表示行，英文字母表示列。原点落在王将方(后手)。然而，由于大部份的棋盘表示时是将玉将(先手)放在底部，因此原点会在最右上方。例如，王将是落在 5a

有时不管行列都由阿拉伯数字表示，比方5e有时也记作55(第五列, 第五行)。

### 棋子

K = 王将

G = 金将

S = 银将

N = 桂马

L = 香车

R = 飞车

B = 角行

P = 步兵

+R or D = 龙王

+B or H = 龙马

+S, +N, +L, +P 其余升变的轻子

### 标记

* 打入会加上 \*符号, 所以打入在5e的兵会记 P*5e
* 升变会在其后加上+。例如一个在c1升变的兵会变 P1c+
* 如果你选择不升变，则在后面加上「=」
* 将军和将死并没有特别标记

## 学习将棋的资源

[Hidetchi 的 YouTube 频道](https://www.youtube.com/playlist?list=PL587865CAE59EB84A) 非常适合初学都与中等程度者。

***

## 策略

### 子力价值

与象棋不同，将棋中没有标准的子力价值。重要的是要记住，价值并没有那么重要，因为失去棋子不是永久性的，而位置更为重要。也就是说，有一个基本的子力价值体系，但职业棋手们也制定了更具体的价值量表:谷川式和佐藤式。如下所示:

| 棋子       | 基本价值 | 谷川  | 佐藤  |
| -------- | ---- | --- | --- |
| 步兵(P)    | 1    | 1   | 1   |
| 香车(L)    | 3    | 5   | 6   |
| 桂马(N)    | 3    | 6   | 6   |
| 银将(S)    | 5    | 8   | 10  |
| 金将(G)    | 5    | 9   | 11  |
| 角行(B)    | 7    | 13  | 17  |
| 飞车(R)    | 8    | 15  | 19  |
| *龙马(H)*  |      | 15  | 20  |
| *龙王(D)*  |      | 17  | 22  |
| *成步(+P)* |      | 12  |     |
| *成香(+L)* |      | 10  |     |
| *成桂(+N)* |      | 10  |     |
| *成银(+S)* |      | 9   |     |

### 开局原则

一般来说，有两种类型的开局方式：**居飞车**和**振飞车**。在居飞车中飞车不会移动，因此主要攻击棋盘的右侧。在振飞车中，飞车移动到左侧（通常是第 2 到第 5 行），将进攻棋盘的另一翼。

开局（称为 *joseki*）主要分成这两种，两者差异极大。

### 围玉

围玉是将棋开局最重要的策略，指将王将动到角落并以其他棋子包围以保护不受攻击。通常需要多步才能完成。围玉的优劣通常以“远”（让王远离交战区）、“坚”（围玉形状难以被对方击破）、“广”（给王预留的逃生路线较为广）来评判。好的玩家需要了解各种围玉的优缺点与变型。

围玉的位置受开局为居飞车或振飞车影响。在居飞车开局中，王将在左围玉。在振飞车中则在右。以下是三种最常见的围玉:

### 矢仓

![Yagura](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Yagura.png)

矢仓围是将棋中采用于相居飞车和相振飞车的围玉。通常简称为矢仓，与美浓、穴熊并列为最具代表性的围玉。居飞车双方围出矢仓后战斗的战型被称为相矢仓，也常被直接简称为矢仓。

此围玉上方很强，但相反的，因为守护到78金将的棋子只有玉将1枚而已，面对横向而来的攻击则效果并不是很好。然而金银3枚均有集中防守到68的位置，因此也不能说面对横向而来的攻击防守薄弱。反而是在第一行，因为没有金银防守而显得有点薄弱，例如有利用桂香飞角一口气攻破的雀刺战法。

在矢仓围玉的时候记住王将总是斜向移动以节省步数，且有许多种矢仓的变体，以应对对手不同的攻击。以下是标准的24步矢仓围:

1. ☗P-7f
2. ☖P-8d
3. ☗S-6h
4. ☖P-3d
5. ☗P-6f
6. ☖S-6b
7. ☗P-5f
8. ☖P-5d
9. ☗S-4h
10. ☖S-4b
11. ☗G4i-5h
12. ☖G-3b
13. ☗G-7h
14. ☖K-4a
15. ☗K-6i
16. ☖P-7d
17. ☗G5h-6g
18. ☖G-5b 
19. ☗S-7g
20. ☖S-3c
21. ☗B-7i
22. ☖B-3a
23. ☗P-3f
24. ☖P-4d

### 美浓

![Mino Castle](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Mino.png)

美浓通常用于振飞车，用来对付居飞车的围玉，王将来到飞车的初始位置，金将走上&右，再上银将，形成“金金银” 。此围玉左侧防御很强，但对上方防御较弱。

以下是一个美浓应对四间飞车的范例:

* P76
* B77 (保护 86/8f 格子) 
* P66 (防止换角)
* R68 (四间飞车)
* S78 
* K48 -> K38 -> K28
* S38 (上银)
* G58 (上金)
* P16 (给王将逃跑空间)
* P46

自此之后可以开始换子，包括飞车，以发起进攻。

### 穴熊

![Anaguma](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Anaguma.png)

十分著名的围玉方式，曾在棋界流行数十年。它的防守非常强大，只不过要花费许多步数完成。

**优点**

金银的连结密集因而非常坚固，再加上玉将在端离战场十分遥远，形成了「绝对不会被王手（别称Z）」的形，对手也因此不得不避免在攻略穴熊的时候牺牲大量棋子。基于这些优点，穴熊方得以采取大胆舍飞车和角行等大子的作战，被称为「只有穴熊才能做到的攻击」。

**缺点**

首先，围玉所需的手数非常多，对手常常在完成之前就挑起战事。再来，围玉完成之后因为棋子集中在盘上一侧，自阵有许多空隙容易被对手打入角行。虽然横向的守备力很高，对上方或端攻较弱，在终盘还因为玉将躲在棋盘的角落，在被攻击的时候无处可逃。最后，因为自阵空隙太多容易被对手入玉，这种时候就已完全没有胜算。这种虽然围玉没有被破坏却输棋的状况被称为「姿烧穴熊(烤全熊)」。

此外，居飞车穴熊则多有遭对手角道直射的疑虑。许多居飞车穴熊的攻略法都包含角道的利用。

### 相挂

双方都使用居飞车并进车前兵进攻。需要注意的事，你必需要在对方兵进到5行之后以【78金】保护角行。

## 让子

为了让相对较弱的棋手也有获胜的机会，较强的棋手有时会让子（日文称为驹落）。在让子的情况下，让子方（即上手）必须在开局时永久除去自己一部分的棋子（即不能以任何方式将之放上棋盘）。不过，在比赛上，让子并不会因为兵力上的差异而为相对较弱的棋手造成明显的优势。下面列出现行的让子制度：

| 棋力段位差 | 名称     | 让子                |
| ----- | ------ | ----------------- |
| 0     | 平手：摇驹  | 摇驹猜先              |
| 1     | 平手：下位先 | 让先                |
| 2     | 左香落    | 除去左旁香车            |
| 3     | 角落     | 除去角行              |
| 4     | 飞落     | 除去飞车              |
| 5     | 飞香落    | 除去飞车与左旁香车         |
| 6~7   | 二枚落    | 除去飞车与角行           |
| 8~9   | 四枚落    | 除去飞车、角行与两枚香车      |
| ≥10   | 六枚落    | 除去飞车、角行、两枚香车与两枚桂马 |
上表“摇驹猜先”通常做法为取5枚步兵掷出，若“步”朝上的较多则摇驹者先手，反之后手

其余的让子、如**八枚落**（六枚落的基础上再除去两枚银将）、**十枚落**（在六枚落的基础上再除去金银）、**步三兵**（仅王在场上，驹台保留三枚步兵，除去其余所有棋子）、**裸玉**（除去王以外所有棋子），一般用于教学指导棋时使用。

<iframe width="560" height="315" src="https://www.youtube.com/embed/YH63AlxpXkg" frameborder="0" allowfullscreen></iframe>