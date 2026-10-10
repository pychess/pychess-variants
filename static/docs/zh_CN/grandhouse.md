# ![Grandhouse](https://github.com/pychess/pychess-variants/blob/master/static/icons/Grandhouse.svg) 双狂大象棋

双狂大象棋的规则就如双狂象棋与大型国际象棋，只是略有修改。

## 双狂象棋规则

除使用基本的国际象棋规则外，另外加上简化的日本将棋持驹（打入）规则。记谱方式同一般，但棋子打入时用@符号表示。每回玩家可选择移动自己的棋子，或将俘虏来的棋子放置没有被占据的格子上。将棋子放回时必须遵循下列原则：

* 允许打步诘(即打入兵将死对方，这与日本将棋不同)。
* 兵不能打在己方底线或**8 - 10 列**!
* 升变后的兵被吃掉后会还原成兵打入场上。
* 打入在己方第三列(就是兵初始所在列)的兵允许第一步动二格。

**与双狂象棋不同之处**: *兵不能打在8 - 10 列(对方前三列)*

## 大型国际象棋规则

以下简述大型国际象棋的规则:

使用10×10的棋盘。棋子布置如上图。
十枚兵摆满在第三行。
第二行的棋子，白方左右两侧a2和j2空白，中间八枚棋子依次为：马、象、后、王、元帅、大主教、象、马。黑方与白方每一列相对摆放，如同国际象棋。
两枚车分别位于第一行的左右两角格。

除了新增棋子和初始配置不同外，还有以下规则:

* 没有王车易位。
* 兵只能升变成己方被吃的棋子。
* 兵在到达第8、第9行时即可升变，到第10行时则**必须**升变。
  若无法升变（没有被吃的棋子或者被吃的棋子已经用于其他兵升变），则该兵不可前进到第10行。 
  但在这种情况下，兵仍然可以将军。

其余规则与正统象棋同。

## 新棋子

### 大主教

### 大主教 | Archbishop

![Archbishop](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Princesses.png)

以上为本站大主教可能出现的各种棋子造型。其中老鹰为S-chess所用。

![Archbishop moves](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Archbishop.png)

尽管在很多资料中这个棋子的称呼各有不同（有Princess，有Cardinal），但是在本站还是叫它大主教。大主教是一个复合棋子，它可以看成是马+象。
它棋子的造型一般如图，把象的下半部分拼在马下面。本站有其他的造型可以选择，不同的棋也有不同的造型。
在走法上，它能单独对角格的王形成威胁。大主教的价值略低于首相和后。

### 首相 | Chancellor

![Chancellor](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Empresses.png)

以上是本站中首相可能会用的几种棋子造型。大象为S-chess所用。

![Chancellor moves](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Chancellor.png)

首相是一个复合棋子，它可以看成车+马。如同大主教，它的棋子造型就是马头拼上车的下半部分。其他的棋有不同的造型，本站也可以切换棋子造型。
首相的价值一般认为比大主教略高一些，但和后相等或略小。

## 策略

请不要以国际象棋的固有思维，一开始就急于出动子力，在大型国际象棋中，有时重复的动同一子反而会给对方造成更多威胁。
子力价值与传统国际象棋基本相同，由于打入的规则你可以不断地换子、弃子打入，并擅用骑士和兵的捉双。你也可以打入子在国王旁边加强防守。