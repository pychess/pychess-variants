# ![Orda Mirror](https://github.com/pychess/pychess-variants/blob/master/static/icons/ordamirror.svg) 可汗对决棋 | Orda Mirror
![Orda Mirror Board](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/OrdaMirror.png)

可汗对决棋(Orda Mirror)是由 Couch Tomato 于2020年推出的国际象棋变体玩法，也被认为是可汗西征棋的衍生变体。该游戏的两方均设计成可汗西征棋中加入的可汗棋组，变成了一个可汗vs可汗的对决。但是棋组相比原版又做了一个改动：原版的穹庐被替换成了新棋子战隼，一个走棋如后，吃子如马的棋子（其他棋子走子如马）。新的棋子让棋组在保留游牧民族的主题的同时又增加了些许机动性。
 
## 规则
1.	棋盘布局如上图所示。
2.	白方先手。
3.	本棋没有王车易位。
4.	兵可以升变为棋组内的任一棋子（王除外）。
5.	**触底获胜**也适用于本游戏——将自己的王安全移动至对方底线时，也获得胜利。
6.	其他规则跟国际象棋一样，包括逼和(无子可动算和棋)和长将和。

## 可汗棋组棋子
可汗棋组（或称部落棋组）有四种新的兵种：2枚枪骑兵、2枚弓骑兵、2枚禁卫、1枚战隼（战隼为可汗对决棋的新棋子）。禁卫（马+王）是本棋最强棋子，左右翼各一。 
可汗方的王称为可汗(Khan)，棋子造型与王不同，但本质的走法和地位与王完全一样，唯一的区别是棋子外形和名称。T
枪骑兵和弓骑兵较为特殊，他们的走子和吃子方式不一样（犹如西洋棋的兵一样）。弓骑兵和枪骑兵都是以马的走法移动，它们的吃子则分别以主教和车的方式。战隼替换了后，与骑兵不同，它走子如同后，吃子如同马。禁卫走吃相同，走法是王+马。

**可汗** 棋子	| 国际象棋对应	| 走子 | 吃子
-- | -- | -- | --
战隼 | 后 | 后 | **马**
弓骑兵 | 象 | **马** | 象
禁卫 | 马 | **马**+王 | **马**+王
枪骑兵 | 车 | **马** | 车

下面是每个棋子的细节和图示。绿色点代表只能移动，红色点代表只能吃子，黄色点代表走吃皆可。
 
###  战隼 | Falcon (F)

![Falcon](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Falcon.png)
 
战隼的走吃不同，注意它和其他部落棋子不一样，它走子是后的走法，吃子是马的走法。

### 禁卫 | Kheshig (H)

![Kheshig](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Kheshig.png)
 
禁卫的走法融合了马和王，在部分棋中被称为半人马(Centaur)。禁卫一开始位于b8和g8，即原本「马」的位置。但它与马不同，它是可汗方的最强棋子。它可以看成是左右两个分队的指挥官。

### 弓骑兵 | Horse Archer (A)

![Horse Archer](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Archer.png)
 
弓骑兵属于走吃分离的棋子，移动走马步，但吃子时斜走不限格数，注意弓骑兵并不是象那样的单色棋子，它比象的强度略高。
 
### 枪骑兵 | Lancer (L)

![Lancer](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Lancer.png)
 
枪骑兵属于走吃分离的棋子，移动走马步，但吃子时直走不限格数，如同车。

## 策略
游戏推出的时间不长，因此策略还在研究之中。大部分的资料来自电脑对弈。

棋子的具体价值目前尚不明晰。目前认为，战隼、弓骑兵、枪骑兵的价值基本接近，禁卫的价值比其余三个稍高，通常作为攻击的主力。

<iframe width="560" height="315" src="https://www.youtube.com/embed/Ap4mGkR8HDA" frameborder="0" allowfullscreen></iframe>
