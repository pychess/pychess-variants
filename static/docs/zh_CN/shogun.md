# ![Shogun](https://github.com/pychess/pychess-variants/blob/master/static/icons/shogun.svg) 幕府象棋 | Shogun Chess

![Shogun](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ShogunPromotions3.png)

幕府象棋（Shogun Chess）是在2019-2020年由Couch Tomato推出的棋类游戏。本棋虽然也是将国际象棋与将棋的打入作了融合，但是最初的设想是将常见的复合棋子（大主教和首相）以一种完全不同的方式引入到国际象棋中。首先，棋盘不扩大，而是使用8×8棋盘，以免强子弱子的价值差距过大，而又不像S-Chess那样杂乱；然后，将升变扩充到全子升变，扩大了升变区，使得弱子有更多的机会强化。最后，引入了将棋的打入规则，使得棋更具有攻击性，也能在防御中抵消升变的威胁。本棋将兵、马的升变也做了平衡，削弱了皇后，增加主题特征。

本棋原名为“General's Chess”，因为最初兵升变为将军（现在则是马的升变）。然而，因为引入了将棋的打入，日语的“将軍”（しょうぐん，Shogun）似乎更为合适。中文则翻译为“幕府象棋”。

## 规则

1. 开局布置跟国际象棋一样
2. 新棋子的走法和升变如上图，它们的走法会在下文解释。注意的是升变的棋子颜色不一样（白方蓝色，黑方黄色）。此外，王后开始为已升变状态，因为它有一个升变前的形态（士）。在本棋中，我们把后、首相、大主教、将军称为重子，其余的称为轻子。关于这一点，在下文有说明。
3. 升变：位于距离棋手最远的三行称为敌阵。当一枚可升级的棋子移进，移出，或者在敌阵中移动时，棋手可以选择把该棋子翻转升级或保持原装。每个起步者（或者打入者）棋子（除了王和王后外）可升级。然而，每一种重子每方最多只能拥有一枚。这意味着您拥有一枚大主教，他剩余的象不可升变，直到已有的大主教被吃掉。后、首相和将军也是如此，但兵升变为兵长不受此限制。
4. 打入：如同将棋和双狂象棋一样，吃掉的棋子俘获到自己手上成为持驹，您可以花一手将您的持驹作为己方棋子放回棋盘。当一枚已升级的棋子被吃时，它返回升变前形态（后就变回士）。仅可以打入在前五行，也就是说不可打入到对方的敌阵。注意，步兵可以第一行打入。

其他规则说明:

* 车被打入之后不可做王车易位。
* 打入在第一行的兵不能走两格，在第二行前进两格
* 可以吃过路兵，但是这么做不可升变。

## 棋子

### 大主教 | Archbishop (A)

![Archbishop](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ArchbishopShogun.png)

大主教是一种常见的仙灵棋子，即象+马。在本棋中，它由象升变而来，走法在象的基础上增加马的走法。因此，它能单独对角格的王形成威胁。

### 首相 | Mortar (M)

![Mortar](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Mortar.png)

Mortar 直译为迫击炮，但本棋子与炮毫无关系，所以使用了通用称呼。
首相也是常见的仙灵棋子，即车+马。在本棋中，它由车升变而来，在车的基础上增加马的走法。

### 将军 | General (G)

![General](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/General.png)

将军由马升变而来，它的走法是在马的基础上增加王的走法。

### 兵长 | Captain (C)

![Captain](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Captain.png)

兵长由兵升级而来，走法跟王一样。兵长不是重子，升变不受数量限制。

### 士 | Duchess | Ferz (F)

![Duchess](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Duchess.png)

士可以升变到王后。一方的后被吃掉之后必须以士的形态进入持驹。士可以斜走一格。别忘记，后是重子，所以如果您已经有后了，士不能在升变为后（在幕府象棋中没有一夫多妻制——译者注：原文如此）。

Duchess 的本意为女公爵，使用士称呼的原因是避免不必要的疑惑。

## 战略

游戏推出时间不长，没有太多的战略！
重要是防御你的自阵，尤其是3线，阻止对方升变。战略跟 Crazyhouse 不一样，因为打入区域的不同，打入通常不会作为进攻的战术，而是防御的战术。无论怎样，王的安全有关键的重要性。在幕府象棋的进攻中，应当观察对方防御的弱点，尤其是可打入的安全位置。因为兵能打入到第一行，双方的防御会更加坚固。因此玩家们不断尝试去进行棋子交换，激活自己的棋子而同时限制对方，攻击弱点。