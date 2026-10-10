# ![Chak](https://github.com/pychess/pychess-variants/blob/master/static/icons/Chak.svg) 玛雅象棋 | Chak

![Chak](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/Chak.png)

## 背景

目前的大众观点认为，国际象棋游戏最早起源于印度，尔后演变为波斯象棋，传播到欧洲并发展出现代的形式。在东亚，尤其是中国和日本，也有丰富的棋类游戏，并且融合了各地的传统文化。世界各地的许多文明都有自己的象棋，然而，美洲原住民呢？中美洲曾经拥有伟大的帝国。如果他们也有自己的棋类游戏呢？

从这个假想的脑洞出发，玛雅象棋（Chak）诞生了。玛雅象棋是 Couch Tomato 于 2021 年设计的游戏，设计理念是使用象棋常见的元素：王、车、马和兵，并引入中美洲的玛雅文明主题。例如，对于包括玛雅文明在内的中美洲文明来说，以祭祀仪式为特征的本土宗教是社会的基本组成部分。因此，在玛雅象棋中引入了神庙和祭祀使用的祭品，并且作为游戏的核心。

Chak 这个词来自玛雅神话中雨神恰克（Chaac，一说Chac），它是雨神和雷霆之神，并且拥有战争一般暴怒的性格。这与玛雅象棋引入的河边战场相符合。另一个相符之处是，玛雅语中相似的两个词「Chuc-ah」(俘虏) 和「Ch’ak」(斩首)被用于称呼玛雅象棋中的两个胜利条件：「登坛」和「将死」。

## 基本规则

分为白绿两方，白方先行。

### 棋盘

玛雅象棋的棋盘为9x9，如下图:

![Chak](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/ChakBoard.png)

其中有三个特殊的区域:
-**河界(River)**, 是两方的边界，王和兵过河后可升变，然而，**升变的棋子不能再退回己方阵地**，只能在对方一侧行动。
-**神殿(Temple)**, 棋盘上划出的一个 3x3 区域，其中心为**祭坛**。神殿本身并无特殊的作用。然而从游戏战略上讲，神殿非常重要，因为有许多攻防的战术都在神殿区域进行。
-**祭坛(Altar)**, 神殿的中心。将己方国王安全移动至对方祭坛即获胜。

### 胜负条件

有三种胜利条件:
**将死（Checkmate）** - 攻击对方王，且对方无法解除将军。
**困毙（Stalemate）** - 让对方无子可动，即使王没有被将军。与国际象棋的逼和不同。
**登坛（Altar mate）** - 将己方王移动到对方祭坛，且不受攻击。

以下情形为和棋:
**重复动子** - 同一个局面连续重复三次。
**50步无吃子** - 如果五十步都没有棋子被吃则和棋。
*（译者注：此处并未包含认输、提和等比赛规则，尽管原文中列举了）*


## 棋子

### 王 | King(K)

![King](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/ChakKing.png)

王 (*Ajaw*, 读作 「Dachau」) 走法就如就如国际象棋的国王，朝八方走一格。
王过河后立即升变为「神王」

### 神王 |Divine King(D)

![Divine King](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/DivineKing.png)

神王可向任何方向移动最多*两个*方格，也可以通过被对方棋子威胁的方格（换句话说，它不像国际象棋的王车易位，王的路径上不能有棋子攻击）。请注意，国王一旦升变，便不能退回己方阵地！由于其攻击范围，神王可以将对方未升变的国王将死。
神王的符号为「D」，是为了与国王「K」区别。神王的棋子造型与王的区别仅仅是一个装饰的不同，但在对局中的王是否升变只需看王是否过了河界即可。这样设计是为了方便在编辑器中摆放棋子。

### 美洲虎 | Jaguar(J)

![Jaguar](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/Jaguar.png)

美洲虎的走法是国际象棋马和王的融合，它可以跳马步，或者八方行动一格。
这种走法在其他变体中常被称为半人马（Centuar），与幕府将棋中的将军和可汗西征棋中的怯薛相同。
美洲虎是玛雅象棋中最强的棋子，它的走法能够轻易实现捉双，对敌人是个很大的威胁。

### 绿咬鹃 | Quetzal(Q)

![Quetzal range](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/QuetzalRange.png)

绿咬鹃，中文简称鹃或者鸟。它的走法很特别，它可以沿八个方向（横、竖或斜）移动任意格，但是它**必须**跳过一个棋子进行移动或吃子。对于熟悉韩国将棋的人来说，这是八方版本的「包」，但没有「不能跳过对方的鸟」的限制。
绿咬鹃是第二强的棋子，但就如象棋的炮，在残局会因为没有炮架而失去价值。

![Quetzal example](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/QuetzalLegal.png)

*范例*: 上图中，绿咬鹃可以移动到标圈的格子，且能吃掉红圈位置的棋子。
*绿咬鹃(Quetzal)是南美洲的一种漂亮的绿色鸟类，在玛雅文明和阿兹特克文明中是羽蛇神的化身，具有神圣的地位。它也是危地马拉的国鸟。*

### 萨满 | Shaman(S)

![Shaman](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/Shaman.png)

萨满可以斜走一格，或者朝前后移动一格。与中将棋的猛豹相同。
由于步伐小，它是最弱的子之一，通常用来防守。
该棋子的造型可以反映它的走法。

### 秃鹫 | Vulture(V)

![Vulture](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/Vulture.png)

秃鹫的走法和国际象棋的马完全相同。

