# ![Shinobi chess](https://github.com/pychess/pychess-variants/blob/master/static/icons/shinobi.svg) 忍棋

![Shinobi](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Shinobi.png)

忍棋是2019-2020由Couch Tomato與Fables推出的遊戲，為非对称性变体系列之四。西洋棋軍隊（王国，黑方），入侵了櫻花忍者城寨（粉红方）的领土。虽然忍者門一開始軍力較弱，但能即刻招募盟友防御:开始時握有力在手中，可打入到自己的领土（前四行）。此外，忍方的棋子在达到最后两行之后可升变，有如日本将棋的规则，不过吃掉的棋子不可再打入。游戏本身极其平衡，甚至比国际象棋更平衡，双方的胜率接近一半。
 
## 规则
1.	设置如上所示。
2.  忍方 (粉红方）是先手。
3.  忍方手里的棋子只能打入前四行（棋盘的前一般）
4.	所有Clan的小棋子在达到第七或第八行之后会升变。类似王国的兵只需要达到第七行就可升变。
5.	双方的兵只可升变成队长
6.	双方有另一个生理条件：Campmate. 这个情况会出现在一个王能安全达到对方的底线。
7.	**Stalemate**  - 没有合法的棋步代表失败（不是按照国际象棋的和平）
8.	**Repetiiton** - 三次重负同一局面代表失败。
9.	Clan不可王车易位。
10.	其他规则，包括王国的移动和吃过路兵跟国际象棋一样

## Clan的棋子

Clan有五个独特单位：忍着，龙王，香车，桂马和士。队长们（并的升变）也在双方的部队中，不过只有Clan一开始拥有。忍着和龙王更特殊，而其他棋子基本上是王国的弱对口单位。Clan在升变之后有权使用王国一样的棋子（车，象，马）。Clan的王可叫做Kage，拥有自己的标志，不过他行为国王。Clan的车和象也有自己的审美。

### 队长 | Captain (C)

![Captain](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ClanCaptain.png)

一开始Clan后的位置倒是站一个队长。更多的队长可得到在兵达到第七行时。队长的移动如王一样，当然他们不是皇家的所以可能被吃掉。

### 忍着 | Ninja (J)

![Ninja](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Ninja.png)

忍着是从象和马的融化中诞生，这棋子是Clan的大主教。这是他们的最强棋子，比只后弱一点。忍着是非常棘手而甚至能单人匹马把对方的王将死。忍着不可升变。

### 龙王 | Dragon (D)

![Dragon](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Dragon.png)

龙王来自车和王的合作，就是日本将其的龙王（升变的车）。龙王不如忍着也不可升变，但无论怎样，它是Clan的佼佼者。

### 香车 (L)

![Lance](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Lance.png)

香车可向前走任意步数，类是四分之一的一辆车。正是日本将其的香车。一开始手里有一辆香车。因为他不可撤退，他们打入的威胁比他们的存在强数倍。初始的香车更不灵活，不过因为他们的存在对方不该让它们的列被打开。香车可升变成车在达到第七或第八行。香车的价值比其他棋子若，不过他们的存在不能忽视，因为他的潜在是升变成一枚极强的棋子。

### 桂马 | Wooden Horse (H)

![Wooden Horse](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Horse.png)

桂马是一种顽固的马，只能移动到一匹马的最后两个方格，正犹如日本将其的桂马。一开始有一匹马在手里。因为不可撤退，它的打入需要考虑！一开始在部队中的两匹马也该认真移动。桂马会在达到最后两行之后升变成马。这个能力和威胁是一种幕后的强点。

### 士 | Monk (M)

![Monk](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Monk.png)
士的移动为斜向一格。一开始两个士在手里。士会升变成象在侵入最后两行时。跟桂马一样，这一点可逼迫王国不断的防御它的领域。
 
## 战略
游戏还年轻，战略还在发展中！大部分的数据来自电脑比赛

棋子的价值难以评估，因为升变的能力。请注意Stockfish的一开始评价可查不少，不过它最后的胜率有平衡。

### 开局
尚未进行过全面分析。可是Fairy-Stockfish极其喜欢1.忍着@c3。之后它不清楚。
