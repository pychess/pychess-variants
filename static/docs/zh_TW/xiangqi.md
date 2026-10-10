# ![Xiangqi](https://github.com/pychess/pychess-variants/blob/master/static/icons/xiangqi.svg) 象棋

![Boards](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Boards.png)


象棋是中國大陸、香港、台灣、馬來西亞、新加坡、越南、琉球地區所流行的傳統的2人對弈棋類遊戲。中國大陸為了進行區分稱此為中國象棋，將西方的「Chess」稱為國際象棋；台灣將「Chess」翻譯為「西洋棋」。據說從春秋戰國時期的「六博」演繹而來，也有一說是源自於古印度象棋恰圖蘭卡，傳入中國成寶應象棋，最後中國人在宋代改造成中國象棋。德國西洋棋歷史學家Peter Banaschak指出，唐代宰相牛僧孺的《玄怪錄》內沒有「炮」的寶應象棋是中國象棋的真正來源。

## 一、為何要玩中國象棋

中國象棋相較西洋棋雖需時較長，步數較多，但亦有其精采之處。中國象棋的開局更為緊湊，比起佈陣決定盤面的「戰略」，更需要考驗棋手計算能力的「戰術」。
它的局面豐富多樣，行棋輕快流暢，戰術凌厲，不像西洋棋常有子力擁塞的情況發生。相較西洋棋旨在發展空間，象棋更強調阻擋與搶占要道。學習象棋可以轉換另類思維，加上「炮」這個複雜而特別的棋子帶來許多別種棋所沒有的戰術，絕對可以增進你的棋感和敏銳度。
 

## 二、規則
所有的棋子都落在格子點上，且在縱橫的線上移動。開局由紅先行，黑其後，目的是將對方將死。與西洋棋不同的是，被困斃(stalemated無子可動)的一方算輸，另外長將和(perpetual checks)在象棋中也不成立。只要有一方連續動三次一樣的棋步該方就直接告負。


## 三、棋盤

象棋的棋盤由9條縱線和10條橫線相交而成。棋子放在各條線的相交點上，並在線上移動。棋盤中間的一行沒有畫上縱線，稱為「河界」，通常標上「楚河漢界」字樣，象徵楚漢相爭時的鴻溝。現行的中式記錄方法是：9條縱線，紅方從右到左用漢字「一」至「九」表示，黑方在自己的那一面從右到左用數字「1」至「9」表示。也就是說，紅方的縱線「一」就是黑方的縱線「9」，以此類推。第四條縱線（或第6條縱線）和第六條縱線（或第4條縱線）稱為「兩肋」、「兩肋線」，簡稱「肋」。棋盤上，劃有斜交叉線而構成「米」字形方格的地方，雙方各有一塊，稱為「九宮」，是將（帥）和士（仕）活動的區域。

## 四、棋子


### 將、帥

![Kings](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Kings.png)

只可在己方的九宮內直行或橫行，每次一步。

將、帥在同一路且兩個棋子之前無任何棋子時，屬於違規走法，此稱為「王不見王」或者「將帥對臉」。

被將死或無處可動時，該方告負。


![King and advisor movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/KingAdvisorDiagram.png)

### 士、仕

![Advisors](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Advisors.png)

只可在己方的九宮內斜行，每次一步。
行動力較低的棋子，用作將（帥）的內防禦之用。

### 象、相

 ![Elephants](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Elephants.png)
 
 ![Elephant movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/ElephantDiagram.png)

象行田：每一著斜走兩步（路線如「田」字的對角線）。

塞象眼（擠象眼）：當「田」字的中心有棋子，就不能走。

與士大致相同，用作將（帥）的外防禦之用。
### 馬、傌

 ![Horses](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Horses.png)
 
 ![Horse movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/HorseDiagram.png)

馬行日：先向一個方向直走兩步，再橫向走一步。

卡馬腳(蹩馬腿)：若前進兩步的方向有棋子卡在第一步的位置，就不能往那個方向走。若棋子是卡在第二步的位置則還是可以跳馬的。

最多能走八個方位（跟西洋棋的騎士一樣，但是西洋棋的騎士並無拐馬腳），有八面虎之稱，近距離殺傷力最強，同時又能憑著九彎十八拐的行進路線掩藏殺機，厲害無比。
隨著戰局的進行，或是棋手實力越高，更易發揮其威力。

### 車、俥

 ![Chariots](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Chariots.png)
 
 ![Chariot movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/ChariotDiagram.png)

只要無子阻隔，直行或橫行不限距離移動。

車為遠距離殺傷力的主力，無論何時都是第2關鍵的子。
有「三步不出車，棋已輸半盤」之稱。殘局有車在手，基本上不成問題；如果只有自己有車，常可穩操勝券。

