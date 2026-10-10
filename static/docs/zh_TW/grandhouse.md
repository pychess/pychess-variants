# ![Grandhouse](https://github.com/pychess/pychess-variants/blob/master/static/icons/Grandhouse.svg) 雙狂大象棋

雙狂大象棋的規則就如雙狂象棋與西洋大象棋，只是略有修改。

## 雙狂象棋規則

除使用正統的西洋棋規則外，另外加上簡化的日本將棋持駒（打入）規則。記譜方式同一般，但棋子打入時用@符號表示。每回玩家可選擇移動自己的棋子，或將俘虜來的棋子放置沒有被佔據的格子上。將棋子放回時必須遵循下列原則：

* 允許打步詰(即打入兵將死對方，這與日本將棋不同)。
* 兵不能打在己方底線或**8 - 10 列**!
* 升變後的兵被吃掉後會還原成兵打入場上。
* 打入在己方第三列(就是兵初始所在列)的兵允許第一步動二格。

**與雙狂象棋不同之處**: *兵不能打在8 - 10 列(對方前三列)*

## 西洋大象棋規則

以下全都來自西洋大象棋的規則:

使用10\*10格的棋盤。

棋子佈置為第三橫行皆為兵卒。第二橫行佈置從白方左側、黑方右側開始，皆為空格、騎士、主教、皇后、國王、首相、大主教、主教、騎士、空格。底橫行的左右角各有一城堡。

除了新增棋子和初始配置不同外，另有以下三個新增規則:

* 兵在到達第八列及第九列時升變，到第十列時則**必需**升變，若無法升變(見下點)，則該兵不可至進到第十行。
* 兵只能升變成與它同色的棋子，且該棋子已經失去。
* 沒有王車易位。

其餘規則與正統象棋同。

## 新棋子

### 大主教

![Cardinal](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Princesses.png)

大主教，Archbishop ：走法同西洋棋的主教 + 騎士(看棋子的樣子就知道了吧!)。記法簡稱為A。

![Cardinal moves](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Archbishop.png)


大主教是唯一可以單獨將死對方王的棋子。

通常認為大主教的價值大於城堡，但遜於大象和王后。

### 首相

![Marshal](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Empresses.png)

首相，Chancellor ：走法同西洋棋的城堡 + 騎士，記法簡稱為C。 (還有另一個名稱為大象，只會在S-Chess中使用)

![Marshal moves](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Chancellor.png)


棋子價值比大主教高，但遜於或等於王后。

## 策略


請不要以「象棋」的觀念，一開始就急於出動子力，在西洋大象棋中，有時重複的動同一子反而會給對方造成更多威脅。

子力價值與傳統西洋棋同，由於打入的規則你可以不斷地換子、棄子打入，並擅用騎士和兵的捉雙。 你也可以打入子在國王旁邊加強防守。
