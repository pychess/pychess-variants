# ![ASEAN](https://github.com/pychess/pychess-variants/blob/master/static/icons/ASEAN.svg) 亚细安象棋 | ASEAN Chess

![ASEAN Board](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/ASEAN.png?raw=true)

亚细安象棋(*ASEAN Chess*)（或称：现代泰国象棋、东盟象棋）是由东南亚国家联盟（东盟）象棋理事会在 2011 年 3 月基于泰国象棋制定的棋类游戏。ASEAN，全称为 Association of Southeast Asian Nations，即东南亚国家联盟，是由东南亚国家组成的经济体。亚细安象棋基于泰国象棋，并融合了 FIDE 标准的国际象棋棋子符号与部分规则。本文将列出与国际象棋不同的棋子走法与规则，与国际象棋相同的部分不再赘述。

## 规则简介

如上文所说，基本的规则与国际象棋十分相似。因此本文将重点展示亚细安象棋的特殊点。亚细安象棋也为擒王棋，即将死对方王获胜。部分棋子的走法来自泰国象棋，开局的棋子摆放也是如此，兵摆在第3行。但与泰国象棋不一样的是，白王和黑王处于同一列，即分别位于 e1 和 e8（国际象棋摆法）。

### 棋子走法

以下两个棋子的走法与国际象棋原本不同，尽管棋子的称呼并没有改变：

#### 后(Queen)

![Queen](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Duchess.png?raw=true)

后的走法为斜走1格。这个走法与泰国象棋的士相同。这也意味着它属于弱子。在仙灵棋子中，这个棋子也被叫做 Ferz(Fers)。

#### 象(Bishop)

![Bishop](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/ASEANBishop.png?raw=true)

象可以斜走一格或者向前一格，如同将棋的银将那样。这也和泰国象棋的象相同。

象是相对较强的棋子，可以用来为其他棋子生根，也可以在国王旁保护。

象比后强，但比马略弱，因为马可以轻易从对方王旁逃离，而象不行。

象的后退能力较差，所以最好旁边有棋子支援。在残局，让己方的王在对方的象后方会比在它前方好。

### 其他规则

*升变* - 兵在抵达第8行时升变，且可以任选升变为车、马、象、后之一。这个升变规则使用了国际象棋的规则，而非泰国象棋。

*逼和* - 无子可动为平局，如同国际象棋一样。

*子力不足* - 若双方的子力都不足以将杀对方王，则为平局。

*三次同形* - 若同一局面重复出现三次，则为平局。

*50 步不吃子* - 若双方连续 50 个回合没有吃子也没有移动过兵，则为平局。

*计步规则* - 当一方只剩孤王时，数对方的棋子。若对方没有兵，则自动开始孤王计步。孤王计步不能取消。
依照对手的子力，对手必须要在指定的步数内完成将杀，如果无法在规定步数完成将杀则和局。复杂的局面也遵循就低原则。

- 进攻方有至少一个车：16 回合
- 进攻方有至少一个象：44 回合
- 进攻方有至少一个马：64 回合