### 包、炮

![Cannons](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Cannons.png)

![Cannon movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/CannonDiagram.png)

若不吃子，走法與車相同。

吃子時需與目標間有一個任何一方的棋子相隔（該子稱為炮架或砲台）。

遠距離殺傷力第二強，進攻時常與車和馬配合使用。
開局因為棋子（砲台）眾多，極為兇猛；殘局時因砲架難以取得，力量大幅下降，若能換到一炮（甚至一馬）會相當划算（西洋棋沒有炮）

### 卒、兵

![Pawns](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Pawns.png)

![Pawn movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/PawnDiagram.png)

過河前每次只可向前直行一步；過河後可左右或往前走一步。

永遠不能後退。

與西洋棋不同，即使打到底線也不能升變成其他棋子，但過河就能橫移，加強能力。
越到殘局威力越強，有時一兵（卒）可抵一馬或一炮，甚至一車。

## 五、勝負:

對一般棋局來說，只要一方被「困斃」或者被「將死」，又或者自動認輸，另一方即可得勝。困斃和將死定義如下：

行棋方無子可走，稱為困斃。
當一方的棋子攻擊範圍內包含了對方的將帥，準備在下一步吃掉它，稱為照將或將軍，簡稱將。
被將軍的一方必須應將，即移動將帥或別的棋子來化解。無法應將的情況稱為「被將死」。

首先超時的一方判負。

雙方在連續50步都沒有吃子時，直接判和。

長打（即長捉、長將、長殺）的一方判負。

## 六、記譜

《棋子表示方式》

棋子 | 英文代號
------------ | ------------- 
帥 將| King（K）
仕 士| Advisor（A）
相 象| Elephant(Ｅ)
傌 馬| Horse（H）
俥 車| Rook（R）
炮 包| Cannon（C）
兵 卒| Pawn（P）

在開始之前請先熟悉中式記譜法:https://zh.wikipedia.org/wiki/%E8%B1%A1%E6%A3%8B#%E4%B8%AD%E5%BC%8F%E8%A8%98%E8%AD%9C%E6%B3%95

PyChess在棋譜列使用傳統西式記譜法，若要匯出PGN檔案則是以中國象棋座標式記譜法表示。分述如下:

### 1. 西式記譜法:


**格式**: [棋子][原棋子所在行][前進或後退][移動後所在行]

直接將中式記法轉成英文字母和數字。各種棋子以英文代號代替。「平」用「=」代替；「進」、「退」和「前」、「後」分別用「+」、「-」取代。如果同一行有兩隻相同棋子，則前面的以+表示，後面的以-表示，其後不加棋子所在行。

例如:

* 馬2進3（H2+3）：黑方在第2條直線上的馬向前再轉左，走到第3條直線上

* 俥一進一（R1+1）：紅方在第一條直線上（即最右方）的俥向前一步

* 後砲平4（C-=4 / C-.4）：黑方在某條直線上有兩隻黑砲，將較近黑方自己的一隻移動到第4條直線

### 2. 座標式記譜法:

**格式**: [棋子][新座標]

仿照國際象棋，將棋盤上每一個格子點都建立座標。

以紅方為正面，把象棋棋盤的縱線從左到右依次記為

九|八|七|六|五|四|三|二|一
---|---|---|---|---|---|---|---|---
a|b|c|d|e|f|g|h|i

棋盤的橫線從下到上依次記為

9|
---|
8|
7|
6|
5|
4|
3|
2|
1|
0

因此帥一開始所在的座標是e0

**記譜方式**

「-」 移動，常省略

「+」 將軍

「#」 將殺

「x」 吃子

若遇到兩種以上的動子可能時(例如紅開局中炮)，則需另外再註明該子的行號(或列號)。

如開局炮二平五=Che2、炮八平五=Cbe2。

又如兩隻車都在肋道，一隻在d3，一隻在d2，則前車平九記為R3a3。


Ex:
1. Che2  (炮二平五) 　   Che7 (包８平５)
2. Cexe6+ (炮五進四) 　  Ade8 (士４進５)
3. Nhg2  (馬二進三) 　   Nhg7 (馬８進７)
4. Cbe2  (炮八平五) 　   Nbc7 (馬２進３)
5. Cee4  (前炮退二) 　   Rih9 (車９平８)


## 七、策略

### 子力價值

棋子 | 分數
------------ | ------------- 
帥 將| 無限
仕 士| 2
相 象| 2.5
傌 馬| 4
俥 車| 9
炮 包| 4.5
兵 卒| 1，過河後變 2

### 基本行棋原則

