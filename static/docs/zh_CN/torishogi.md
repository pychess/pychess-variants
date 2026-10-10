# ![Tori Shogi](https://github.com/pychess/pychess-variants/blob/master/static/icons/ToriShogi.svg) 禽将棋 | Tori Shogi

|                                                                                                                    |                                                                                                                   |
| ------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| ![International Set](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriIntl.png) | ![Traditional Set](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriKanji.png) |

禽将棋是十八世纪时，将棋九世名人大桥宗英发明的日本将棋变体。在将棋的发展史上，禽将棋拥有独特的历史意义：它是使用“打入”规则——现代将棋中独特的规则——的将棋变种中较为古老的一个。禽将棋，顾名思义，棋子皆以飞禽为名。现流行于欧美。

## 规则

* 禽将棋棋盘为7×7格，接近自己的二行横列为自阵，接近对手的二行横列为敌阵。
* 只有鹰与燕可升级，其余棋子不可升级。与将棋不同，**升级是强制的**。
* 有打入与持驹规则，如同将棋一样。
* 打入的限制如下：①燕等同于步兵，不可打步诘。②同一列上不可有**三个以上**己方的燕，即您可以将燕打入在没有燕或仅有一枚燕的一列。若该列已有两枚燕，则燕不可打入在该列。③不可打入无去向位置（与将棋相同）。
* 将对方的鹏将死或困毙为胜。
* 循环局面出现三次，先开始循环周期的玩家必须改变行动，否则判负。

