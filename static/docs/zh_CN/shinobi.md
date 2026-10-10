# ![Shinobi chess](https://github.com/pychess/pychess-variants/blob/master/static/icons/shinobi.svg) 忍者象棋

![Shinobi](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Shinobi.png)

忍者象棋是2019-2020由Couch Tomato与Fables推出的游戏，也是非对称棋组变体系列的第四款。游戏的背景设定为王国的军队（黑）入侵了樱流忍者一族（粉）的领土而展开的战斗*（译者注：樱流忍者，原文如此，为Sakura Clan）。*忍者方一开始子力较弱，但能快速召集友军支援与防御。忍者方开始时握有大量后备子力在手中，可打入到自己的领土（前四行）。此外，忍者方的棋子在达到最后两行之后可升变，类似于日本将棋的规则。但是与将棋不同的是，吃掉的棋子不可再打入。游戏本身极其平衡，甚至比国际象棋更平衡，双方的胜率接近五五开。
 
## 规则
1.	开局布局如上图所示。注意忍者方有额外的棋子在手中。
2.  忍者方 (粉红方）先手。
3.  忍者方手里的棋子只能打入前四行（棋盘的前一半）
4.	所有忍者方的基本棋子，达到第七或第八行之后会升变。同样的，王国方的兵只需要达到第七行就可升变。
5.	双方的兵只可升变成兵长(Captain)。兵长的走法见下面说明。
6.	双方有另一个获胜条件：触底获胜(**Campmate**). 将王安全移动到对方底线也算获胜。
7.	**困毙(Stalemate)**：若一方在未被将军的情况下没有合法的行动，则该方失败（与国际象棋的逼和不同）
8.	**重复局面(Repetiiton)** - 若一方累计三次重复出现同一局面，则平局。
9.	忍者方没有王车易位。
10.	其他规则，包括王国的移动和吃过路兵跟国际象棋一样

## 忍者方的棋子

忍者方有五个特有兵种：忍者、龙王、香车、桂马、僧兵。兵长可由兵升变，因此双方都可以使用，但只有忍者方开局有兵长。请放心，所有的棋子走法都和常见的棋子类似。对忍者一方而言，忍者和龙王是特有的棋子，其他棋子基本上是王国方的弱化版。 忍者方在升变之后也可以拥有王国方的棋子（车，象，马）。 忍者方的王叫做Kage(かげ，影)，棋子的造型也不同，但是走法和国际象棋的王是完全一样的。类似的，忍者方的车（飞车）和象（僧正）也有特有的棋子造型，但不影响其走法。

### 兵长 | Captain (C)

![Captain](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ClanCaptain.png)

一开始忍者方d1位置有一个兵长。双方的兵达到第七行时也必须升变为兵长。兵长的移动和王完全相同，即八方一格。当然，他们和王不同，他们可以被吃。

### 忍者 | Ninja (J)

![Ninja](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Ninja.png)

忍者可以看成是国际象棋象和马的结合，即斜走不限，或者跳马步。这个棋子在许多象棋变种(如Grand Chess)中称为大主教(ArchBishop)。忍者是忍者一方的最强棋子，他拥有很灵活的机动性，能轻易绕过对方防线。忍者能单独对角格的王形成威胁。忍者的棋子强度略弱于后。
忍者不可升变。

### 龙王 | Dragon (D)

![Dragon](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Dragon.png)

龙王既可以直走任意格数，也可以斜走一格。与将棋的的龙王完全相同。龙王棋子略弱于忍者，但比车略强。
龙王不可升变。

### 香车 (L) | Lance (L)

![Lance](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Lance.png)

香车只可向前走任意步数，与将棋的香车完全相同。开局时，忍者方手里有一枚香车，这枚香车可以借助打入，实行串打战术。请注意，香车不能后退，所以打入时请务必思考谨慎。开局的香车灵活性较差，但是也能有效控制他们所在的列。
香车在达到第七或第八行时，升变成**飞车(Rook)**，走法和车相同。（在达到第七行时，可以不升变；达到第八行时则必须升变）
香车比其他棋子弱，不过因为它们可以升变成车，所以他们的隐藏价值不可忽视。
（注：升变是否为强制取决于该棋子在该位置是否完全不可能再移动，如下述桂马在第七第八行都必须升变）

### 桂马 | Wooden Horse (H)

![Wooden Horse](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Horse.png)

桂马走法和马相似，但只能向前跳跃，如同将棋的桂马。忍者方开局有一枚桂马在手中，桂马 的走法结合打入，使得它能够有效捉双。但是桂马不可后退，因此它的打入也需要谨慎思考。开局在场上的两枚桂马也可以发挥类似作用，但是它们不能后退，所以移动前也需要注意。
桂马在达到第七或第八行时**必须**升变成**马兵（Knight）。**
桂马相对国际象棋的棋组是非常弱的，但它们具备升变成马这个隐藏能力。
*（译者注：马兵的名字取自广将棋，尽管它和马的走法完全一样）*

### 僧兵 | Monk (M)

![Monk](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Monk.png)
僧兵的移动为斜向一格。忍者方开局手里有两个僧兵，场上没有。
僧兵达到第七或第八行时，可以升变成**僧正(Bishop)**，僧正走法与国际象棋主教相同。
僧兵也是很弱的子，但是它也拥有残局升变为主教的隐藏能力。
 
## 战略
游戏还年轻，战略还在发展中！大部分的数据来自电脑比赛

棋子的价值难以评估，因为升变的能力。请注意 Stockfish 的一开始的价值估计会有误差，不过它最后的胜率有平衡。

### 开局
尚未进行过全面分析。但是，经统计，Fairy-Stockfish 极其喜欢开局派出忍者：1.J@c3。之后的应对种类非常多。