* 由於開局時子尚多，容易成為炮的炮架，所以炮在開局擁有相當強大的攻擊性。而到殘局時，由於子力變少炮容易成為孤炮，失去其戰鬥價值。反觀馬在開局時因為子力密集，易卡馬腳，因此成為需被保護的弱子，待殘局子力清空，馬的威力才真正發揮，能在近距離控制多個點位。 
* 用車控制住肋道或二、八路，並卡住相眼、馬腳，或是占住河界。
* 撐起士、相以完善防守，限制對方子力在自方區域的活動能力。
* 不要讓對方架住空頭炮(炮、將之間沒有棋子)。如此炮會將那條線完全封死。
* 開局讓子力生根(互相防守)，不要輕易讓馬脫根。

### 開局原則

對於業餘棋手來說，有70%紅方開局走中炮，直接瞄準中路，目標明確且方便右翼子力出動，行棋較為套路，不易出錯。



![Cannon opening](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/CannonOpening.png)

瞭解中炮局是對新手不錯的還擇，以下將簡介四種黑方可以做出的應對，稱為四大開局:



**1. 屏風馬**

![Screen horses](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Screen_Horses.png)

屏風馬是指在同一個棋局中，一位象棋棋手同時走馬二進三和馬八進七。

屏風馬是一個防守穩健的佈局，可讓士象守護中宮、雙馬保護中兵。由於能有效果保護中兵，對將的保護很有利。

雙馬前進後 (即，馬二進三和馬八進七)，棋手一般會選擇卒七進一或卒三進一，這樣可讓單馬、甚至雙馬更為靈活，可立即出擊。

可以有效果對抗對方紅棋的當頭炮開局，也可抗衡紅棋比較積極進攻的中炮盤頭馬。

**2. 反宮馬**

將炮動到士角使其更加靈活，可以直接牽制紅方左翼上馬八進七，往後也可發動肋道的攻勢。

反宮馬最明顯的弱點是總有一邊馬沒有根 (沒有另一隻棋子保護這隻馬)。

一旦沒有根的反宮馬被對方紅棋的車壓制，或被紅炮瞄準攻擊的時候，黑棋的防守會變得非常被動，造成難以抽出機會去反擊對手。

![Fan Gong Ma](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Fan_Gong_Ma.png)

**3. 順手炮**

順炮 (順手炮) 開局，是對炮局中的中炮局的一個主流開局佈局。順炮局的佈局過程是後手方 (黑棋) 跟先手方走的是同一邊的中炮開局。

在中國象棋中，能搶先是一個非常關鍵的贏棋因素。順炮局這個開局方式其實沒有大問題。相對於中炮對各種馬局的開局方式，使用順炮開局的後手方子力調動一般比較快，在一定程度上可跟先手方 (紅棋) 拼搶先手。

後手方使用到順炮開局的情況，意味著在棋局中的雙方都屬於偏向進攻型的棋手，雙方在子力調動上都需要非常快速。先手方多數會走順車，後手方可走橫車，後手方在形勢上還是能保持著均勢。

**4. 對炮局**

與順手炮相似，只是改走與對手反向的炮，

**5.三步虎**

![Three Step Tiger](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Three_Step_Tiger.png)

黑方上馬之後快速平邊炮亮車，是較激進的走法。

### 其他先手開局
紅方除了中炮局外，尚有其他開局，稱為緩攻類開局，並不會如中炮對黑方直接造成威脅。

**1. 仙人指路** - 指先手走兵三進一或兵七進一，先開馬前兵，意在等待後手方表露意圖後再作打算，屬緩攻型佈局。因為它彈性大，可佈成各類陣勢，也非常常見。
以兵七進一為例，後手方一般的應著為：
* 砲８平５，稱為還中炮，不理會挺兵而逕自攻擊對方中兵，屬於攻擊型的應著。
* 砲２平３，稱為卒底炮，又稱一聲雷，針對挺起的兵進行攻擊，同樣屬於攻擊型的應著。
* 卒7進１，演變成對兵局，後手方針鋒相對，一樣不表示意圖，而且同樣彈性較大，之後能演變成多種不同類型的佈局,同樣亦是較穩健的應著。
* 象３進５，演變成仙人指路對飛象，是甚為穩健的下法。
* 馬８進７，演變成挺兵對起馬

**2. 飛象局** - 飛象護住中路，為高手常用的下法，比起一來一往的激烈對攻，此局較為隱晦含蓄，歛藏殺機，較不入套路之流。

**3. 起馬局** - 走馬二進三或馬八進七，是AI最為推薦，分數最高的開局

紅方尚有「士角炮」、「過宮炮」等開局。


<iframe width="560" height="315" src="https://www.youtube.com/embed/5EDG5RP8OZ8" frameborder="0" allowfullscreen></iframe>

<iframe width="560" height="315" src="https://www.youtube.com/embed/boT1qyDA5RA" frameborder="0" allowfullscreen></iframe>