*计时* - 禽将棋使用和将棋一样的读秒计时制，请参看「[术语](https://www.pychess.org/variants/terminology)」。

## 棋子

棋子造型预设为图案版，以鸟的绘画造型提示其走法。

棋子走法分为三种：单格型、人型、Y型。

*译者注：本文参照多语言wiki，将棋子的英文和日文名（音读名）分别列出，以便多语言对照。*

## 单格型

单格型的棋子一次只能走一格。

### 鹏 | Phoenix

![Phoenix](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Phoenix.png)

鹏（ほう）等同于玉将，八方走一格。若被将死则输掉游戏。

### 燕 | Swallow

![Swallow](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Swallow.png)

燕（えん）可向前走一格。

关于燕的打入，见上文。

升变为**雁**。

### 鹰 | Falcon

![Falcon](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Falcon.png)

鹰（おう）除了不能向后，可向其他七个方向走一格。鹰是非常有用的攻击棋子。这个走法在其他将棋变种中通常称为“醉象”。

升变为**雕**。

### 鹤 | Crane

![Crane](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Crane.png)

鹤（かく）可斜走一格，或向前、向后一格。这个走法在将棋变体中通常称为“猛豹”。

## 人型

![Upside-down Y pieces](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/UpsidedownYPieces.png)

**人**型棋子的走法通常包含向前和斜向后。包含两种棋子。

### 雉 | Pheasant

![Pheasant](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pheasant.png)

雉（ち）可向前向跳二格（可越子），或向后斜向走一格。

*绿雉，为日本国鸟。棋子造型上的红点除了表示越子行动以外，也沿用了日本国旗的图案。*

### 鹑 | Quail

|                                                                                                             |                                                                                                               |
| ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| ![LeftQuail](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/LeftQuail.png) | ![RightQuail](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/RightQuail.png) |

鹑（じゅん）是较为特殊的棋子。两枚鹑依据配置于左右两侧而走法不同，棋上会标明左或右字。

左鹑可以向前或右后方走任意格数，或向左后方斜走一格。
右鹑可以向前或左后方走任意格数，或向右后方斜走一格。

在本站游玩时，请注意鹑爪子的朝向为可走任意距离的方向。

## **Y**型

Y型棋子均由其他棋子升级而来。它们的主要行动方向为斜前和向后两个方向。

### 雁与雕

![Promoted pieces](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PromotedPieces.png)

### 雁 | Goose

![Goose](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Goose.png)

*（译者注：原版棋子为雁，英文为消歧义改为Goose）*

雁（がん）为燕的升变，可向斜前方、后方跳两格。由于步伐太大，它所能到达的位置很少。

### 雕 | Eagle

![Eagle](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Eagle.png)

雕（しゅう）为鹰的升变。除保留原本走法外，还可以向斜前与后方自由行走，或向斜后方走最多两格。

这是最强的棋子。

## 记谱

禽将棋使用类似将棋的记谱法。在Pychess中，使用较通用的棋子缩写。

### 座标

原点在白方(后手方)的最右方，也就是棋盘的左上角，先记行再记列，例如白方鹏在4-1。

### 棋子缩写

| 棋子  | 英文  | Pychess缩写 |
| --- | --- | --------- |
| 鹏   | Ph  | K         |
| 燕   | Sw  | S         |
| 鹰   | Fa  | F         |
| 鹤   | Cr  | C         |
| 雉   | Ph  | P         |
| 左鹑  | LQ  | L         |
| 右鹑  | RQ  | R         |
| *雁* | +Sw | +S        |
| *雕* | +Fa | +F        |

### 记号

* 打入记作 \*。例如将燕打在3-3记作"S\*33"
* 升变会在后方加上「+」。如燕在 1-1 升变记作 S11+.
* 将和将死不特别标记。

## 策略

### 子力值值

下列是禽将棋软件所使用的子力价值([看这里](https://happyclam.github.io/project/2019-01-03/torishogiapp))。

| 棋子  | 价值  |
| --- | --- |
| 燕   | 1   |
| 雉   | 3   |
| 鹤   | 6   |
| 鹑   | 7   |
| 鹰   | 7   |
| *雁* | 2   |
| *雕* | 16  |

除燕外，其他子持有在手中时价值会略微下降。

上述数值为软件作者所使用的数值，可能存在一些误差。笔者认为，在走法上，鹤比鹑价值要高一些，因鹑类似于香车，不能轻易移动。

### 开局

基本上有四个合理的开局动作:

1+2：吃掉对方的一只燕

3+4：斜走鹤到你的一只雉前面

若直接将鹤往前一步，对方可以将燕打入在雉前，而你无法防守。

![弱点](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriWeakSpots.png)

上图这些点（雉前）是弱点，请记住这些点并利用鹏和鹰加强防守，这样鹤就不必一直守住这些点！

过于推进鹑不是很有利（除非你想围玉）；进燕让对方吃，或过度移动鹏也不好。

### 燕

燕子可以说是将棋的步兵，但也大不相同。可打入两枚燕子到同行完全改变了策略。因此，燕子实际上是游戏的灵魂，知道如何运用它们是学习禽将棋的关键部分之一。

以下是有关燕子的战术:

* **双燕** (两只燕前后相邻)非常强。因为这可以用最少的棋子锁住一条要道。缺点是双燕不能轻易移动，也不能再打入额外的燕在这一列。

* 由于燕往往会以令人眼花缭乱的速度在场上交换，**几乎可以将它们视为筹码**。手中拥有很多持子燕会让你的攻击有很大的灵活性。燕常处在棋子的前线，如果你有鹤或鹰可以生根的话，可以打入燕来推进你的前线。

* 使用燕子深入敌阵攻击时请小心，如果进入对方下二线，**它会强制升变成雁**！在三线燕的攻击一般会借助双燕形状实行打击，如下图。![别做这种傻事!](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriGooseMistake.png)

### 边路攻击

边路是发动攻击的好位置。如上所述，你可以牺牲一只燕子来推进自己的燕子，以夺取敌方的鹑(将燕打在鹑前方)。下面是一个典型的边路攻击时，一个边列的变化图(由左至右)：

![Edge Sequence!](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriEdgeSequence.png)

若鹑无处可去，它只能选择换子: 把燕吃掉，再被对方的鹑吃。

![Edge Sequence!](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriFailedEdgeAttack.png)

但这只有在鹑无法移动的情况下成立，如果鹑斜后方开放，那它还是可以撤退。

因此这最好用来对付对方开局雉前有棋子的情况（通常是鹤），因为刚好会挡住鹑。

### 残局

残局是最重要的部分。如果您下出完美的开局和中局，但如果你无法将死对方，那么对手可以将你的失误化为反转的机会！残局的目标是俘虏足够的棋子来将对手的鹏将死。你甚至不需要子力优势，只需正确的运子即可。由于将死的方式有很多，因此无法在说明中涵盖不同的情况。不过，有一些重要的提示:

* **鹤和鹰**是将军常用的子。
* **雁**是非常弱的棋子，但常用来支援将杀，因为它是少数可以向前斜向攻击的棋子之一。可以用它在远距离为鹤、雕生根，以将死对方鹏。
* **鹰**很容易将对方将死。不要将它们打在鹏旁边将军（这样很容易跑掉），而是将其打在*可以*下一回合将到鹏的位置旁边。这样就可以升变为雕，从而拥有更强大的子力。更好的是打入鹰的同时威胁到另一子，形成捉双。
* **雉和鹑**也有向后斜向攻击，这对于打破鹏的防御很重要。再者，鹑有无限的对角线，可以在你攻击时用来保护你自己的鹏。请记住，当你全力将军时会一直换子，若将死不成功，对手可以使用这些新棋子来发动攻击，这是鹑非常有用的地方。
* 不能用燕子直接将死对方(将军是可以的)。

## 让子

以下是常见的让子:

* 让一子: 左鹑
* 让一子: 鹰
* 让二子: 鹰和左鹑
* 让三子: 鹰和双鹑

<iframe width="560" height="315" src="https://www.youtube.com/embed/5f9QKK7cm20" frameborder="0" allowfullscreen></iframe>