# ![Xiangqi](https://github.com/pychess/pychess-variants/blob/master/static/icons/xiangqi.svg) 象棋 | Xiangqi

![Boards](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Boards.png)

象棋是流行于中国大陆、中国香港、中国台湾、马来西亚、新加坡、越南、琉球地区的传统2人对弈棋类游戏。曾经有一段时间，中文为了区分，把象棋叫做中国象棋，Chess 称为国际象棋，同时在英语中象棋使用 Chinese Chess 的译名；在 2009 年，中国国家体育总局正式使用“象棋”的称呼，而英语则使用新的译名 Xiangqi 。在中国港澳台地区，通常将 Chess 翻译为“西洋棋”。

关于象棋的历史，曾经有根据《楚辞》“菎蔽象棋，有六簙些”，认为象棋从春秋战国时期的「六博」演绎而来的说法，但这一说法因为汉语字词存在古今异义，且象棋旧称作“象戏”而存疑。随着越来越多的深入研究，现认为象棋是中国本土逐渐发展定型的游戏。Sam Sloan阅读了大量不同语言——包括汉语——的文献，[这里是他的文章](http://www.anusha.com/origin.htm)。

目前出土的最早的象棋原型是唐朝的宝应象棋，与恰图兰卡（国际象棋的原型）颇为相似。可以确定的是，现代象棋的基本规则，早在宋代就已经定型——当时的著名词人李清照、著名政治家司马光都曾经研究过各种各样的变体。

象棋最初没有炮，炮是唐代宰相牛僧孺所加入。

根据棋类研究者 Murray H.J.R. 的文献，象棋的雏形可能从南北朝时期就已经有了。目前对象棋的最早记述见于唐朝的《玄怪录》。

## 一、为何要玩象棋

中国象棋比国际象棋虽需时较长，步数较多，但亦有其精彩之处。中国象棋的开放线多，开局和残局节奏更快。比起更注重战略的国际象棋，象棋更考验棋手计算能力的战术性。
它的局面丰富多样，行棋轻快流畅，战术凌厉，不像国际象棋常有子力拥塞的情况发生。和国际象棋注重发展空间不同，象棋更强调阻挡与抢占要道。

学习象棋可以转换您的棋类思维，加上【炮】这个复杂而特别的棋子带来许多其他棋所没有的战术，绝对可以增进您的棋感和敏锐度。

## 二、规则

与国际象棋最大的不同点是象棋所有的棋子都落在棋盘的交叉点上，且在纵横的线上移动。开局由红先行，黑后，目的是将死对方的帅/将。

在象棋中，被困毙(stalemated 无子可动)的一方落败，而不是逼和。

长将和(perpetual checks)在象棋中也不成立。在本站，只要有一方循环走出三次一样的步法，该方就直接告负。

## 三、棋盘

象棋的棋盘由9条纵线和10条横线相交而成。棋子放在各条线的相交点上，并在线上移动。

棋盘中间的一行没有画上纵线，称为“河界”。现代的象棋通常借用楚汉争霸的历史事件，标有“楚河汉界”字样作为装饰。

现行的中式记录方法是：9条纵线，红方从右到左用汉字“一”至“九”表示，黑方在自己的那一面从右到左用数字"1"至"9"表示。也就是说，红方最右边的纵线为一线，对应黑方的第9线，以此类推。

棋盘上，划有斜交叉线而构成米字形方格的区域，双方各有一块，称为“九宫”，是将（帅）和士（仕）活动的区域。

## 四、棋子

### 将、帅

![Kings](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Kings.png)

只可在己方的九宫内朝前后左右走一格。

将、帅在同一路且两个棋子之前无任何棋子时，是不允许的。这种行为称为“照面”或“将帅对脸”。

被将死或一方无子可动时，该方告负。

![King and advisor movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/KingAdvisorDiagram.png)

### 士、仕

![Advisors](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Advisors.png)

只可在己方的九宫内斜走一格。
行动力较低的棋子，用作将（帅）的内防御之用。

### 象、相

 ![Elephants](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Elephants.png)

 ![Elephant movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/ElephantDiagram.png)

象行田：象可以斜走两格，如同一个“田”字。

塞象眼（挤象眼）：当田字的中心有棋子，就不能走。

象也是防御棋子，用作将（帅）的外防御之用。

### 马、傌

 ![Horses](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Horses.png)

 ![Horse movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/HorseDiagram.png)

马行日：先朝一个方向直走一格，再顺着该方向斜走一格，如同“日”字。

蹩马腿（卡马脚）：若第一步（直走一格）的位置有棋子阻挡，就不能往那个方向走。如图，黑马不能向右跳。斜向相邻的棋子不会蹩马腿。新手请特别注意“蹩马腿”的位置，会存在自己的马被蹩而对方的马没有被蹩的情况。

最多能走八个方位，有八面虎之称，近距离杀伤力最强，同时又能凭着九弯十八拐的行进路线掩藏杀机，厉害无比。
随着战局的进行，或是棋手实力越高，更易发挥其威力。

### 车、俥

 ![Chariots](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Chariots.png)

 ![Chariot movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/ChariotDiagram.png)

车可以直走任意距离。

车为远距离杀伤力的主力，无论何时都是第2关键的子。
有“三步不出车，棋已输半盘”的棋谚。残局有车在手，基本上不成问题；如果只有自己有车，常可稳操胜券。

### 砲、炮

![Cannons](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Cannons.png)

![Cannon movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/CannonDiagram.png)

炮的走法与车相同，只是不能按车的走法吃子。

吃子时必须跳过一个棋子（该子称为炮架或炮台）。

远距离杀伤力第二强，进攻时常与车和马配合使用。
开局因为棋子（炮架）众多，极为凶猛；残局时因炮架难以取得，有时甚至需要借助对方的防御棋子。若能换到一炮（甚至一马）会相当划算。

### 卒、兵

![Pawns](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Pawns.png)

![Pawn movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/PawnDiagram.png)

过河前每次只可向前走一格；过河后可左右或向前走一格。

兵不能后退。

与国际象棋不同，即使走到底线也不能升变成其他棋子。但兵过河就能横移，加强能力。
越到残局威力越强，有时一兵（卒）可抵一马或一炮，甚至一车。

## 五、胜负:

对一般棋局来说，只要一方被将死或困毙，又或者自动认输，另一方即可得胜。

双方在连续50步都没有吃子时，直接判和。

长打（即长捉、长将、长杀）的一方需改变行动，否则判负。

## 六、记谱

在Pychess中，棋子的符号如下表：

| 棋子  | 英文代号        |
| --- | ----------- |
| 帅 将 | King（K）     |
| 仕 士 | Advisor（A）  |
| 相 象 | Elephant(Ｅ) |
| 傌 马 | Horse（H）    |
| 俥 车 | Rook（R）     |
| 炮 包 | Cannon（C）   |
| 兵 卒 | Pawn（P）     |

关于中式记谱法，请[查看这里](https://zhuanlan.zhihu.com/p/67939221?ivk_sa=1024320u)。

PyChess在棋谱中使用传统西式记谱法。本文在此作一些说明。

**格式**: [棋子][原棋子所在行][前进或后退][移动后所在行]

直接将中式记法转成英文字母和数字。各种棋子以英文代号代替。 「平」用「=」代替；「进」、「退」和「前」、「后」分别用「+」、「-」取代。如果同一行有两只相同棋子，则前面的以+表示，后面的以-表示，其后不加棋子所在行。

例如:

* 马2进3（H2+3）：黑方在第2条直线上的马向前再转左，走到第3条直线上

* 俥一进一（R1+1）：红方在第一条直线上（即最右方）的俥向前一步

* 后炮平4（C-=4 / C-.4）：黑方在某条直线上有两只黑炮，将较近黑方自己的一只移动到第4条直线

## 七、策略

### 子力价值

| 棋子  | 分数       |
| --- | -------- |
| 帅 将 | 无限       |
| 仕 士 | 2        |
| 相 象 | 2.5      |
| 傌 马 | 4        |
| 俥 车 | 9        |
| 炮 包 | 4.5      |
| 兵 卒 | 1，过河后变 2 |

### 基本行棋原则

* 由于开局时子尚多，容易成为炮的炮架，所以炮在开局拥有相当强大的攻击性。而到残局时，由于子力变少炮容易成为孤炮，失去其战斗价值。反观马在开局时因为子力密集，易卡马脚，因此成为需被保护的弱子，待残局子力减少，马的威力才真正发挥，能在近距离控制多个点位。
* 用车控制住肋道或二、八路，并卡住相眼、马脚，或是占住河界（巡河车）。
* 撑起士、相以完善防守，限制对方子力在自方区域的活动能力。
* 不要让对方架住空头炮(炮、将之间没有棋子)。如此炮会将那条线完全封死。
* 开局让子力生根(互相防守)，不要轻易让马脱根。
* 象与国际象棋的象（主教）不同，它是防御棋子。尤其可以减少对方炮的威胁。
* 注意闪将和闪击更为常见（尽管象棋中有更多的称呼去给这些战术取名），双将也是。

### 开局原则

对于业余棋手来说，有70%红方开局走中炮，即「炮八平五」直接瞄准中路，目标明确且方便右翼子力出动，行棋较为套路，不易出错。

![Cannon opening](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/CannonOpening.png)

了解中炮局是对新手不错的选择。以下将简介四种黑方可以做出的应对，称为四大开局:

**1. 屏风马**

![Screen horses](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Screen_Horses.png)

屏风马是指在同一个棋局中，一位象棋棋手同时走马二进三和马八进七。

屏风马是一个防守稳健的布局，可让士象守护中宫、双马保护中兵。由于能有效果保护中兵，对将的保护很有利。

双马前进后 (即，马二进三和马八进七)，棋手一般会选择卒七进一或卒三进一，这样可让单马、甚至双马更为灵活，可立即出击。

可以有效果对抗对方红棋的当头炮开局，也可抗衡红棋比较积极进攻的中炮盘头马。

**2. 反宫马**

将炮动到士角使其更加灵活，可以直接牵制红方左翼上马八进七，往后也可发动肋道的攻势。

反宫马最明显的弱点是总有一边马没有根 (没有另一只棋子保护这只马)。

一旦没有根的反宫马被对方红棋的车压制，或被红炮瞄准攻击的时候，黑棋的防守会变得非常被动，造成难以抽出机会去反击对手。

![Fan Gong Ma](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Fan_Gong_Ma.png)

**3. 顺手炮**

顺炮 (顺手炮) 开局，是对炮局中的中炮局的一个主流开局布局。顺炮局的布局过程是后手方 (黑棋) 跟先手方走的是同一边的中炮开局。

在中国象棋中，能抢先是一个非常关键的赢棋因素。顺炮局这个开局方式其实没有大问题。相对于中炮对各种马局的开局方式，使用顺炮开局的后手方子力调动一般比较快，在一定程度上可跟先手方 (红棋) 拼抢先手。

后手方使用到顺炮开局的情况，意味着在棋局中的双方都属于偏向进攻型的棋手，双方在子力调动上都需要非常快速。先手方多数会走顺车，后手方可走横车，后手方在形势上还是能保持着均势。

**4. 对炮局**

与顺手炮相似，只是改走与对手反向的炮，

**5. 三步虎**

![Three Step Tiger](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Three_Step_Tiger.png)

黑方上马之后快速平边炮亮车，是较激进的走法。

### 其他先手开局

红方除了中炮局外，尚有其他开局，称为缓攻类开局，并不会如中炮对黑方直接造成威胁。

**1. 仙人指路** - 指先手走兵三进一或兵七进一，先开马前兵，意在等待后手方表露意图后再作打算，属缓攻型布局。因为它弹性大，可布成各类阵势，也非常常见。
以兵七进一为例，后手方一般的应着为：

* 炮 8 平 5，称为还中炮，不理会挺兵而径自攻击对方中兵，属于攻击型的应着。
* 炮 2 平 3 ，称为卒底炮，又称一声雷，针对挺起的兵进行攻击，同样属于攻击型的应着。
* 卒 7 进 1 ，演变成对兵局，后手方针锋相对，一样不表示意图，而且同样弹性较大，之后能演变成多种不同类型的布局,同样亦是较稳健的应着。
* 象 3 进 5 ，演变成仙人指路对飞象，是什为稳健的下法。
* 马 8 进 7 ，演变成挺兵对起马

**2. 飞象局** - 飞象护住中路，为高手常用的下法，比起一来一往的激烈对攻，此局较为隐晦含蓄，敛藏杀机，较不入套路之流。

**3. 起马局** - 走马二进三或马八进七，是AI最为推荐，分数最高的开局

红方尚有「士角炮」、「过宫炮」等开局。

<iframe width="560" height="315" src="https://www.youtube.com/embed/5EDG5RP8OZ8" frameborder="0" allowfullscreen></iframe>

<iframe width="560" height="315" src="https://www.youtube.com/embed/boT1qyDA5RA" frameborder="0" allowfullscreen></iframe>