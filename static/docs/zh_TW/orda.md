# ![Orda chess](https://github.com/pychess/pychess-variants/blob/master/static/icons/orda.svg) 可汗西征棋 | Orda

![Orda](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Orda.png)

![Legend](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/OrdaLegend.png)

可汗西征棋是一種國際象棋變體，於2020由Couch Tomato推出。這次創造的是一個非對稱的變體，雙方使用不同的棋種。靈感來自Chess with different armies 的 Ralph Betza，走的是草原民族風格。仿照蒙古軍隊的特色，主題是「馬」的移動。事實上，Orda是一種蒙古軍事結構，意為皇室，而這也在英語中產生了一個新詞：Hordeーー遊牧民族。為了描繪拔都西征，敵對的軍隊是歐洲王室。遊戲本身極其平衡，甚至比國際象棋更平衡，雙方的勝率接近一半。
 
## 規則
1.	設置如上所示。
2.	雙方擁有兵和王（可汗）
3.	王室方是先手。
4.	可汗不可王車易位。
5.	可汗的兵因為已經過了第二行不可前進兩格，相反王室的兵可以，而可以被吃過路兵。
6.	雙方的兵只可升變為後或禁衛
7.	雙方有另一個勝利條件：達陣ーー當一方的王能安全達到對方底線的時候，該方勝利。
8.	其他規則跟國際象棋一樣，包括逼和(無子可動算和棋)和長將和。

## 可汗方的棋子
有四個可汗特有的新棋種：2個槍騎，2個射騎，2個禁衛，1個穹盧。禁衛最強（王和馬的移動），而穹盧相當弱。Horde的王叫做可汗，有自己的符號，但本質上就是國王，差異就造型和主題而已。槍騎和射騎很特別，因為他們的動子和吃子方式不一樣（猶如西洋棋的兵一樣）。射騎以馬的走法移動，以主教的方式吃子;槍騎也是以馬的走法移動，而以車的走法吃子。禁衛吃子與移動沒有差別，走法是王+馬。穹盧則就如日本將棋的銀將般移動和吃子。

**可汗** 棋子	| **王室** 棋子	| 移動 | 吃掉移動
-- | -- | -- | --
穹盧 | 後 | “銀將” | “銀將”
射騎 | 象 | 馬 | 主教
禁衛 | 馬 | 馬+王 | 馬+王
槍騎 | 車 | 馬 | 車

下面是每個棋子的細節和圖示。綠色點代表移動走法，紅色點代表吃子走法，黃色點代表都可。
 
### 穹盧 | Yurt (Y)

![Yurt](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Yurt.png)
 
穹盧能移動到斜角方向或往正前方行走一格，猶如日本將其的銀將。穹盧一開始站在後的位置，不過不像後它很弱，即為輕子。但在他的小範圍之內，他的控制強度很高，因為沒有人想跟他換子。穹盧對蒙古人和突厥人來說是一種可移動的房屋，它們的重要性和小移動能力反應在這個棋子上。

### 禁衛 | Keshig (H)

![Kheshig](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Kheshig.png)

禁衛的移動融合馬和王的移動。禁衛一開始位於西洋棋「馬」的位置。不像馬，它是Horde的最強棋子。一般來說，因為它們比其他棋子重要，最好是不要輕易出動，因為開局的爭奪圍繞著小棋子，而如果禁衛因為被威脅而需要逃跑，你會因此而失先。禁衛本身是帝國的衛隊，所以在它們的守護下，王很難被將死。

### 射騎 | Horse Archer (A)

![Horse Archer](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Archer.png)

射騎是一枚分化棋子，移動猶如馬，吃子猶如主教。因為它能換方格的顏色而控制比主教更多的方格，所以比主教強一點。射騎是蒙古軍隊中一個核心主力，他們的速度和威力帶來兇猛的威脅。
 
### 槍騎  | Lancer (L)

![Lancer](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Lancer.png)

槍騎是一枚分化棋子，移動猶如馬，吃子猶如車。它的價值比車偏低，因為它的移動較慢，特別是在殘局。它應該還比射騎強一點。雖然槍騎比車弱，他們的機動性更強。槍騎是蒙古軍隊中另一個核心主力，做為重騎兵。
 
## 棋子價值

準確的棋子價值尚不清楚。以下是Fairy-stockfish所評估的。

王室方	| 價值 (前期 / 後期) | 可汗方 | 價值 (前期 / 後期)
-- | -- | -- | --
兵| 120 / 213	| 兵 | 120 / 213
後 | 2538 / 2682	| 穹盧 | 630 / 630
象 | 825 / 915	| 射騎	| 1100 / 1200
馬 | 781 / 854	| 禁衛 | 1800 / 1900
車 | 1276 / 1380	| 槍騎 | 1050 / 1250

下表更為簡明

王室方	| 價值 | 可汗方	| 價值
-- | -- | -- | --
兵 | 1	| 兵 | 1
後	| 9	| 穹盧 | 2
象 | 3 | 射騎 | 4
馬 | 3 | 禁衛 | 7
車 | 5 | 槍騎 | 4

## 戰略
遊戲推出尚早，大部分的資料來自電腦對弈。

可汗不能王車易位，所以一個基本的戰略是將可汗移動到g7。Fairy stockfish程式在56%的遊戲中走了Kf7。王室方的首選依序是d4，g3，b3。可汗方的主要弱點是它的棋子不能保持威脅，如果他受到攻擊而需要撤退，就失去它們原先的攻擊。國王方可利用這一點。

### 開局
以下分析來自Fairy-Stockfish的評估

白方開局	| 遊戲比例 | 白方勝率 % | 金方勝率 % | 金方應手
-- | -- | -- | -- | --
d4 | 38%	(47) | 45% | 38% | Kf7 ~= c5 >> Hb7
g3	| 24% (30)	| 33% | 43% | Kf7 >> d5
b3 | 14% (18) | 33% | 44% | Kf7 >> Lc7
e3 | 11% (14) | 50% | 50% | Kf7 ~50% of the time
d3 | 6% (8) | 25% | 25% | e5 ~=Kf7
Nf3 | 3% (4) | 25% | 50% | e5 always
e4 | 2% (3) | 33% | 67% | d5
c4 | 1% (1) | 100% | 0% | Kf7

四個最常見開局。“易位”代表金方很快把可汗移動到f7。小括弧代表其他選擇。

**本科易位 - 雙角攻擊** - 最常見
1. g3 Kf7
2. e4 Kg7
3. (Bd3 or Nf3) ...

![Benko's Castle](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/BenkoCastle.png)

*本科易位 2... Kg7*

**Stockfish 防禦 - 封閉變例**
1. d4 c5
2. dxc5 *bxc5*
3. c4 Kf7
4. (Nc3) ...

**Stockfish Defense - 開放變例**
1. d4 c5
2. dxc5 *dxc5*

**Stockfish Defense - 后翼推進**
1. d4 c5
2. *e3* cxd4
3. exd4 b5
4. b3 Kf7
5. c4

![Stockfish Defense Queenside Push](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/QueensidePush.png)

*Stockfish Defense - 后翼推進，走5. c4*
