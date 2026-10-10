# ![Shinobi chess+](https://github.com/pychess/pychess-variants/blob/master/static/icons/shinobi.svg) 新忍者象棋 | Shinobi Chess+

![Shinobi+](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Shinobiplus.png)

忍者象棋是 2021 年由 Couch Tomato 与 Fables 推出的游戏，也是非对称棋组变体系列的第四款。游戏的背景设定为王国的军队（黑）入侵了樱流忍者（Sakura Clan）的领土（粉）而展开的战斗。忍者方一开始子力较弱，但能快速召集友军支援与防御。忍者方开始时握有大量后备子力在手中，可打入到自己的领土（前四行）。此外，忍者方的棋子在达到最后两行之后可升变，类似于日本将棋的规则。但是与将棋不同的是，吃掉的棋子不可再打入。

初版的忍者象棋，引擎自战测试的结论是双方五五开。但经过大量玩家和 NNUE 引擎的提升，发现忍者方拥有较大优势。因此经过调整，更新为现在的忍者象棋（Shinobi+），调整了开局和手上的棋子配置，新增了对应将棋龙马的妖狐，并且调整了黑方的升变。

## 基本规则
1.	开局布局如上图所示。注意忍者方有额外的棋子在手中。
2.  忍者方（粉色）先手。
3.  忍者方手里的棋子只能打入前四行（棋盘的前一半）
4.	所有忍者方可升变的棋子，走到第七或第八行之后会升变。王国方的兵只需要达到第六行就升变。
5.	双方的兵只可升变成兵长(Captain)。兵长的走法见下面说明。
6.	双方有另一个获胜条件：触底获胜(**Campmate**). 将王安全移动到对方底线也算获胜。
7.	**困毙(Stalemate)**：若一方在未被将军的情况下没有合法的行动，则该方失败（与国际象棋的逼和不同）
8.	**长将（Perpetual check）**：禁止循环的长将局面，若连续重复进行三次长将循环，则不能继续循环将军，否则判负。
9.	**重复局面(Repetiiton)** - 若一方累计三次重复出现同一局面，则平局。
9.	忍者方没有王车易位。
10.	其他规则，包括王国棋子的移动和吃过路兵，与国际象棋一样。

## 忍者方的棋组

忍者方拥有九种棋子（其中六种为忍者方特有）：兵 8 枚，王 1 枚，**忍者**、**龙王**、**妖狐**、**香车**、**桂马**、**僧兵**、兵长各 1 枚。兵长也可由双方的兵升变而来。请放心，所有的棋子走法都和常见的棋子类似。其中，忍者、龙王和妖狐拥有较为特别的走法，其他三种棋子可以看成是王国方棋子的弱化版。

香车、桂马、僧兵通过升变，也可以变成和王国方的棋子一样的走法（车，马、象）。粉色方的王叫做影王（Kage），棋子外形和称呼虽然都不同，但走法和王完全一样。类似的，忍者方的车（飞车）和象（僧正）也有特有的棋子造型，但走法和车象都是一样的。 

### 兵长 | Captain (C)

![Captain](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ClanCaptain.png)

开局时，忍者方拥有一个兵长。兵长也可由兵升变得到。
兵长的移动和王完全相同，即八方一格。
当然，他们和王不同的是，它们可以被吃。

### 忍者 | Ninja (J)

![Ninja](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Ninja.png)

忍者可以看成是国际象棋象和马的结合，即斜走不限，或者跳马步。这个棋子在许多象棋变种(如Grand Chess)中称为大主教(ArchBishop)。忍者是忍者一方的最强棋子，他拥有很灵活的机动性，能轻易绕过对方防线。忍者能单独对角格的王形成威胁。忍者的棋子强度略弱于后。

忍者不可升变。

### 龙王 | Dragon (D)

![Dragon](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Dragon.png)

龙王可以直走任意格数，或斜走一格。与将棋的的龙王完全相同。龙王比忍者弱，但比车（飞车）略强。

龙王不可升变。

### 妖狐 | Fox (F)

![Fox](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Fox.png)

妖狐可以斜走任意格数，或直走一格。这与将棋的龙马完全相同。妖狐比忍者稍弱，但比车（飞车）强。

妖狐不可升变。

### 香车 | Lance (L)

![Lance](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Lance.png)

香车只可向前走任意步数，与将棋的香车完全相同。开局时，忍者方手里有一枚香车，这枚香车可以借助打入，实行串打战术。请注意，香车不能后退，所以打入时请务必思考谨慎。开局的香车灵活性较差，但是也能有效控制他们所在的列。

香车在达到第七行时，可升变成**飞车(Rook)**，走法和车相同。若达到第八行，则必须升变。
（注：升变是否为强制取决于该棋子在该位置是否完全不可能再移动，如下述桂马在第七第八行都必须升变）

香车比其他棋子弱，不过因为它们可以升变成车，所以他们的隐藏价值不可忽视。

### 桂马 | Wooden Horse (H)

![Wooden Horse](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Horse.png)

桂马走法和马相似，但只能向前跳跃，如同将棋的桂马。忍者方开局有一枚桂马在手中，桂马的走法结合打入，使得它能够有效捉双。但是桂马不可后退，因此它的打入也需要谨慎思考。

桂马在达到第七或第八行时**必须**升变成**马兵（Knight）。**
桂马相对国际象棋的棋组是非常弱的，但它们具备升变成马这个隐藏能力。
*（译者注：马兵的名字取自广将棋，尽管它和马的走法完全一样）*

### 僧兵 | Monk (M)

![Monk](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Monk.png)

僧兵的移动为斜向一格。忍者方开局手里有一个僧兵。

僧兵达到第七或第八行时，可以升变成**僧正(Bishop)**，僧正走法与国际象棋主教相同。
僧兵也是很弱的子，但是它也拥有残局升变为主教的隐藏能力。
 
## 游戏策略
游戏推出时间不长，策略还在发掘中！目前大部分的数据来自引擎自战。

棋子的价值尚未得到评估，因为要考虑到升变。请注意Stockfish的一开始的价值估计会有误差，不过它最后的胜率有平衡。
