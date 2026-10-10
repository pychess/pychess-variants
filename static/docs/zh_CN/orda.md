# ![Orda chess](https://github.com/pychess/pychess-variants/blob/master/static/icons/orda.svg) 可汗西征棋 | Orda

![Orda](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Orda.png)

![Legend](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/OrdaLegend.png)

可汗西征棋（Orda Chess）是一种国际象棋变体，于 2020 年由 Couch Tomato 推出。这次创造的是一个非对称的变体——双方使用不同的棋组。最初的灵感来自与 Ralph Betza 提出的棋组制象棋（Chess with different armies），在此基础之上融入了鲜明的主题。新棋组具备浓厚的草原游牧民族风格，大部分棋子都具备马步的走法，参考马背上的民族，命名为 Horde（下称可汗方）。这里 Orda 一词来源于突厥语，字面意思是游牧部落首领的帐篷，后来也代指汗国，在英语中演变成 Horde 即部落。该棋组的敌对方为基本的国际象棋棋组，参考历史上的拔都西征，指代欧洲王室，命名为王国（Kingdom）。经软件分析，游戏本身极其平衡，甚至比国际象棋更平衡，双方的胜率接近五五开。
 
## 基本规则
1.	棋盘布局如上图所示。
2.	双方仅有兵和王是完全相同的（金方的王称为可汗）
3.	王国方（白方）先手。
4.	可汗方（金方）没有王车易位。
5.	可汗方的兵开始时位于第三行，因此不可挺进两格。王国方的兵可以挺进两格。因为上述限制，王国方不能吃可汗方过路兵（因没有吃过路兵的条件），而可汗方可以吃王国方的过路兵。
6.	双方的兵只可升变为后或怯薛
7.	双方的另一个胜利条件是**触底获胜**——将自己的王安全移动至对方底线时，也获得胜利。
8.	其他规则跟国际象棋一样，包括逼和(无子可动算和棋)和长将和。

## 可汗方的棋子
有四个可汗特有的新棋子：枪骑兵2枚，弓骑兵2枚，怯薛2枚，穹庐1枚。怯薛最强（王+马），而穹庐虽然替代了后，但是属于弱子。 
可汗方的王称为可汗(Khan)，棋子造型与王不同，但本质的走法和地位与王完全一样，唯一的区别是棋子外形和名称。
枪骑兵和弓骑兵较为特殊，他们的走子和吃子方式不一样（犹如西洋棋的兵一样）。弓骑兵以马的走法移动，以主教的方式吃子;枪骑兵也是以马的走法移动，而以车的走法吃子。怯薛走吃相同，走法是王+马。穹庐则就如日本将棋的银将般移动和吃子。

**可汗** 棋子	| **王国** 棋子	| 走法 | 吃法
-- | -- | -- | --
穹庐 | 后 | 银将 | 银将
弓骑兵 | 象 | 马 | 主教
怯薛 | 马 | 马+王 | 马+王
枪骑兵 | 车 | 马 | 车

下面是每个棋子的细节和图示。绿色点代表只能移动，红色点代表只能吃子，黄色点代表走吃皆可。
 
### 穹庐 | Yurt (Y)

![Yurt](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Yurt.png)
 
穹庐可以斜走一格或往正前方行走一格，与日本将棋的银将相同。可汗方只有一个穹庐，开局位于d8，即原本后的位置，不过与后定位不同，它很弱，属于轻子，在作战能力上仅比兵强。但是不要小看它，因为它是可汗方少数的走吃相同的棋子。而且不像怯薛，穹庐作为轻子，它可以在支援防御和兑子战中发挥很大的作用。
Yurt 意为穹庐，或蒙古包，是蒙古人和突厥人常用的可移动的房屋。棋子的设计反映了它们的重要性和短距离移动能力。

### 怯薛 | Keshig (H)

![Kheshig](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Kheshig.png)

怯薛的走法融合了马和王。怯薛一开始位于b8和g8，即原本「马」的位置。但它与马不同，它是可汗方的最强棋子。它可以看成是左右两个分队的指挥官。一般来说，开局最好是不要轻易出动，如同国际象棋的后开局不宜过早出动一样。
Kheshig，中文译作怯薛、宿卫、禁卫。他们是蒙古帝国的精英怯薛军。作为怯薛的代表，怯薛在保护王的局面下非常有用。事实上，王国方很难在双怯薛的残局中取胜。
*（《元史·兵志二》：“怯薛者，犹言番直宿卫也。” ）*