### 毒蛇 | Serpent(R)

![Serpent](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/Serpent.png)

毒蛇就如中国象棋的车，可朝一个方向任意直行。
它是第三强的子，仅次于美洲虎和绿咬鹃。

### 兵 | Pawn(P)

![Pawn](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/ChakPawn.png)

兵的走子与吃子是不同的。走法可以向前、左、右移动一格，如同中国象棋的过河卒。吃子的方式则为斜前一格吃子，如国际象棋的兵。
兵过河后升变为勇士。

### 勇士 |Warrior(W)

![Warrior](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/ChakWarrior.png)

勇士的走法和萨满完全相同，可以斜走一格，或者朝前后移动一格。与萨满不同的是，勇士不能退回河界后。

### 祭品 |Offering(O)

![Offering](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/Offering.png)

祭品不能移动,也不能吃子。它一直待在在祭坛中心。它的作用不只是为了展现主题的装饰，它可以作为绿咬鹃的炮架。并且，在登坛的攻防战中，它还可以协助己方的王，防御神王的攻击。如果此时没有其他棋子，一般会是和棋。如果祭品在先前己被吃了，神王就有办法驱离对方的王，从而登坛。

## 子力价值

详细价值尚未知，但以下大小关系是己知的: 美洲虎 > 绿咬鹃 > 毒蛇 > 秃鹫 > 萨满 > 勇士 > 兵

## 策略 - 棋子用法

**绿咬鹃**: 始终注意绿咬鹃的路线。在游戏开始时，任何移动到绿咬鹃前面的棋子都会作为炮架攻击对方的美洲虎，这是一个稍微有利的交换。
**美洲虎**: 建立防御并防止美洲虎过河。如果美洲虎在你的棋子生根之前就发起攻击，将可以轻松地捉双。
**兵**: 兵非常灵活和强大，并且很早就可升变。正因如此，它不像其他棋种的兵那样可任意弃子；如果您决定弃兵，请确保获得更好局势，因为在游戏结束时一个兵的差距可能会左右胜败。
**神殿**: 神殿非常重要，因为对方的神王只要到达神殿就赢棋。

## 策略 - 残局

残局通常在抢先登上祭坛。在本节中，我们将关注以神王为唯一攻击棋子的残局。

### 王 v.s 王 

若对方国王是唯一的防守者，攻击者只需要迫使对方王移出神殿，便可以轻松登坛:

![KvsKzugzwang](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/KvsKzugzwang.png)

当祭品还在的时候，攻击者仍然可以获胜，但更加棘手。攻击者应该做的不是登坛，而是以下这种困毙：

![KvsKStalemate](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/KvsKStalemate.png)

以下是走出这种困毙的棋谱:

![KvsKO](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/KvsKO.png)

1. Dd6+ 
2. Kf7 Dd7+ 
3. Kf2 De8
4. Kf9 Df7+
5. Ke9 De7!

如此形成以下局面:

![KvsKOzugzwang](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/KvsKOzugzwang.png)

此时绿方被迫移动，白方即可走出困毙。

然而。如果防守方多出一子（不动的绿咬鹃除外），情况就会发生巨大变化，如下:

![KvsKdraw](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/KvsKdraw.png)

不管祭品是否还在，神王都没有办法将死守方的王。唯一需要担心的是下错棋，让自己多出来的一子被神王吃掉。因此建议将其保留在最后4列内，因为神王永远无法到达那里，如此双方便和棋。

### 堡垒

堡垒是指有子防守着祭坛，且防御子力均被保护。面对这种堡垒，对方的单王无计可施。

![Fortresses](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/Fortresses.png)

以上这些范例都意谓着，若一方将棋子移开防守，将卸掉堡垒，若双方都如此则导致和局。另一方面，若一方的堡垒有根而一方没有，该子通常可以过河并攻击对方的堡垒，通常多子的一方会获胜。

### 其他防御

#### 美洲虎

美洲虎对神王可能会因重复局面而和棋

![JaguarPerpetual](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/JaguarPerpetual.png)

...除非对方可以直接弃美洲虎登坛。

![JaguarPerpetual2](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/JaguarPerpetual2.png)

然而当祭品还在时，又是两码子事:

![JaguarvsKO](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/JaguarvsKO.png)

绿可走 1. Jf9; 白方唯一可以继续攻击美洲虎的走法为 Df7, 但当 2. Je9+ Dg 而 3. Jd9, 则将失去对美洲虎的威胁。而若白方花二步来攻击美洲虎， 绿方可以在河的另一头作更有义意的事。若白把王动到f9, 则 Jd8 后，同样也会失去对美洲虎的威胁。所以最好是把王动到 d7 来迫使美洲虎移动。最好记得以走法来形成和棋。

#### 毒蛇

![SerpentFortress](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/SerpentFortress.png)

残局毒蛇可以封住整条横线/竖线，如此神王便无法登坛。

![SerpentFortressTrap](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/SerpentFortressTrap.png)

而且，若神王从划记的格子离开去骚扰毒蛇，可能会付出代价，例如:

![SerpentFortressTrap2](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/SerpentFortressTrap2.png)

白方神王放弃威胁祭坛，转而是试图攻击毒蛇，但是这是完全没有用的，绿方抢先占据e8，用毒蛇攻击白方两个萨满，此时若白方Kd7回头，则毒蛇e2，依然守住绿祭坛。此时白萨满无论吃掉毒蛇与否都无法阻止绿方登坛。