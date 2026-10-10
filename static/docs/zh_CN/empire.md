# ![Empire chess](https://github.com/pychess/pychess-variants/blob/master/static/icons/empire.svg) 帝王象棋 | Empire Chess

![Empire](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Empire.png)

帝王象棋(Empire Chess)是一种国际象棋变体，在 2019-2020 由 Couch Tomato 推出，非对称棋组变体系列的第三款（第四个发布于 Pyches s的，因为代码问题拖延了一段时间）。游戏的背景设定在一个王国（黑）与一个强大的帝国（金）之间。帝国的皇帝听说过有一位在战场上统领千军万马的女士，并且有意让她与帝国公爵结婚。然而，王国的国王捷足先登娶走了她。帝国的皇帝感到受到了莫大羞辱，于是起兵亲征，要去给王国军一个教训！

帝国军非常强大，所有的棋子（公爵除外）都比对方相应棋子要强，因为大部分子都可以按后的走法移动，区别在于吃子方法不同。如果您玩过可汗西征棋，您可能会发现这两个棋比较类似，只是将马的走法换为皇后的走法。
另一个特别的规则是照面（自中国象棋中引入），这可增加将死的可能性。
游戏经程序评测，非常平衡。双方的胜率接近五五开。 

## 基本规则

1. 棋盘布局如上所示
2. 帝国方（金）先手
3. 帝国方的兵因为位于第三行，因此它们不能挺进两格。相反王国的兵可以挺进两格。因为上述限制，王国方不能吃帝国方过路兵（因没有吃过路兵的条件），而帝国方可以吃王国方的过路兵。
4. 双方的兵只可升变为后
5. **照面(Faceoff)** - 双方的王不能在横向或纵向照面，即不能处于同一行或同一列，且两个棋子之间无任何棋子，如同中国象棋一样。黑方王车易位时，若经过的格子或到达的格子会与对方王照面，则不允许进行。
6. **触底获胜(Campmate)** - 双方的另一个胜利条件，将王安全移动到对方底线也算获胜。
7. **困毙(Stalemate)** - 若一方在未被将军的情况下没有合法的行动，则该方失败（与国际象棋的逼和不同）
8. **重复局面(Repetiiton)** - 若一方累计三次重复出现同一局面，则这一方落败。（多见于长将）
9. 帝国方不可王车易位
10. 其他规则，包括王国方棋子的移动和吃过路兵，均与国际象棋一样

## 帝王方棋子

帝国方有五个新兵种，卒 2 枚，攻城塔 2 枚，战鹰 2 枚，红衣主教 2 枚，公爵 1 枚。帝国方所有的大子都可以按后的走法移动，吃法与原本王国的对应棋子相同。唯一的例外是公爵，它只可按王的走法吃子。帝国的王叫做帝王(Kaiser)，棋子外形和称呼虽然都不同，但走法和王完全一样。

下面是每个棋子的细节和图示。绿色点代表仅可移动，红色点代表仅可吃子，黄色点代表走吃皆可。

### 卒 | Soldier(S)

![Soldier](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/EmpireSoldier.png)

卒的走法和中国象棋过河兵一样，可左右或往前走一步。注意卒不可升变。

### 公爵 | Duke(D)

![Duke](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Duke.png)

公爵是王国方后的对应棋子。他走棋是后的步法，但吃子只能按王的步法。虽然他确实是帝国方重子里较弱的，但是在残局中他可与任意一枚棋子协同实行将杀，甚至是借助帝王（注意照面规则）。

### 攻城塔 | Siege Tower(T)

![Siege Tower](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Tower.png)

攻城塔的走子是后的步法，吃子则是车的步法。也可以认为是在车的基础上，增加了按象的步法只走不吃的能力。攻城塔是帝国最强的棋子。

### 战鹰 | Eagle(E)

![Eagle](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Eagle.png)

战鹰的走子是后的步法，吃子只能按马的步法。战鹰的价值跟马差不多，是帝国最弱的重子。

### 红衣主教 | Cardinal(C)

![Cardinal](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Cardinal.png)

红衣主教走子是后的步法，吃子只能按象的步法。它也可以认为是在国际象棋象的基础上，增加了按车的步法只走不吃的走法。与象不同，他可以切换方格颜色，因此价值仅略微弱于攻城塔。是帝国威力第二大的棋子。

## 棋子价值

具体价值尚无定论，下文是 Fairy-Stockfish 所用。

| 王国棋子 | 价值 (早期 / 晚期) | 帝国棋子 | 价值 (早期 / 晚期) |
| ---- | ------------ | ---- | ------------ |
| 兵    | 120 / 213    | 兵    | 120 / 213    |
| 后    | 2538 / 2682  | 公爵   | 1050 / 1150  |
| 象    | 825 / 915    | 主教   | 1225 / 1420  |
| 马    | 781 / 854    | 战鹰   | 1000 / 1075  |
| 车    | 1276 / 1380  | 攻城塔  | 1375 / 1480  |
|      |              | 卒    | 200 / 270    |