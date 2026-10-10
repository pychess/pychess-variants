# ![Tori Shogi](https://github.com/pychess/pychess-variants/blob/master/static/icons/ToriShogi.svg) 禽將棋

|   |   |
--- | ---
![International Set](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriIntl.png) | ![Traditional Set](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriKanji.png)

禽將棋是十八世紀時，將棋九世名人大橋宗英發明的日本將棋變體，棋子皆以飛禽為名。現流行於歐美。

## 規則


* 7×7格的將棋盤，接近自己的二行橫列為自陣，反之，接近對手的二行橫列為敵陣。棋子進入敵陣就必須升變。
* 只有鷹與燕有升級棋，而且升級為強制性。
* 棋子共六類，若包含升級棋則八種，各方有十六顆棋子。
* 有打入與持駒規則。
* 燕的打入類同於步兵，同樣不可打步詰，但可將燕打入於已有己方燕一子的一路，但不可打入己方燕已有兩子以上的一路。
* 將對方的鵬將死和困斃為勝。
* 重復走子三次算和。

*計時* - 禽將棋使用byo-yomi計時，請參看「[術語](https://www.pychess.org/variants/terminology)」。



## 棋子

棋子造型預設為國際圖案版，每隻鳥的造型都代表其走法。

棋子走法分為兩種，一種為單格型，一種為Y型。



## 單格型

單格型的棋子一次只能走一格。

### 鵬

![Phoenix](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Phoenix.png)

等同於玉將，可向八方走一格。若被將死則輸掉遊戲。

### 燕

![Swallow](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Swallow.png)

可向前走一格。

升變後為**鵝**。

### 鷹

![Falcon](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Falcon.png)

可朝後方以外的方向走一格。由於可以同時攻擊多方，常用於將死。

升變後為**鵰**。

### 鶴

![Crane](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Crane.png)

可朝前方、後方三格走一步。

## ⅄型

![Upside-down Y pieces](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/UpsidedownYPieces.png)

**⅄**型棋子的走法類似倒過來的英文字母**Y**。

### 雉

![Pheasant](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pheasant.png)

可向前向跳二格(不會被前方棋子阻擋)，或向後斜向走一格。

### 鶉

|   |   |
--- | ---
![LeftQuail](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/LeftQuail.png) | ![RightQuail](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/RightQuail.png)

鶉依據配置於左右兩側而走法不同，棋上會標明左或右字。

左鶉可以向前或右後方自由行走，或向左後斜向走一格。

右鶉可以向前或左後方自由行走，或向右後斜向走一格。


## **Y**型

### 鵝與雕

![Promoted pieces](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PromotedPieces.png)


### 鵝

![Goose](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Goose.png)

為燕的升變，可向斜前方、後方跳兩格。由於步伐大，它所能到達的位置很少。

### 雕

![Eagle](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Eagle.png)

為鷹的升變。除保留原本走法外，可以向斜前與後方自由行走，或向斜後方走最多兩格。

這是最強的棋子。

## 記譜

禽將棋使用類似將棋的記譜法。在Pychess中，使用較通用的棋子縮寫。

### 座標

原點在白方(後手方)的最右方，也就是棋盤的左上角，先記行再記列，例如白方鵬在4-1。

### 棋子縮寫
棋子 | 英文  | Pychess縮寫
------------ | ------------- | -------------
鵬 | Ph | K
燕 | Sw | S
鷹 | Fa | F
鶴 | Cr | C
雉 | Ph | P 
左鶉 | LQ | L
右鶉 | RQ | R 
*鵝* | +Sw | +S
*雕* | +Fa | +F

### 記號

* 打入記作 \*。例如將燕打在3-3記作"S\*33"
* 升變會在後方加上「+」。如燕在 1-1 升變記作 S11+.
* 將和將死不特別標記。

## 策略

### 子力值值

下列是禽將棋軟體列出的子力價值([看這裡](https://happyclam.github.io/project/2019-01-03/torishogiapp))。

棋子 | 價值
------------ | -------------
燕 | 1 
雉 | 3
鶴 | 6
鶉 | 7
鷹 | 7
*鵝* | 2
*雕* | 16

除燕外，其他子持有在手中時價值會下降。(其實筆者實戰下來覺得鶴比鶉強。)

### 開局


基本上有四個合理的開局動作:

1+2：拿下對手的一隻燕子

3+4：對角移動你的一隻鶴到你的一隻雉前面

若直接將鶴往前一步，對方可以將燕打入在雉前，而你無法防守。

![弱點](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriWeakSpots.png)

這些點是弱點，請記住這些點並用鵬或鷹保護，這樣鶴就不必一直守住這些點！

推進鶉不是很有利（除非你想圍玉）;進燕讓對方吃，或特別動鵬也不好。

### 燕

燕子可以說是將棋的步兵，但也大不相同。可打入兩隻燕子到同行完全改變了策略。因此，燕子實際上是遊戲的靈魂，知道如何運用它們是學習 Tori Shogi 的關鍵部分之一。

以下是有關燕子的戰術:

* **雙燕** (兩隻燕疊在一起)非常強。因為這可以鎖住一條要道。缺點是你不太能夠動它，也不能再打入燕在那行。

* 由於燕往往會以令人眼花繚亂的速度在場上交換，**幾乎可以將它們視為貨幣**。手中有很多燕會讓你的攻擊有很大的靈活性。燕常作為棋子的前線，如果你有鶴或鷹可以生根的話，可以打入燕來推進你的前線。

* 使用燕子深入敵陣攻擊時請小心，如果進入對方下二線，**它會被強迫升變成鵝**！

(順序圖)![別做這種傻事!](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriGooseMistake.png)

### 邊緣攻擊

邊緣攻擊是發動攻擊的好方法。如上所述，你可以犧牲一隻燕子來推進自己的燕子，以奪取敵方的鶉(將燕打在鶉前方)。下面是成功進行邊緣攻擊時的順序圖(由左至右)：

![Edge Sequence!](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriEdgeSequence.png)

由於鶉無處可緅，因此它只能選擇換子: 把燕吃掉，再被對方的鶉吃。

![Edge Sequence!](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/ToriFailedEdgeAttack.png)

但這只有在鶉無處可動的情況下成立，如果鶉斜後方是空的，那它還是可以往那邊撤退。

因此這最好用來對付對方開局將鶴動到雉前的情況，因為鶴剛好會擋到鶉。


### 殘局


殘局是最重要的部分。你可以打出完美的開局和中局，但如果你無法將死對方，對手可以將你的失誤化為轉機！殘局的目標是俘虜足夠的棋子來將對手的鳳凰將死。你甚至不需要子力優勢，只需正確的運子即可。 由於將死的方式有很多，因此無法在說明中涵蓋不同的情況。不過，有一些重要的提示:


* **鶴和鷹**是將軍常用的子。
* **鵝**是非常弱的棋子，但常用來將殺，因為它是少數可以向前斜向攻擊的棋子之一。可以用它為鶴、雕生根，以將死對方鵬。
* **鷹**很容易將對方將死。不要將它們打在鵬旁邊將軍（很容易跑掉），而是將其打在*可以*下一回合將到鵬的位置旁邊。這樣就可以升變為雕，這是一個更強大的棋子。更好的是打入鷹時，也同時威脅到另一子，形成捉雙。
* **雉和鶉**也有向後斜向攻擊，這對於打破鵬的防御很重要。再者，鶉有無限的對角線，可以在你攻擊時用來保護你自己的鵬。請記住，當你全力將軍時會一直換子，若將死不成功，對手可以使用這些新棋子來發動攻擊，這就是鵪鶉非常有用的地方。
* 不能用燕子直接將死對方(將軍是可以的)。

## 讓子

以下是常見的讓子:

* 讓一子: 左鶉
* 讓一子: 鷹
* 讓二子: 鷹如左熟
* 讓三子: 鷹與雙鶉

<iframe width="560" height="315" src="https://www.youtube.com/embed/5f9QKK7cm20" frameborder="0" allowfullscreen></iframe>
