# ![Shogi](https://github.com/pychess/pychess-variants/blob/master/static/icons/shogi.svg) 將棋

![Boards](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Boards.png)

*将棋*，しょうぎ (Shogi)，日本將棋，亦稱本將棋（本，基本之意），是一種盛行於日本的棋類遊戲。將棋的始祖目前沒有確實實證，目前被普遍認為可能是中國的寶應象棋或是從東南亞傳入的印度恰圖蘭卡。在日本，將棋跟圍棋並列為兩大最受歡迎的棋，而且都設有段位與職業賽頭銜。

## 為何要學將棋?

將棋玩起來非常類似真實的戰場，不像中國象棋開局即展開攻殺，它非常強調佈陣的概念，其多變足以讓你在每場開局築出不同的陣型。你也會看到進攻時將軍帶領著步兵逐漸推進、凌厲的飛車和角行在卒林間縱橫陷陣，王將在眾棋子的保獲下隱蔽到安全的堡壘。

同時將棋的最大特色ーー**打入**，你可以俘虜對手的棋子，並作為己方軍力隨時投入戰場!這使得進攻變得非常刺激，並因此讓將棋具有僅次於圍棋的複雜度。另外**升變**也是十分有趣，小的棋子只要成功衝入敵營，就可以晉升為將軍繼續作戰!

將棋總體行棋快速，殺機盡出，酐暢淋漓，想體會全新棋感的玩家不容錯過。

