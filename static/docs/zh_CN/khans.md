# ![Khans chess](https://github.com/pychess/pychess-variants/blob/master/static/icons/khans.svg) 可汗象棋 | Khan's Chess

![Khans Chess](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Khans.png)

![Legend](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/KhansLegend.png)

可汗象棋（Khan's Chess）是由 Couch Tomato 于 2023-2024 年设计的棋种，也是可汗西征棋的新版本。如同可汗西征棋一样，可汗象棋也是一个非对称的棋类游戏，国际象棋棋组对抗的是具有马的移动方式，但具有不同吃法的棋组。可汗象棋的设计动机主要和可汗西征棋设计之后，Fairy Stockfish 的不断发展有关，主要原因有二：（1）NNUE 神经网络的评估认为，可汗西征棋在高水平对局的平衡性并非之前认为的五五开；（2）可汗西征棋中依然使用了国际象棋的兵卒，需要替换成更符合主题背景的棋子。事实上，从游戏设计角度考虑，国际象棋的兵卒更像是一种适用于防御的单位，而可汗棋组更多的是需要引进高机动性的棋子以符合其风格。可汗棋组的背景是蒙古的游牧部落，他们通常以纯粹的骑兵作战和快速袭扰战术而闻名。而由于 Fairy Stockfish 经过更新拓展了功能，增加的兼容性，可以支持更多的自定义棋子。经过反复测试，可汗象棋在可汗西征棋的棋组基础上，用两种新棋子取代了原本的兵卒和穹庐——侦察骑兵（Scout）和可敦（Khatun，原意为可汗的正妻，因此用于对应国际象棋的后）。新的兵——侦察骑兵——改为布置在第二行而非第三行。经过 NNUE 测试， 游戏目前是平衡的。

对于熟悉可汗西征棋的玩家来说，您只需要了解新棋子的走法。其余的规则与可汗西征棋基本相同。
 
## 基本规则
1.	棋盘布局如上图所示。注意双方棋组对应的棋子处于同一位置。
2.	双方棋子走法仅有王是完全相同的（部落方的王称为可汗）
3.	王国方（白方）先手。
4.	可汗方（金方）没有王车易位。
5.	兵的升变与国际象棋完全相同。然而，可汗方的侦察骑兵只能升变成可敦。
6.	双方的另一个胜利条件是**触底获胜**——将自己的王安全移动至对方底线时，也获得胜利。
7.	**困毙**（Stalemate）：无子可动的一方落败，而非逼和。
8.	其他规则，例如三次循环重复规则，与国际象棋相同。

## 可汗方的棋子
可汗方共有五种新棋子：侦察骑兵8枚、枪骑兵2枚、弓骑兵2枚、怯薛2枚、可敦1枚。怯薛是可汗方最强的棋子（走法为王+马），两边各一枚。可敦虽然与国际象棋的后对应，但相对较弱
可汗方的王与国际象棋的王走法完全相同，只是棋子造型和称呼不一样。
枪骑兵、弓骑兵、可敦属于走吃分离的棋子，它们的走法均和国际象棋马相同，但吃法分别对应车、象、王。怯薛则是普通的走同吃的棋子。
侦察骑兵也是走吃分离。其完整走法见下面说明。

**可汗** 棋子	| **王国** 棋子	| 走法 | 吃法
-- | -- | -- | --
可敦 | 后 | 马 | 王
弓骑兵 | 象 | 马 | 象
怯薛 | 马 | 马+王 | 马+王
枪骑兵 | 车 | 马 | 车

下面介绍棋子的详细走法。下面的图例中，绿色点代表仅可移动，红色点代表仅可吃子，黄色点代表走吃皆可。

### 侦察骑兵 | Scout (S)

![Scout](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Scout.png)
 
侦察骑兵的走法如图。它走马步，但只能向前，不能向后。因此，它只有四个方向移动。侦察骑兵吃子只能向前一格吃。它虽然攻击力不高，也不能像国际象棋的兵卒一样形成坚固的兵链，但是它具有快速的移动能力，升变的速度比国际象棋的兵快很多。

侦察骑兵行动至对方底线则立刻升变成可敦。
 
### 可敦 | Khatun (T)

![Khatun](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Khatun.png)
 
可敦走法和马相同，但吃法和王一样。它虽然属于弱子，但它在防守中能发挥很大作用。

### 怯薛 | Kheshig (H)

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

