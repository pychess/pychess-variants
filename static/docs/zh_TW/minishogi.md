
# ![Minishogi](https://github.com/pychess/pychess-variants/blob/master/static/icons/minishogi.svg) 迷你將棋

![Minishogi](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Minishogi.png)

迷你將棋即是縮小版的日本將棋，使用5x5的棋盤，於1970由琉球的楠本重信發明。

## 規則

由於此變體基於日本將棋，如果不熟悉將棋規則請先查看[日本將棋](https://www.pychess.org/variants/shogi)。

初使配置如上，沒有桂馬與香車，且只有一個步兵。

唯一與標準將棋不同規則是，只有到達最後一列才能升變。

***

## 簡附日本將棋的規則(刪去桂馬、香車)：

你可以「俘虜」你吃掉的子並成為你的軍隊，隨時可以將他們**打入**場上任何位置上戰鬥。
(有一些子有特殊限制，將在下文中介紹)。

同時，棋子可以在成功進入敵陣後，**升變**成更強的戰力。

## 棋盤與棋子

### 玉將、王將

![BlackKings](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/BlackKings.png)

![WhiteKings](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/WhiteKings.png)

![KingDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/King.png)

先手方為玉將。後手為王將。

往八個方向行走，但只能走一格，猶如西洋棋的「王」。將死對方王將者獲勝。

### 飛車

![Rooks](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Rooks.png)

![RookDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Rook.png)

飛車的移動就如象棋的車，或西洋棋的城堡，可以任意前行或橫行。它是將棋最強的未升變棋子。

其升變後為龍王。

### 龍王

![Dragons](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Dragons.png)

![DragonDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Dragon.png)

龍王是升變後的飛車，走法如本來的飛車加上西洋棋「王」的走法。它是場上最強的棋子。

### 角行

![Bishops](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Bishops.png)

![BishopDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Bishop.png)

象行的移動方式如西洋棋的主教，朝斜向移動任意步數。由於它所能控制的格子是場上總格子數的半，因此較飛車弱，為將棋第二強的未升變棋子。

其升變後為龍馬。

### 龍馬

![Horses](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Horses.png)

![HorseDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Horse.png)

龍馬是升變後的角行，除了原本角行的走法，還加上西洋棋「王」的移動，因此可以到達場上任意一個格子，為場上第二強的棋子。

### 金將

![Golds](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Golds.png)

![GoldDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Gold.png)

向前、左前、右前、左、右或後行走一格，猶如中文「甲」字。
金將無法升變。


### 銀將

![Silvers](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Silvers.png)

![SilverDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Silver.png)

斜角方向或正前方行走一格。

升變後叫「成銀」，走法同金將。

### 步兵

![Pawns](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawns.png)

![PawnDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawn.png)

步兵的走法為直行一格。

升變後叫「と金(成步)」，走法同金將。

## 升變\|成駒

![PSilvers](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PSilvers.png)

![PKnights](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PKnights.png)

![PLances](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PLances.png)

![Tokins](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Tokins.png)


將棋的棋子設有升變制度。除了王將（玉將）、金將及已經升變的棋子外，棋盤上所有棋子均可升變，若棋子剛打入敵陣，則要多走一步才可升級。

當一枚可升級的棋子移進、移出、或者在敵陣（在迷你將棋中是最後一行）中移動時，棋手可以選擇把該棋子翻轉升級或保持原狀，但是如果該棋子不升級的話會沒有辦法再走（例如走到敵陣的底線的步兵）則該棋子會被迫升級。

大子(飛車、角行)升變後各自成為「龍王」、「龍馬」，其餘輕子升變後皆為金將。

## 打入\|持ち駒

將棋最特別的是棋手可以花一手將己方吃掉的棋子放回棋盤成為己方棋子，稱為打入。當一枚已升級的棋子被吃時，它的升級會被取消，打入時用原先的棋種表示。

打入有以下限制：

* 剛打入的棋子即使落在敵陣亦不能馬上升級，**一定要在移動一步之後才可升變**。也可以選擇移動後不升變，若之後要再升變，需要再移動一次才行。
* 不能把棋子打入在一些不能再走的位置。例如步兵不能落在敵陣的底線。



對步兵的打入有一些額外規則:
1) **二步一筋**: 若某行已有無方未升變步兵，則不能在該行再打入步兵。 (若該行兵已升變則不在此限)。「二步一筋」在日本的將棋職業賽中為最常見犯規，自一九七七年迄今，在日本的將棋職業賽中已有44次「二步一筋」的記錄。 
2) **打步詰**: 指用打入步兵的方式使對方王將無法脫逃，若觸犯則直接判輸局。打步詰必須要「打」、「步」、「詰」三個條件同時成立才算數，所以以下的三種情形皆沒犯規：

	* 走步詰：移動步兵，將死對方王將
	* 打其他棋子詰：打入非步兵的棋子，將死對方王將
	* 打步將：打入步兵，將軍對方王將但沒將死

## 其他規則



**長將** - 將棋容許連將但是不能重複同樣的手法長照（長將），若雙方重複循環同樣的方式照將、應照達四次時，則照將方違規，判負。 

**千日手** - 雙方重複循環同樣的著法，使得局面沒有進一步變化達四次時，則視為和局。

***


## 策略

由於棋盤較小，飛車與角行相對就不像將棋中那麼強。但在它們升變之後，依舊有很大的主宰力。
