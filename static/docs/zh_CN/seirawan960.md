# ![Seirawan960](https://github.com/pychess/pychess-variants/blob/master/static/icons/S960.svg) S-Chess 960

S-Chess 960 为 S-Chess 加入菲舍尔任意制的规则的变种，在游玩之前请先熟悉S-Chess的规则。

您需要在S-Chess的页面勾选“960模式”游玩本变种。

## 任意制规则

除了兵还在原位以外，其余棋子的初始布局将由电脑随机产生。随机的过程遵循下列原则：

- 黑白双方的棋子必须呈对称排列，如同原本的国际象棋的对称特征。
- 两枚象不可位于同色格，必须一黑一白。
- 两枚车不能在王的同一侧，必须一左一右（可以不相邻）。

包括国际象棋的基本布局在内，棋盘初始排列一共有4×4×6×5×4÷2=960种。

王车易位仍旧允许，即使王和车不在原本位置。进行的条件与原本规则基本一致：

- 王和车到达各自目的位置的路线不得有其他棋子阻隔。
- 进行易位的王和车必须都未动过。
- 王被将军时不能易位。
- 王移动时经过或到达的格子不能被对方攻击。
  不论王和车的初始位置在哪里，王车易位后二者所处位置是固定的——和国际象棋一样。
  当王与a线方向的车易位时，王移到c1(c8)，车到d1(d8)；当与h线方向的车易位时，王到g1(g8)，车到f1(f8)。

其余规则与 S-Chess 相同。

## 新棋子

### 鹰

![Hawk](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Hawk.png)

鹰的走法等于象+马。在走法上，它能单独对角格的王形成威胁。
鹰的价值一般认为比车高，但比大象和后低。

### 大象

![Elephant](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ElephantSeirawan.png)

大象的走法等同于车+马。一般认为它的价值比鹰高，但是跟后相等或是低一些。