### 弓骑兵 | Horse Archer (A)

![Horse Archer](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Archer.png)

弓骑兵属于走吃分离的棋子，移动走马步，但吃子时斜走不限格数，注意弓骑兵并非单色棋子，它比主教的强度略高。
弓骑兵（或称骑射手）是蒙古军队中一个核心兵种，他们快速的机动性和强大的打击能力在战斗中对敌人是非常大的威胁。在本棋对局中，弓骑兵可以快速的实施捉双、牵制等战术以谋取优势。
 
### 枪骑兵 | Lancer (L)

![Lancer](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Lancer.png)

枪骑兵属于走吃分离的棋子，移动走马步，但吃子时直走不限格数，如同车。注意它不像车那样具有很高的机动性，因此价值比车偏低，在残局中枪骑兵的弱点更为明显。它的价值比弓骑兵略高。
枪骑兵是蒙古军队中另一个核心兵种，即重骑兵。在本棋中，枪骑兵虽然不如车，但是他们可以较早地投入战场，扩大场面优势。
 
## 棋子价值

准确的棋子价值尚无定论。以下是 Fairy-stockfish 在对局中所使用的数据。

王室方	| 价值 (前期 / 后期) | 可汗方 | 价值 (前期 / 后期)
-- | -- | -- | --
兵| 120 / 213	| 兵 | 120 / 213
后 | 2538 / 2682	| 穹庐 | 630 / 630
象 | 825 / 915	| 弓骑兵	| 1100 / 1200
马 | 781 / 854	| 怯薛 | 1800 / 1900
车 | 1276 / 1380	| 枪骑兵 | 1050 / 1250

下表更为简明

王室方	| 价值 | 可汗方	| 价值
-- | -- | -- | --
兵 | 1	| 兵 | 1
后	| 9	| 穹庐 | 2
象 | 3 | 弓骑兵 | 4
马 | 3 | 怯薛 | 7
车 | 5 | 枪骑兵 | 4

## 战略
游戏推出的时间不长，大部分的资料来自电脑对弈。

可汗不能王车易位，所以一个基本的战略是尽快将可汗移动到g7，最好是在前4回合内完成。
Fairy stockfish在56%的游戏中走了Kf7。王室方的首选依序是d4，g3，b3。
可汗方的主要弱点是它的棋子不能持续地控制棋盘的某个位置。例如，如果攻击可汗方的枪骑兵和弓骑兵，它们就因为撤退而离开它们原本的控制范围。国王方可利用这一点。

### 开局
以下分析来自Fairy-Stockfish的评估

白方开局	| 游戏比例 | 白方胜率 % | 金方胜率 % | 金方应手
-- | -- | -- | -- | --
d4 | 38%	(47) | 45% | 38% | Kf7 ~= c5 >> Hb7
g3	| 24% (30)	| 33% | 43% | Kf7 >> d5
b3 | 14% (18) | 33% | 44% | Kf7 >> Lc7
e3 | 11% (14) | 50% | 50% | Kf7 ~50% of the time
d3 | 6% (8) | 25% | 25% | e5 ~=Kf7
Nf3 | 3% (4) | 25% | 50% | e5 always
e4 | 2% (3) | 33% | 67% | d5
c4 | 1% (1) | 100% | 0% | Kf7

四个最常见开局。下述的Castle代表金方尽快把可汗移动到f7。小括弧代表其他选择。

**Benko's Castle - 双角攻击** - 最常见
1. g3 Kf7
2. e4 Kg7
3. (Bd3 or Nf3) ...

![Benko's Castle](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/BenkoCastle.png)

*Benko's Castle ，截止2... Kg7*

**Stockfish Defense - 封闭变例**
1. d4 c5
2. dxc5 *bxc5*
3. c4 Kf7
4. (Nc3) ...

**Stockfish Defense - 开放变例**
1. d4 c5
2. dxc5 *dxc5*

**Stockfish Defense - 后翼推进**
1. d4 c5
2. *e3* cxd4
3. exd4 b5
4. b3 Kf7
5. c4

![Stockfish Defense Queenside Push](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/QueensidePush.png)

*Stockfish Defense - 后翼推进，截止5. c4*