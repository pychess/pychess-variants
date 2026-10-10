# ![Chak](https://github.com/pychess/pychess-variants/blob/master/static/icons/Chak.svg) 馬雅象棋 | Chak

![Chak](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/Chak.png)

## 背景

國際象棋遊戲最早起源於印度，爾後演變為波斯象棋，傳播到歐洲並發展出現代的形式。東亞也有豐富的象棋變體，融合了各地的傳統文化。世界各地的許多文化都有自己的象棋，然而，美洲原住民呢？ 中美洲曾經擁有偉大的帝國。如果他們也有自己的國際象棋呢？

馬雅象棋 Chak 是Couch Tomato 於 2021 年設計的遊戲，設計理念是使用象棋常見的元素：國王、車、騎士和兵，並引入中美洲的馬雅文化。例如，對於馬雅和其他中美洲文化來說，社會的組成圍繞著祭祀儀式；因此，神靈祭祀和神殿成了遊戲的關鍵精神。

Chak 這個詞來自馬雅神祇中雨神 Chaac，它掌管雨水、雷電與戰爭。剛好此遊戲的戰場是設在河邊。而馬雅語中相似的兩個詞「Chuc-ah」(俘虜) 和「Ch’ak」(斬首)剛好成為了 Chak 中的 「登壇」和「將死」。

## 基本規則

分為白綠兩方，白方先行。

### 棋盤

馬雅象棋的棋盤為 9x9 :

![Chak](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/ChakBoard.png)

其中有三個特殊的區域:

-**河界**, 兩方的界限，王和兵過河後可升變，然而，**王與兵過河後不能再回去己方陣地**，只能待再對方一側。

-**神殿**, 一個象徵性的 3x3 位置，中心為**祭壇**，並無特殊功能。然而從戰略上講，神殿非常重要，因為有許多將死與登壇的戰術都在神殿發生。

-**祭壇**, 神殿的中心，將己方國王動至對方祭壇即獲勝。

### 勝負條件

有三種勝利條件:

**將死** - 對方無法防止將軍。

**困斃** - 讓對方的王無處可動。

**登壇** - 將己方王動到對方祭壇，且不能被將軍。


以下情形為和棋:

**重復動子** - 同一個局面連續重復三次。

**50步無吃子** - 如果五十步都沒有棋子被吃則和棋。


## 棋子

### 國王 (K)

![King](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/ChakKing.png)

國王 (*Ajaw*, 讀作 「Dachau」) 走法就如就如西洋棋的國王，朝八方走一格。

國王過河後可升變為「神王」

### 神王 (D)

![Divine King](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/DivineKing.png)

神王可向任何方向移動最多*兩個*方格，也可以通過被對方棋子威脅的方格（換句話說，它不像西棋的王車易位，王的路徑上不能有棋子攻擊）。 請記住，國王一互升變，便不能退到河界後！由於其攻擊範圍，神王可以直接將未變的國王將死。

請注意，神王的符號「D」是為了與國王「K」區別。

### 美洲豹 (J)

![Jaguar](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/Jaguar.png)


美洲豹的移動融合西洋棋的騎士和國王，即 

1. 先朝一個方向走兩格，再垂直走一格，就如L型。

或者:

2. 朝八方移動一步。 

這種走法在其他變體中常被稱為「半人馬」，與幕府將棋中的將軍和可汗西征棋中的禁衛相同。

由於能同時打擊多個方位，美洲豹是馬雅象棋中最強的棋子。

### 羽神(Q)

![Quetzal range](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/QuetzalRange.png)

羽神的走法很特別，它類似於國際象棋皇后，因為它可以在任何方向（垂直或對角）移動任意格...... *但是*，它需要先跳過中間的棋子。對於熟悉韓國將棋的人來說，這與韓國將棋的「包」類似，但增加了對角線移動，且沒有「不能跳過對方的羽神」的限制。

羽神是第二強的棋子，但就如象棋的炮，在殘局會因為沒有炮架而失去價值。

![Quetzal example](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/QuetzalLegal.png)

*範例*: 上圖中，羽神可以移動到以上格子(紅色代表吃子)。

### 祭司 (S)

![Shaman](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/Shaman.png)

祭司朝前方及後方三格移動一步。

由於步伐小，它是最弱的子之一，通常用來防守。

該棋子的形狀是用來提示它的走法。

### 禿鷹 (V)

![Vulture](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/Vulture.png)

禿鷹的走法就如中國象棋的馬，只是沒有拐馬腳的規則(或如西洋棋的騎士)，先朝一個方向走兩格，再垂直走一格，就如L型。

### 蚺蛇 (R)

![Serpent](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/Serpent.png)

蚺蛇就如中國象棋的車，可朝一個方向任意直行。

它是第三強的子，僅次於美洲豹和羽神。

### 兵 (P)

![Pawn](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/ChakPawn.png)

