# ![Shogun](https://github.com/pychess/pychess-variants/blob/master/static/icons/shogun.svg) 幕府棋

![Shogun](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ShogunPromotions3.png)

幕府棋是一種國際象棋變體，在2019-2020被Couch Tomato推出。雖然這種變體是融西洋棋於將其的規則，原意
是用跟通常的方式引進仙靈棋子（大主教和首相）。比如說，保持8x8棋盤而非讓它擴大，這樣不會減損小棋子的價值。另外我們希望避免S-chess的凌亂棋盤。思想演變到讓小棋子在對方底線之前升變為仙靈棋。後來“打入“也加入規則為了增加攻擊性的選擇而抵消防禦性質由於升變的威脅。兵棋和馬的獨特升變以及王后的降至也加入規則為了完成主題和對稱性。
名字本來暫定稱為”General's Chess“，根據那時兵的升變，現在馬的升變。然而，因為打入和升變地區的規則以日本將其為基礎，日本語的”將軍“一詞聽起來更合適。

## 規則

1. 佈置跟國際象棋一樣

2. 新棋子如上圖中的定義，它們的移動是以下纖細的描述。值得注意的是升變的棋子顏色不一樣。此外，王后開始的形式是升變的，儘管它有新的未升變形式（士）。為了術語的緣故，車會稱為小棋子，後，首相，大主教和將軍(不包括隊長)被認為大棋子。

3. 升變：位於距離棋手最遠的三行稱為敵陣。當一枚可升級的棋子移進，移出，或者在敵陣中移動時，棋手可以選擇把該棋子翻轉升級或保持原裝。每個起步者（或者打入者）棋子（除了王和王后外）可升級。然而，你只能擁有每種棋子一枚升變形式的。例如，如果白方擁有一枚大主教，他剩餘的像不可升變直到現有的大主教被吃掉。

4. 打入：猶如日本將其和crazyhouse一樣，棋手可以花一手將己方吃掉的棋子放回棋盤成為己方棋子，當一枚已升級的棋子被吃時，它的升級被取消（這樣王后可變回士）。打入被限製到先五行，正確的說不可打入到對方的敵陣。步兵可打入第一行！

其他規則說明:
* 車被打入之後不可做王車易位。
* 兵被打入在第一行還可從第二行前進兩格
* 吃過路兵可行，不過不可直接升變。

## 棋子

### 大主教 | 副官 | 公主 Archbishop (A)

![Archbishop](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ArchbishopShogun.png)

國際象棋變體中的一種常見的仙靈棋子。再此遊戲中，它升級從象而合併馬的移動。因此，只有它能單人匹馬把王將死。

### 首相 | Mortar (M)

![Mortar](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Mortar.png)

首相也是常見。再次遊戲中，它升級從車而合併馬的移動。

### 將軍 | General | Centaur (G)

![General](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/General.png)

將軍的移動如馬或王的走法。

### 隊長 | Captain (C)

![Captain](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Captain.png)

隊長升級從兵而走法跟王一樣。與眾不同，許多隊長可能同時存在，因為它的身份是小棋子。

### 士 | Duchess | Ferz (F) 

![Duchess](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Duchess.png)

士升變到王后，它只能在後被吃掉之後能存在與棋手手中的士。士的移動為斜向一格。別忘記，士不能升為後，如果棋手已經擁有一枚後（在幕府棋中，一夫多妻是非法的!）。

## 戰略

遊戲還年輕，沒有太多的戰略！
重要是防禦你的敵陣，而不讓對方免費升變。戰略跟Crazyhouse不一樣，因為打入的嚴厲限制。無論怎樣，王的安全有關鍵的重要性，而棋子價值相對位置被減少。位置包括多少方格雙方能控制，特別重要是控制王周圍的方格。因為兵能打入到第一行，雙方可以建造一個非常堅固的城堡，不過這樣不會為了對方造成問題。玩家們應該不斷嘗試激活他們的棋子而同時限制對方，希望如此鑽孔子。