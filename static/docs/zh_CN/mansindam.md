# ![Mansindam](https://github.com/pychess/pychess-variants/blob/master/static/icons/mansindam.svg) 万神谈 | Mansindam

_一种结合了强力棋子和打入玩法的棋类游戏。_

![Mansindam](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/board.png)

![Mansindam](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/promotions.png)

## 棋子
所有的棋子在升变时，都附加八方1格的走法。

### 步兵/Pawn(P) 
![Pawn](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/pawn.png)

步兵，简称步，仅可向前走吃1格。升级为哨兵。

### 哨兵/Guard(G)
![Guard](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/guard.png)

哨兵可以八方走吃1格。

### 骑士/Knight(N)
![Knight](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/knight.png)

骑士，简称骑，走法与国际象棋马完全相同。升级成卫士。

### 卫士/Centaur(E)
![Centaur](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/centaur.png)

卫士，简称卫。走法在国际象棋马基础上，增加八方1格。

### 角行/Bishop(B)
![Bishop](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/bishop.png)

角行，简称角。可以斜走任意距离，与将棋角行相同。升级成龙马。

### 龙马/Archer(H)
![Archer](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/archer.png)

龙马，简称马。除了斜走不限之外，还可以八方1格。与将棋龙马相同。

### 方行/Rook(R)
![Rook](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/rook.png)

方行，简称方。可以直走任意距离，与车和将棋的飞车相同。升级成龙王。

### 龙王/Tiger(T) 
![Tiger](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/tiger.png)

龙王，简称龙，除了直走不限之外，还可以八方1格。与将棋的龙王相同。

### 猊下/Cardinal(C)
![Cardinal](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/cardinal.png)

猊下，简称猊，走法兼具国际象棋象和马的走法。升级为圣下。

### 圣下/Rhino(I)
![Rhino](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/rhino.png)

圣下，简称圣，走法为国际象棋象、马、王的结合。

### 首相/Marshal(M)
![Marshal](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/marshal.png)

首相，简称首，走法兼具国际象棋车和马的走法。升级为名相。

### Myeong(名)/Ship(S)
![Ship](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/ship.png)

名相，简称名，走法为国际象棋车、马、王的结合。

### 奔王/Queen(Q)
![Queen](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/queen.png)

奔王，简称奔，走法与国际象棋后相同。不升级。

### 天马/Angel(A)
![Angel](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/angel.png)

天马，简称天，走法为国际象棋的后和马的结合。不升级。

### 阳、阴/King(K)
![King](https://github.com/pychess/pychess-variants/blob/master/static/images/MansindamGuide/king.png)

阳和阴，为双方的王，走法与国际象棋的王完全相同。也可以使用玉表示。

## 规则
**将军与将杀**
* 自己的王（阳、阴）被攻击时称为将军。被将军必须应将解除将军状态，若无法应将，则称为“将杀”。被将杀的一方落败。
* 王不可以进入被对方攻击的区域。

**基本规则**
* 白棋王称为阳，黑棋的王称为阴。
* 白棋先行动。
* 本棋没有虚手（pass）。
* 没有王车易位。
* 没有“50步不吃子作和”的规则。

**升级规则**
* 距离己方最远的3行称为敌阵。
* 棋子在进入敌阵、离开敌阵、或在敌阵内行动时立刻升级。
* 升级为强制的，符合条件不能不升级。
* 升级后的棋子被吃时返回原形态进入驹台。

**打入**
* 吃掉的对方棋子进入我方驹台。
* 可以在我方行动时将驹台棋子落在棋盘上，称为打入。
* 即使打入在敌阵，也不会马上升级。若想升级，必须走一次该棋子。
* 允许通过打入进行将军和将杀。

**步兵的打入**
* 可以通过打入步兵实行将杀。这和将棋不同。
* 不能在同一纵列出现两个或以上的己方步兵。
* 步兵不能打入在对方底线。

**困毙(Stalemate)**
没有合规行动的玩家输掉游戏，即困毙。

**触底(Campmate)**
将王移动到对方底线的玩家获胜。注意，不能将国王移动到受攻击的区域。

**三次重复局面**
同一个局面不能累计出现三次，即使不是连续循环，也不能三次同形，否则判负。

**胜败判定**
以下情况下，玩家落败：
* 王被将杀
* 对方王进入己方底线
* 玩家主动认输
* 玩家犯规