[更多資訊(英文)](https://chessbase.in/news/peter-heine-nielsen-on-shogi)

## 規則

與棋他象棋類遊遊一樣，玩家輪流下棋，先將死對方者獲勝。

你可以「俘虜」你吃掉的子並成為你的軍隊，隨時可以將他們**打入**場上任何位置上戰鬥。
(有一些子有特殊限制，將在下文中介紹)。

同時，棋子可以在成功進入敵陣後，**升變**成更強的戰力。


## 棋盤與棋子

將棋的棋盤是9列9行的棋盤。 靠近自己的3列是本陣，遠離自己而靠近對手的3列是敵陣。將棋的棋子呈鐘形，前端較尖。和中國象棋及西洋棋不同，將棋是以棋子前端的指的方向來區別所屬。將棋共有八種棋子（包含升級棋則有十四種），依據棋子重要性和強度棋子形狀有不同大小。每種棋子均有獨特的簡稱及走法，分述如下：

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

**所有輕子升變後走法都等同金將**

### 銀將

![Silvers](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Silvers.png)

![SilverDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Silver.png)

斜角方向或正前方行走一格。

升變後叫「成銀」

### 桂馬

![Knights](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Knights.png)

![KnightDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Knight.png)

只能走到前兩格的左方或右方。
桂馬是用跳的，所以中間的棋子並不阻礙桂馬前進。

升變後叫「成桂」

![Lances](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Lances.png)

![LanceeDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Lance.png)

向前走任意步數，不能跨過別的棋子。

升變後叫「成杏」

### 步兵

![Pawns](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawns.png)

![PawnDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawn.png)

步兵的走法為直行一格。

升變後叫「と金(成步)」

## 升變\|成駒

![PSilvers](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PSilvers.png)

![PKnights](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PKnights.png)

![PLances](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PLances.png)

![Tokins](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Tokins.png)


將棋的棋子設有升變制度。除了王將（玉將）、金將及已經升變的棋子外，棋盤上所有棋子均可升變，若棋子剛打入敵陣，則要多走一步才可升級。

當一枚可升級的棋子移進、移出、或者在敵陣（位於距離棋手最遠的三行）中移動時，棋手可以選擇把該棋子翻轉升級或保持原狀，但是如果該棋子不升級的話會沒有辦法再走（例如走到敵陣的底線的步兵）則該棋子會被迫升級。

大子(飛車、角行)升變後各自成為「龍王」、「龍馬」，其餘輕子升變後皆為金將。

||升變前|升變後
---|---|---
大子|飛車、角行|龍王、龍馬
輕子|其他棋子|金將


## 打入\|持ち駒

將棋最特別的是棋手可以花一手將己方吃掉的棋子放回棋盤成為己方棋子，稱為打入。當一枚已升級的棋子被吃時，它的升級會被取消，打入時用原先的棋種表示。

打入有以下限制：

* 剛打入的棋子即使落在敵陣亦不能馬上升級，**一定要在移動一步之後才可升變**。也可以選擇移動後不升變，若之後要再升變，需要再移動一次才行。
* 不能把棋子打入在一些不能再走的位置。例如步兵、香車都不能落在敵陣的底線；桂馬不能落在敵陣的底線及次底線。



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

## 記譜

我們使用西式記譜(類似西洋棋)的記譜法。

### 座標

以阿拉伯數字表示直行，英文字母表示橫列。原點落在王將方(後手)。然而，由於大部份的棋盤表示時是將玉將(先手)放在底部，因此原點會在最右上方。 例如，王將是落在 5a

有時不管行列都由阿拉伯數字表示，比方5e有時也記作55(第五列, 第五行)。

### 棋子

K = 王將

G = 金將

S = 銀將

N = 桂馬

L = 香車

R = 飛車

B = 角行

P = 步兵

+R or D = 龍王

+B or H = 龍馬

+S, +N, +L, +P 其餘升變的輕子

### 標記

* 打入會加上 \*符號, 所以打入在5e的兵會記 P*5e
* 升變會在其後加上+。例如一個在c1升變的兵會變 P1c+
* 如果你選擇不升變，則在後面加上「=」
* 將軍和將死並沒有特別標記

## 學習將棋的資源

[Hidetchi 的 YouTube 頻道](https://www.youtube.com/playlist?list=PL587865CAE59EB84A) 非常適合初學都與中等程度者。

***

## 策略

### 子力價值

與象棋不同，將棋中沒有標準的子力價值。 重要的是要記住，價值並沒有那麼重要，因為失去棋子不是永久性的，而位置更為重要。也就是說，有一個基本的子力價值體系，但職業棋手們也制定了更具體的價值量表:谷川式和佐藤式。如下所示:

棋子 | 基本價值 | 谷川 | 佐藤
------------ | ------------- | ------------- | -------------
P | 1 | 1 | 1
L | 3 | 5 | 6
N | 3 | 6 | 6
S | 5 | 8 | 10
G | 5 | 9 | 11
B | 7 | 13 | 17
R | 8 | 15 | 19
*H* |  | 15 | 20
*D* |  | 17 | 22
*+P* |  | 12 | 
*+L* |  | 10 | 
*+N* |  | 10 | 
*+S* |  | 9 | 

### 開局原則

一般來說，有兩種類型的開局方式：**居飛車**和**振飛車**。 在居飛車中飛車不會移動，因此主要攻擊棋盤的右側。在振飛車中，飛車移動到左側（通常是第 2 到第 5 行），將進攻棋盤的另一翼。

開局（稱為 *joseki*）主要分成這兩種，兩者差異極大。 

### 圍玉

圍玉是將王將動到角落並以其他棋子包圍以保護不受攻擊。通常需要多步才能完成。好的玩家需要了解各種圍玉的優缺點與變型。

圍玉的位置受開局為居飛車或振飛車影響。在居飛車開局中，王將在左圍玉。在振飛車中則在右。以下是三種最常見的圍玉:

### 矢倉

![Yagura](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Yagura.png)

矢倉圍是將棋中採用於相居飛車和相振飛車的圍玉。通常簡稱為矢倉，與美濃、穴熊並列為最具代表性的圍玉。居飛車雙方圍出矢倉後戰鬥的戰型被稱為相矢倉，也常被直接簡稱為矢倉。

此圍玉上方很強，但相反的，因為守護到78金將的棋子只有玉將1枚而已，面對橫向而來的攻擊則效果並不是很好。然而金銀3枚均有集中防守到68的位置，因此也不能說面對橫向而來的攻擊防守薄弱。反而是在第一行，因為沒有金銀防守而顯得有點薄弱，例如有利用桂香飛角一口氣攻破的雀刺戰法。

在矢倉圍玉的時候記住王將總是斜向移動以節省步數，且有許多種矢倉的變體，以應對對手不同的攻擊。以下是標準的24步矢倉圍:

1. ☗P-7f
2. ☖P-8d
3. ☗S-6h
4. ☖P-3d
5. ☗P-6f
6. ☖S-6b
7. ☗P-5f
8. ☖P-5d
9. ☗S-4h
10. ☖S-4b
11. ☗G4i-5h
12. ☖G-3b
13. ☗G-7h
14. ☖K-4a
15. ☗K-6i
16. ☖P-7d
17. ☗G5h-6g
18. ☖G-5b 
19. ☗S-7g
20. ☖S-3c
21. ☗B-7i
22. ☖B-3a
23. ☗P-3f
24. ☖P-4d

### 美濃

![Mino Castle](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Mino.png)

美濃是一個振飛車用來對付居飛車的圍玉，王將來到飛車的初始未置，金將走上&右，再上銀將，形成“金金銀” 。此圍玉在左側很強，但在上方較弱。

以下是一個美濃應對四間飛車的範例:

* P76
* B77 (保護 86/8f 格子) 
* P66 (防止換角)
* R68 (四間飛車)
* S78 
* K48 -> K38 -> K28
* S38 (上銀)
* G58 (上金)
* P16 (給王將逃跑空間)
* P46

自此之後可以開始換子，包括飛車，以發起進攻。

### 穴熊

![Anaguma](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Anaguma.png)

十分著名的圍玉方式，曾在棋界流行數十年。它的防守非常強大，只不過要浩費許多步數完成。

**優點**

金銀的連結密集因而非常堅固，再加上玉將在端離戰場十分遙遠，形成了「絕對不會被王手（別稱Z）」的形，對手也因此不得不避免在攻略穴熊的時候犧牲大量棋子。基於這些優點，穴熊方得以採取大膽捨飛車和角行等大子的作戰，被稱為「只有穴熊才能做到的攻擊」。

**缺點**

首先，圍玉所需的手數非常多，對手常常在完成之前就挑起戰事。再來，圍玉完成之後因為棋子集中在盤上一側，自陣有許多空隙容易被對手打入角行。雖然橫向的守備力很高，對上方或端攻較弱，在終盤還因為玉將躲在棋盤的角落，在被攻擊的時候無處可逃。最後，因為自陣空隙太多容易被對手入玉，這種時候就已完全沒有勝算。這種雖然圍玉沒有被破壞卻輸棋的狀況被稱為「姿燒穴熊(烤全熊)」。

此外，居飛車穴熊則多有遭對手角道直射的疑慮。許多居飛車穴熊的攻略法都包含角道的利用。

### 雙翼攻擊

雙方都使用居飛車並進車前兵進攻。需要注意的事，你必需要在對方的兵鞏到第5列前就上銀將保護角行。

## 讓子

為了讓相對較弱的棋手也有獲勝的機會，較強的棋手有時會讓子（日文稱為駒落）。在讓子的情況下，讓子方（即上手）必須在開局時永久除去自己一部分的棋子（即不能以任何方式將之放上棋盤）。不過，在國際賽上，讓子並不會因為兵力上的差異而為相對較弱的棋手造成明顯的優勢。現列如下：

名稱 | 讓子
--- | ---
左香落 | 除去左旁香車
角落 | 除去角行
飛落 | 除去飛車
飛香落 | 除去飛車與左旁香車
二枚落 | 除去飛車與角行
四枚落 | 除去飛車、角行與香車兩乘
六枚落| 除去飛車、角行、香車兩乘與桂馬兩匹
裸玉 | 除玉將外讓去所有子

<iframe width="560" height="315" src="https://www.youtube.com/embed/YH63AlxpXkg" frameborder="0" allowfullscreen></iframe>
