# ![Janggi](https://github.com/pychess/pychess-variants/blob/master/static/icons/Janggi.svg) 韓國將棋

![Boards](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Boards.png)

韓國將棋，韓文장기(“*chahng-ghee*”)，流行於朝鮮地區的象棋類遊戲，與中國象棋有相近發展的關係，在宋代以前由中國傳入高麗。


## 棋盤

韓國將棋的棋盤與中國象棋的棋盤大致相同，差別在於沒有河界。

### 棋盤佈置

韓國將棋主要有四種開局配置，在對局開始前，雙方各自都可以自由選擇其中一種配置。雖然楚方是先手，但選擇配置時，是由漢方先選擇，才輪到楚方。配置選好後就不得更改，並由楚方先行。配置的名稱主要是根據象的位置決定的。

1. 內象配置 - 兩隻象都在馬內側
2. 外象配置 - 兩隻象都在馬外側
3. 左象配置 - 左象在馬外側，右象在馬內側
4. 右象配置 - 右象在馬外側，左象在馬內側


## 棋子

韓國將棋的棋子是八角形，棋子大小不一。楚／漢為最大，表示它的重要性；然後為車、包、馬和象為第二大；士、卒／兵為最小。先手方為楚，以藍色或綠色代表，棋子名以草書漢字書寫；後手方為漢，以紅色代表，棋子名以正楷漢字書寫。棋子只有一面寫著棋子名，背面為空白，唯楚／漢例外兩面都寫著楚／漢，做為虛手時的用途，詳見後述。

### 將 (楚／漢)

![Kings](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Kings.png)

將 (楚／漢)的走法為在九宮內沿著直線或斜線走一步，不能離開九宮。此外將還有虛手、照面等規則，詳見後述。

**照面:** 當將主動移到和對方的將在同一直線上且彼此間無棋子時，為「**照面**」，目的是邀請對方結束對局，被照面的一方若沒立即移開或用棋子遮擋就必須接結束對局，以計分方式判定勝負。詳見下文「**規則**」。

**虛手:** 輪到走棋的一方可以把自己的將翻面，表示棄權不走棋，直接讓對方繼續下，此動作為「虛手」。除了被將軍時之外，任何時候都可以自由虛手，也沒有次數限制，若雙方都虛手則和局。韓國將棋沒有困斃或逼和，當一方無子可動時只是被迫虛手，對局仍舊繼續進行。

![King and advisor](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Palace.png)

### 士

![Advisors](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Advisors.png)

士的走法為在九宮內沿著**直線**或斜線走一步，不能離開九宮，即與將相同。

### 馬

 ![Horses](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Horses.png)
 
 ![Horse movement](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/HorseDiagram.png)
 
馬的走法為直一步再斜一步，即與中國象棋的馬相同，路徑上若有棋子同樣會被拐腳。以上圖為例，打勾處為馬能走到的地方，藍色處為拐腳點。

### 象

 ![Elephants](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Elephants.png)
 
 ![Elephant movement](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/ElephantDiagram.png)

與中國象棋的象走田不一樣，韓國將棋象是是走2x3的長方型，即先朝一個方向直走一步，再朝斜向走**兩步**。與馬一樣，只有是行走的路徑上有子就會被卡象眼。

### 車

 ![Chariots](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Chariots.png)
 
 ![Chariot movement](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/ChariotDiagram.png)

車的走法為沿著直線或**九宮的斜線**走任意距離。


### 包

![Cannons](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Cannons.png)

![Cannon movement](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/CannonDiagram.png)

與中國象棋的包不一樣，不能像車一般任意移動，無論是走子或吃子都需要跳過一子。且有限制包不能吃包，且也不能跳過包移動，無論自己的還是對手的均不可跳過，故韓國將棋沒有雙包殺。

當包在宮中時，還可以**沿著斜線**移動。亦即，當包在宮的一角，且中宮有子時，可斜跳至宮的另一角。

總而言之，包的走法為沿著直線或**九宮的斜線**跳過一個棋子走任意距離。

### 兵、卒

![Pawns](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Pawns.png)

![Pawn movement](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/PawnDiagram.png)

兵的走法為沿著直線或**九宮的斜線**前進一步，或橫著走一步。不能後退。

## 記譜

### 縮寫

K = 將

A = 士

E = 象

H = 馬

C = 包

R = 車

P = 兵

現今韓國將棋的記譜方式是先以座標定位要移動的棋子，再寫棋子名，最後再寫目標處的座標。座標均以楚方的視角為基準，以兩個阿拉伯數字表示；第一個數字表示橫線，由上至下依序為1至9，最底為0；第二個數字表示緃線，由左至右依序為1至9。如：76象53，記錄象從76的位置移動到53的位置。

在 Pychess 中，我們使用 (英文縮寫)(初位置)-(末位置)，吃子在後方加上x，若將軍則在後加上+，將死為#。

因此，左車前進三格記作 R01-71。


## 規則


1. 與國際象棋一樣，目標是將死對方。

2. 與大多數其他國際象棋變體不同，Janggi可以虛手(pass)。因此，將不可能被困斃。 **要在Pychess中虛手，請雙擊將軍，或單擊右側的pass按鈕。**

3. 當將主動移到和對方的將在同一直線上且彼此間無棋子時，為「**照面**」，目的是邀請對方結束對局，被照面的一方若沒立即移開或用棋子遮擋就必須接結束對局，以計分方式判定勝負。

棋子 | 計分
------------ | ------------- 
車 | 13
包 | 7
馬 | 5
象 | 3
士 | 3
卒 | 2

由於藍方(楚方)先行較有優勢，因此紅方(漢方)額外獲得1.5分

在可能「將軍」與「照面」同時發生，此時以「照面」為優先。

4. 重複動子與長將:
* 長將與重複動子三次者者判負。
* 50步未將死則以計分決定勝負。


## 與象棋不同之處

* 棋盤無河界
* 有多種配置雙方皆可各自選擇；開局時將位於九宮正中心
* 象直走一步再斜走兩步，無範圍限制，全盤都可走
* 將走九宮的直線和斜線 
* 包移動和吃子時都必須跳過棋子，且有限制不能跳過包亦不能吃包，可跳過一子走九宮的斜線
* 除馬、象外，其餘棋子在宮中的走法皆改變，將、車、包、兵可走斜、士可走直。



## 策略

### 基本概念

* 因為兵可以橫向移動，互相生根，所以兵形很重要，也因此通常不會建議進兵。


* 開局配置的重點是象該如何定位，這對開局有重大影響。外象能進到兩個卒之間。而內象則被卒擋住。
* 再者，象的位置決定了要打開哪一邊線的攻擊。 例如，在左象配時（並且對手象也是外象），可以將左邊的卒移走，打開車的開放線，然後用象去攻擊對方的包路卒。原因是現在對方的邊兵不能動，如果他的邊兵防守包路卒，他就會掉卒請注意，如果對手有兩個內象，則改為開相反的邊線。

![Activating the elephant and chariot](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/ActiveElephant.png)

<iframe width="560" height="315" src="https://www.youtube.com/embed/KDkF2dEt41g" frameborder="0" allowfullscreen></iframe>