兵的移動與攻擊是分開的。走法就如中國象棋的過河卒，吃子的方式卻如西棋的兵。

兵過河後升變為「士」。

### 士 (W)

![Warrior](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/ChakWarrior.png)

士的走法就如祭司，朝前方與後方三格動一步。與祭司不同的是，士不能退回河界後。

### 祭品 (O)

![Offering](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/Offering.png)



祭品不能移動或吃子，它一直待在在祭壇中心。設計上不只是為了主題（玩家獻上祭品），還可作為羽神的炮架。最後，如果你自己的國王在神殿內，它還有助於擋住神王的攻擊，如果此時沒有其他棋子則會強迫和棋。如果祭品在先前己被吃了，神王就有辦法登壇。


## 子力價值

詳細價值尚未知，但以下大小關係是己知的: 美洲豹 > 羽神 > 蚺蛇 > 禿鷹 > 祭司 > 士 > 兵

## 策略 - 棋子基本動法

**羽神**: 始終注意羽神的路線。在遊戲開始時，任何移動到羽神前面的棋子都會作為炮架攻擊對方的美洲虎，這是一個稍微有利的交換。

**美洲豹**: 建立防禦並防止美洲豹過河。如果美洲豹在你的棋子生根之前就發攻擊，將可以輕鬆地捉雙。

**兵**: 兵非常靈活和強大，並且很早就可升變。正因如此，它不像其他棋種的兵那樣可任意棄子；如果您願意棄兵，請確保獲得更好局勢，因為在遊戲結束時一個兵的差距可能會左右勝敗。

**神殿**: 神殿非常重要，因為對方的神王只要到達神殿就贏棋。

## 策略 - 殘局

殘局通常在搶先登上祭壇。在本節中，我們將關注以神王為唯一攻擊棋子的殘局。

### 王 v.s 王 

若對方國王是唯一的防守者，攻擊者只需要迫使對方王移出神殿，便可以輕鬆登壇:

![KvsKzugzwang](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/KvsKzugzwang.png)



當祭品還在的時候，攻擊者仍然可以獲勝，但更加棘手。 攻擊者應該做的不是登壇，而是以下這種困斃：

![KvsKStalemate](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/KvsKStalemate.png)

以下是走出這種困斃的棋譜:

![KvsKO](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/KvsKO.png)

1. Dd6+ 

2. Kf7 Dd7+ 

3. Kf2 De8

4. Kf9 Df7+

5. Ke9 De7!

如此形成以下局面:

![KvsKOzugzwang](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/KvsKOzugzwang.png)

此時綠方被迫移動，白方即可走出困斃。

然而。 如果防守方多出一子（不動的羽神除外），情況就會發生巨大變化，如下:

![KvsKdraw](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/KvsKdraw.png)

不管祭品是否還在，神王都沒有辦法將死守方的王。唯一需要擔心的是下錯棋，讓自己多出來的一子被神王吃掉。因此建議將其保留在最後4列內，因為神王永遠無法到達那裡，如此雙方便和棋。


### 堡壘

堡壘是指有子防守著祭壇，如此對方便無計可施: 

![Fortresses](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/Fortresses.png)

以上這些範例都意謂著，若一方將棋子移開防守，將卸掉堡壘，若雙方都如此則導致和局。另一方面，若一方的堡壘有根而一方沒有，該子通常可以過河並攻擊對方的堡壘，通常多子的一方會獲勝。

### 其他防禦

#### 美洲豹

美幻豹對神王會因重複局面而和棋

![JaguarPerpetual](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/JaguarPerpetual.png)

...除非對方可以直接棄子登壇。

![JaguarPerpetual2](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/JaguarPerpetual2.png)



然而當祭品還在時，又是兩碼子事:

![JaguarvsKO](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/JaguarvsKO.png)

綠可走 1. Jf9; 白方唯一可以繼續攻擊美洲豹的走法為 Df7, 但當 2. Je9+ Dg 而 3. Jd9, 則將失去對美洲豹的威脅。而若白方花二步來攻擊美洲豹， 綠方可以在河的另一頭作更有義意的事。 若白把王動到f9, 則 Jd8 後，同樣也會失去對美洲豹的威脅。所以最好是把王動到 d7 來迫使美洲豹移動。最好記得以走法來形成和棋。

#### 蚺蛇

![SerpentFortress](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/SerpentFortress.png)

蚺蛇可以封住整條路線，如此神王便無法登壇。

![SerpentFortressTrap](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/SerpentFortressTrap.png)

而且，若神王從劃記的格子離開去騷擾蚺蛇，可能會付出代價，例如:

![SerpentFortressTrap2](https://github.com/pychess/pychess-variants/blob/master/static/images/ChakGuide/SerpentFortressTrap2.png)

綠方棄蚺蛇攻擊白祭司，同時又守住綠祭壇。此時白祭司無論吃掉蚺蛇與否都無法阻止綠方登壇。
