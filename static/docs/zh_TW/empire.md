# ![Empire chess](https://github.com/pychess/pychess-variants/blob/master/static/icons/empire.svg) 帝國棋 | Empire Chess

![Empire](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Empire.png)

是一種國際象棋變體，在2019-2020被Couch Tomato推出，非對稱性變體系列之四。強大的帝國(金方）聽說過以為在戰場上大權在握的女士，所以以為帝國國公提出了結婚。可惜，王國的國王反而娶了她。受辱的凱撒帶著軍隊出發去懲罰他們！

黃軍非常強大，所有的棋子（國公之外）比對方對應強。主題像可汗v王室的主題，不過用後的走法代替嗎的走法。另一個獨特的規則是王凱撒對峙（象棋也有），這可增加將死的可能性。遊戲是按照象棋程序極其平衡。雙方的勝率接近一半。 

## General Rules
1.	設置如上所示
2.	帝國（金方）是先手
3.      帝國的兵因為已經過了第二行不可前進兩格，相反王國的兵可以，而可以被吃過路兵。
4.	雙方的兵只可升變為後
5.	**王凱撒對峙** - 王，凱撒在同一路（性或列）且兩個棋子之間無任何棋子時，屬於違規走法。
6.	**Campmate** - 雙方有另一個生理條件，這個情況會出現在一個王能安全達到對方的底線。
7.	**Stalemate** - 沒有合法的棋步代表失敗（不是按照國際象棋的和平）
8.	**Repetition** - 三次重負同一局面代表失敗
8.	帝國不可王車易位
9.	其他規則，包括王國的移動和吃過路兵跟國際象棋一樣

## 帝國棋子

有五個新棋子屬於帝國所用，2卒，2塔，2贏，2主教，1國公。帝國所有的第一行棋子可安然移動如後，攻擊如他們王國的對應。國公是例外，只可攻擊如王。帝國的王名稱凱撒，有自己的表示不過跟對方的王實際上沒有區別。

下面是每個棋子的細節和圖示。綠色點代表走法，紅色點代表吃掉走法，黃色點代表都可

### 卒 | Soldier (S)
![Soldier](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/EmpireSoldier.png)

卒正是像棋升變過的兵，可左右或往前走一步，不可升變。

### 國公 | Duke (D)

![Duke](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Duke.png)

國公是後對應。他可移動如後，但只能攻擊為一個王。這不代表他太弱了，在殘局中他可跟一枚棋子的幫助把王將死，甚至凱撒（因為王凱撒對峙）。

### 塔 | (T)

![Siege Tower](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Tower.png)

塔有後的安然走法，為了攻擊有車的走法。算是一輛車加上象的安然走法。塔是帝國最強的棋子。

### 贏 (E)

![Eagle](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Eagle.png)

贏可如後移動，不過只可如馬攻擊。贏的價值跟馬差不多所以是帝國最差的棋子（兵和卒之外）。

### 主教 | Cardinal (C)

![Cardinal](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Cardinal.png)

主教可如後移動，不過只可如像攻擊。所以它算是一隻象加上一輛安然車的走法。因為不像象，他可換方格的顏色，他不比塔若多少，算是帝國威力排名第二。

## 棋子價值

不清，下文是Fairy-Stockfish所用。

王國棋子	| 價值 (早期 / 晚期) | 帝國棋子 | 價值 (早期 / 晚期)
-- | -- | -- | --
兵 | 120 / 213	| 兵 | 120 / 213
後 | 2538 / 2682	| 國公 | 1050 / 1150
象 | 825 / 915	| 主教	| 1225 / 1420
馬 | 781 / 854	| 贏 | 1000 / 1075
車 | 1276 / 1380	| 塔 | 1375 / 1480
 | | | 卒 | 200 / 270