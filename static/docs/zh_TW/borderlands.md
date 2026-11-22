<style>
td { vertical-align: top; }
.tab_inline { display: inline; width: 50%; border: 1px solid; }
.region_name { vertical-align: bottom; font-weight: bold; }
.region_area { vertical-align: top; }
.zone_highlight { vertical-align: middle; min-width: 60px; }
.piece_title { vertical-align: middle; width:50%; }
.piece_title_nowrap { white-space: nowrap; }
.piece_movement { vertical-align: middle; }
.piece_values { vertical-align: middle; border: 1px solid; }
#region_table tr.line_t { border-style: solid; border-width: 1px 0px 0px 0px; }
#region_table tr.line_b { border-style: solid; border-width: 0px 0px 1px 0px; }
#region_table tr.line_tb { border-style: solid; border-width: 1px 0px 1px 0px; }
#region_table td { text-align: left; }

.board_row { display: flex; }
.board_column { flex: 50%; padding: 5px; }
</style>

# 🌄 邊境之地 (Borderlands)

![Borderlands](../../static/images/BorderlandsGuide/BorderlandsPoster.png)

《邊境之地》(Borderlands) 是 dpldgr 於 2025 年為了 PyChess 變體設計競賽所創作的西洋棋變體。

《邊境之地》從許多經典棋類（西洋棋、將棋、象棋和信使棋）中汲取靈感，並以獨特且富有創意的方式將它們融合在一起。總體而言，這裡的棋子比經典變體中的棋子更為強大。

- **首領 (Chief)**（即「王」類棋子）機動性很高，但移動範圍受限，這使得它容易被圍困並吃掉。
- 滑行棋子（如車、象）與跳躍吃子棋子（如炮、斜炮）被融合，創造出更強大的棋子（如**弓箭手**、**投石手**）。
- 大多數棋子都可以**升變 (Promotion)**，這提供了將棋子留在棋盤上的誘因，因為每個棋子都能透過圍捕敵方首領或佔領村莊格來協助贏得比賽。
- 玩家不能只是單純地將棋子向前推進，否則會暴露破綻，導致因「征服」條件而迅速落敗。
- 擁有種類繁多的棋子，各自具備不同的優勢與劣勢。

## 歷史背景
《邊境之地》並非設定在特定的地點或文化中。相反地，它抽象地呈現了古典時代早期（約西元前 500-100 年）隨著戰車戰術衰退後的戰爭演變。它反映了該時代典型的步兵陣型、散兵（游擊兵）戰術以及新興的聯合作戰戰術重點。

## 一般規則
1.	白方先行。
2.	所有棋子皆可被捕捉，且一旦被吃掉即永久移出遊戲。
3.	《邊境之地》中沒有「將死」(Checkmate) 或「逼和」(Stalemate)。
4.	《邊境之地》中沒有「入堡」(Castling)。取而代之的是，首領在任何回合都可以選擇在其移動區域內向任意方向進行兩格的不吃子跳躍。
5.	棋子一旦抵達其**晉升區 (Promotion Zone)** 或**晉升格**，即立即升變。
6.	開局位於第 3 列的**戰士 (Warrior)** 在其第一步可以選擇走兩格，並且在敵方的下一回合中可以被執行「吃過路兵」(En Passant)。

## 獲勝條件
1.	**投降獲勝**：吃掉敵方兩名首領，敵方立即投降。
2.	**征服獲勝**：連續兩個回合佔據所有四個**村莊格 (Village Squares)**（每位玩家各一回合）。

## 和局條件
1.	**無進展**：150 回合內（每方各 75 回合）沒有吃子或升變。
2.	**僵局**：由於雙方都沒有現實機會佔領所有四個村莊格或捕捉兩名敵方首領，導致遊戲無法進行。

## 失敗條件
1.	**無棋可走**：如果輪到玩家行動時無法做出任何合法移動，該玩家輸掉遊戲。
2.	**長將**：（待確認：這對首領是否適用）。
3.	**重複局面**：同一局面重複出現第 5 次。

## 棋盤
《邊境之地》的空棋盤與初始佈局如下：

<div class="board_row">
  <div class="board_column"><img src="../../static/images/BorderlandsGuide/BoardEmpty.png" alt="Borderlands Empty Board" style="width:100%"></div>
  <div class="board_column"><img src="../../static/images/BorderlandsGuide/BoardInitial.png" alt="Borderlands Initial Position" style="width:100%"></div>
</div>

### 區域與格位
《邊境之地》有許多重要的區域與特定格位：

<table id="region_table" style="border-style: solid; border-width: 1px 0px; border-collapse: collapse;">
<tbody>
	<tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../../static/images/BorderlandsGuide/WhiteTerritory.png" alt="White Territory"></td><td class="region_name">白方領地 (White Territory)</td></tr>
	<tr><td class="region_area">第 1-5 列</td></tr>
	<tr><td>所有白方棋子在遊戲開始時皆位於此區域內。</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../../static/images/BorderlandsGuide/WhiteVillageZone.png" alt="White Village Zone"></td><td class="region_name">白方村莊區 (White Village Zone)</td></tr>
	<tr><td>第 1-3 列</td></tr>
	<tr><td>大多數白方棋子在遊戲開始時位於此區域。</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../../static/images/BorderlandsGuide/WhiteIncursionZone.png" alt="White Incursion Zone"></td><td class="region_name">白方入侵區 (White Incursion Zone)</td></tr>
	<tr><td>第 6-7 列</td></tr>
	<tr><td>白方掠奪者 (Marauders) 必須投入此區域才能進場。黑方戰士最初防守著此區域的每一個格子。</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../../static/images/BorderlandsGuide/WhitePromotionZone.png" alt="White Promotion Zone"></td><td class="region_name">白方晉升區 (White Promotion Zone)</td></tr>
	<tr><td>第 8-10 列</td></tr>
	<tr><td>所有可升變的白方棋子（雄獅除外）皆可在此區域內任意位置升變。</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="2"><img src="../../static/images/BorderlandsGuide/WhiteVillages.png" alt="White Villages"></td><td class="region_name">白方村莊 (White Villages)</td></tr>
	<tr><td>西南村莊：a1,b1,c1,a2,b2,c2,a3,b3,c3<br/>東南村莊：g1,h1,i1,g2,h2,i2,g3,h3,i3</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="2"><img src="../../static/images/BorderlandsGuide/WhiteVillageSquares.png" alt="White Village Squares"></td><td class="region_name">白方村莊格 (White Village Squares)</td></tr>
	<tr><td>西南村莊格：b2<br/>東南村莊格：h2</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="2"><img src="../../static/images/BorderlandsGuide/WhiteLionsYard.png" alt="White Lion's Yard"></td><td class="region_name">白方雄獅庭院 (White Lion's Yard)</td></tr>
	<tr><td>格位：d1,e1,f1,d2,e2,f2,d3,e3,f3</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="2"><img src="../../static/images/BorderlandsGuide/WhiteLionsDen.png" alt="White Lion's Den"></td><td class="region_name">白方雄獅巢穴 (White Lion's Den)</td></tr>
	<tr><td>格位：e2</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../../static/images/BorderlandsGuide/WhiteLionsIncursionSquares.png" alt="White Lion's Incursion Squares"></td><td class="region_name">白方雄獅入侵格 (White Lion's Incursion Squares)</td></tr>
	<tr><td>格位：d7,f7</td></tr>
	<tr><td>白方雄獅必須通過這些格位之一才能進行升變。</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../../static/images/BorderlandsGuide/WhiteLionsPromotionSquare.png" alt="White Lion's Promotion Square"></td><td class="region_name">白方雄獅晉升格 (White Lion's Promotion Square)</td></tr>
	<tr><td>格位：e9</td></tr>
	<tr><td>白方雄獅抵達此格後升變，隨後即可自由遊走於整個棋盤。</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../../static/images/BorderlandsGuide/WhiteLionsMovementZone.png" alt="White Lion's Movement Zone"></td><td class="region_name">白方雄獅活動區 (White Lion's Movement Zone)</td></tr>
	<tr><td>區域：白方領地、白方雄獅入侵區、白方雄獅晉升格</td></tr>
	<tr><td></td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../../static/images/BorderlandsGuide/BlackTerritory.png" alt="Black Territory"></td><td class="region_name">黑方領地 (Black Territory)</td></tr>
	<tr><td>第 6-10 列</td></tr>
	<tr><td>所有黑方棋子在遊戲開始時皆位於此區域內。</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../../static/images/BorderlandsGuide/BlackVillageZone.png" alt="Black Village Zone"></td><td class="region_name">黑方村莊區 (Black Village Zone)</td></tr>
	<tr><td>第 8-10 列</td></tr>
	<tr><td>大多數黑方棋子在遊戲開始時位於此區域。</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../../static/images/BorderlandsGuide/BlackIncursionZone.png" alt="Black Incursion Zone"></td><td class="region_name">黑方入侵區 (Black Incursion Zone)</td></tr>
	<tr><td>第 4-5 列</td></tr>
	<tr><td>黑方掠奪者 (Marauders) 必須投入此區域才能進場。白方戰士最初防守著此區域的每一個格子。</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../../static/images/BorderlandsGuide/BlackPromotionZone.png" alt="Black Promotion Zone"></td><td class="region_name">黑方晉升區 (Black Promotion Zone)</td></tr>
	<tr><td>第 1-3 列</td></tr>
	<tr><td>所有可升變的黑方棋子（雄獅除外）皆可在此區域內任意位置升變。</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="2"><img src="../../static/images/BorderlandsGuide/BlackVillages.png" alt="Black Villages"></td><td class="region_name">黑方村莊 (Black Villages)</td></tr>
	<tr><td>西北村莊：a8,b8,c8,a9,b9,c9,a10,b10,c10<br/>東北村莊：g8,h8,i8,g9,h9,i9,g10,h10,i10</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="2"><img src="../../static/images/BorderlandsGuide/BlackVillageSquares.png" alt="Black Village Squares"></td><td class="region_name">黑方村莊格 (Black Village Squares)</td></tr>
	<tr><td>西北村莊格：b9<br/>東北村莊格：h9</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="2"><img src="../../static/images/BorderlandsGuide/BlackLionsYard.png" alt="Black Lion's Yard"></td><td class="region_name">黑方雄獅庭院 (Black Lion's Yard)</td></tr>
	<tr><td>格位：d8,e8,f8,d9,e9,f9,d10,e10,f10</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="2"><img src="../../static/images/BorderlandsGuide/BlackLionsDen.png" alt="Black Lion's Den"></td><td class="region_name">黑方雄獅巢穴 (Black Lion's Den)</td></tr>
	<tr><td>格位：e9</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../../static/images/BorderlandsGuide/BlackLionsIncursionSquares.png" alt="Black Lion's Incursion Squares"></td><td class="region_name">黑方雄獅入侵格 (Black Lion's Incursion Squares)</td></tr>
	<tr"><td>格位：d4,f4</td></tr>
	<tr><td>黑方雄獅必須通過這些格位之一才能進行升變。</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../../static/images/BorderlandsGuide/BlackLionsPromotionSquare.png" alt="Black Lion's Promotion Square"></td><td class="region_name">黑方雄獅晉升格 (Black Lion's Promotion Square)</td></tr>
	<tr><td>格位：e2</td></tr>
	<tr><td>黑方雄獅抵達此格後升變，隨後即可自由遊走於整個棋盤。</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../../static/images/BorderlandsGuide/BlackLionsMovementZone.png" alt="Black Lion's Movement Zone"></td><td class="region_name">黑方雄獅活動區 (Black Lion's Movement Zone)</td></tr>
	<tr><td>區域：黑方領地、黑方雄獅入侵區、黑方雄獅晉升格</td></tr>
	<tr><td></td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../../static/images/BorderlandsGuide/Roads.png" alt="Roads"></td><td class="region_name">道路 (Roads)</td></tr>
	<tr><td>東路格位：a4,a5,a6,a7<br/>中路格位：e4,e5,e6,e7<br/>西路格位：i4,i5,i6,i7<br/></td></tr>
	<tr><td>道路連接兩個村莊區域。</td></tr>
	<tr class="line_t"><td class="zone_highlight" rowspan="3"><img src="../../static/images/BorderlandsGuide/ChiefMovementZone.png" alt="Chief Movement Zone"></td><td class="region_name">首領活動區域 (Chief Movement Zone)</td></tr>
	<tr><td>區域：白方村莊區、黑方村莊區、道路</td></tr>
	<tr class="line_b"><td>首領的移動被限制在兩個村莊區與道路之間。</td></tr>
</tbody>
</table>

## 棋子
### 名稱、移動方式、記譜法、圖示與升變
下方的移動圖示遵循以下慣例：
<table style="border-collapse: collapse;">
<tbody>
	<tr><td width="15%"><img src="../../static/images/BorderlandsGuide/RedCircle.png" alt="Red Circle"></td><td class="piece_movement" style="text-align: left;">紅色圓圈：可移動至此格，若有敵子則可吃子，無阻礙。</td></tr>
	<tr><td width="15%"><img src="../../static/images/BorderlandsGuide/GreenCircle.png" alt="Green Circle"></td><td class="piece_movement" style="text-align: left;">綠色圓圈：僅可移動至此格（不吃子），無阻礙。</td></tr>
	<tr><td width="15%"><img src="../../static/images/BorderlandsGuide/BlueCircle.png" alt="Blue Circle"></td><td class="piece_movement" style="text-align: left;">藍色圓圈：僅可在此格吃子（不可單純移動），無阻礙。</td></tr>
	<tr><td width="15%"><img src="../../static/images/BorderlandsGuide/GreenLine.png" alt="Green Line"></td><td class="piece_movement" style="text-align: left;">綠色線條：可進行不吃子的滑行移動，最多三格。</td></tr>
	<tr><td width="15%"><img src="../../static/images/BorderlandsGuide/TealLine.png" alt="Teal Line"></td><td class="piece_movement" style="text-align: left;">青色線條：可進行吃子或不吃子的滑行移動，或者像「炮」一樣跳過一個棋子進行吃子。</td></tr>
</tbody>
</table>

<table style="border-collapse: collapse;">
<tbody>
	<tr><td width="25%"></td><td class="piece_title" width="50%" style="background-color:#d4c7e3;color:#000000">首領 (Chief, C)</td><td width="25%"></td></tr>
	<tr><td width="25%"></td><td><img src="../../static/images/BorderlandsGuide/Chief.png" alt="Chief"><br/>Betza: KmNmAmD</td><td width="25%"></td></tr>
	<tr><td colspan="3">首領是棋盤上最有價值的棋子。捕捉敵方兩名首領，敵人將立即投降。<p/>首領的移動範圍僅限於村莊區域以及連接村莊的道路。<p/></td><td></td><td></td></tr>
	<tr><td width="25%"></td><td class="piece_title" style="background-color:#e6e6e6;color:#000000">衛兵 (Guard, G)</td><td width="25%"></td></tr>
	<tr><td width="25%"></td><td><img src="../../static/images/BorderlandsGuide/Guard.png" alt="Guard"><br/>Betza: KmNmAmD</td><td width="25%"></td></tr>
	<tr><td colspan="3">衛兵是唯一無法升變的棋子，遊戲一開始即可自由遊走於整個棋盤。它們的職責是不惜一切代價保護己方首領。<p/></td><td></td><td></td></tr>
</tbody>
</table>
<table style="border-collapse: collapse;">
<tbody>
	<tr><td class="piece_title" style="background-color:#e6e6e6;color:#000000"><span class="piece_title_nowrap">掠奪者 (Marauder, M)</span></td><td class="piece_title" style="background-color:#f7e6ae;color:#000000">晉升後的 <span class="piece_title_nowrap">掠奪者 (+M)</span></td></tr>
	<tr><td><img src="../../static/images/BorderlandsGuide/Marauder.png" alt="Marauder"><br/>Betza: FmN</td><td><img src="../../static/images/BorderlandsGuide/MarauderPromoted.png" alt="Marauder Promoted"><br/>Betza: KmN</td></tr>
	<tr><td colspan="2">掠奪者的職責是不惜一切代價擾亂敵人。如果敵人的防禦有小漏洞，他們可以迅速潛入敵後。
<p/>
掠奪者在遊戲開始時位於「手中」(in hand)，必須透過投放至其「入侵區」才能進場，且通常能在下一回合升變。<p/>
它們可以像菲爾茲 (Ferz, 斜向走一格) 移動，也可以像騎士 (Knight) 一樣進行不吃子跳躍。升變後，掠奪者獲得正向 (Orthogonally) 走一格的能力。</td><td></td></tr>
	<tr><td class="piece_title" style="background-color:#e6e6e6;color:#000000"><span class="piece_title_nowrap">獵鷹 (Falcon, F)</span></td><td class="piece_title" style="background-color:#f7e6ae;color:#000000">晉升後的 <span class="piece_title_nowrap">獵鷹 (+F)</span></td></tr>
	<tr><td><img src="../../static/images/BorderlandsGuide/Falcon.png" alt="Falcon"><br/>Betza: WmAmD</td><td><img src="../../static/images/BorderlandsGuide/FalconPromoted.png" alt="Falcon Promoted"><br/>Betza: KmAmD</td></tr>
	<tr><td colspan="2">它們可以像瓦齊爾 (Wazir, 正向走一格) 移動，也可以像阿爾菲 (Alfil, 斜向跳兩格) 或達巴巴 (Dabbaba, 正向跳兩格) 一樣進行不吃子跳躍。升變後，獵鷹獲得斜向走一格的能力。<p/></td><td></td></tr>
	<tr><td class="piece_title" style="background-color:#e6e6e6;color:#000000"><span class="piece_title_nowrap">戰象 (Elephant, E)</span></td><td class="piece_title" style="background-color:#f7e6ae;color:#000000">晉升後的 <span class="piece_title_nowrap">戰象 (+E)</span></td></tr>
	<tr><td><img src="../../static/images/BorderlandsGuide/Elephant.png" alt="Elephant"><br/>Betza: ADmR3</td><td><img src="../../static/images/BorderlandsGuide/ElephantPromoted.png" alt="Elephant Promoted"><br/>Betza: ADmR3WmF</td></tr>
	<tr><td colspan="2">戰象是跳躍棋子。它們可以像阿爾菲 (Alfil) 或達巴巴 (Dabbaba) 一樣移動，並能像車 (Rook) 一樣進行最多三格的不吃子滑行。升變後，戰象獲得正向走一格 (W) 和斜向不吃子走一格 (mF) 的能力。<p/></td><td></td></tr>
	<tr><td class="piece_title" style="background-color:#e6e6e6;color:#000000"><span class="piece_title_nowrap">馬 (Horse, H)</span></td><td class="piece_title" style="background-color:#f7e6ae;color:#000000">晉升後的 <span class="piece_title_nowrap">馬 (+H)</span></td></tr>
	<tr><td><img src="../../static/images/BorderlandsGuide/Horse.png" alt="Horse"><br/>Betza: NmB3</td><td><img src="../../static/images/BorderlandsGuide/HorsePromoted.png" alt="Horse Promoted"><br/>Betza: NmB3FmW</td></tr>
	<tr><td colspan="2">馬是跳躍棋子。它們可以像騎士 (Knight) 一樣移動，並能像主教 (Bishop) 一樣進行最多三格的不吃子滑行。升變後，馬獲得斜向走一格 (F) 和正向不吃子走一格 (mW) 的能力。<p/></td><td></td></tr>
	<tr><td class="piece_title" style="background-color:#e6e6e6;color:#000000"><span class="piece_title_nowrap">投石手 (Slinger, S)</span></td><td class="piece_title" style="background-color:#f7e6ae;color:#000000">晉升後的 <span class="piece_title_nowrap">投石手 (+S)</span></td></tr>
	<tr><td><img src="../../static/images/BorderlandsGuide/Slinger.png" alt="Slinger"><br/>Betza: BcpBmW</td><td><img src="../../static/images/BorderlandsGuide/SlingerPromoted.png" alt="Slinger Promoted"><br/>Betza: BcpBW</td></tr>
	<tr><td colspan="2">投石手是遠程棋子，能沿著斜線從遠處攻擊。它們可以像主教 (Bishop) 一樣移動，像斜炮 (Vao) 一樣吃子（需跳過一子），還可以進行正向不吃子走一格 (mW)。升變後，投石手獲得正向吃子走一格 (W) 的能力。<p/></td><td></td></tr>
	<tr><td class="piece_title" style="background-color:#e6e6e6;color:#000000"><span class="piece_title_nowrap">弓箭手 (Archer, A)</span></td><td class="piece_title" style="background-color:#f7e6ae;color:#000000">晉升後的 <span class="piece_title_nowrap">弓箭手 (+A)</span></td></tr>
	<tr><td><img src="../../static/images/BorderlandsGuide/Archer.png" alt="Archer"><br/>Betza: RcpRmF</td><td><img src="../../static/images/BorderlandsGuide/ArcherPromoted.png" alt="Archer Promoted"><br/>Betza: RcpRF</td></tr>
	<tr><td colspan="2">弓箭手是遠程棋子，能沿著直線從遠處攻擊。它們可以像車 (Rook) 一樣移動，像炮 (Pao) 一樣吃子（需跳過一子），還可以進行斜向不吃子走一格 (mF)。升變後，弓箭手獲得斜向吃子走一格 (F) 的能力。<p/></td><td></td></tr>
	<tr><td class="piece_title" style="background-color:#e6e6e6;color:#000000"><span class="piece_title_nowrap">戰士 (Warrior, W)</span></td><td class="piece_title" style="background-color:#f7e6ae;color:#000000">晉升後的 <span class="piece_title_nowrap">戰士 (+W)</span></td></tr>
	<tr><td><img src="../../static/images/BorderlandsGuide/Warrior.png" alt="Warrior"><br/>Betza: fWfceFifmnD</td><td><img src="../../static/images/BorderlandsGuide/WarriorPromoted.png" alt="Warrior Promoted"><br/>Betza: NADmQ3</td></tr>
	<tr><td colspan="2">戰士的移動方式結合了西洋棋兵 (Pawn) 和將棋步兵 (Pawn)。位於第 3 列的戰士在第一步可以走兩格，並可在敵方下一回合被敵方戰士「吃過路兵」。升變後，戰士的移動方式會改變。<p/>晉升後的戰士可以像騎士、阿爾菲或達巴巴一樣移動，並能像后 (Queen) 一樣進行最多三格的不吃子滑行 (mQ3)。<p/></td><td></td></tr>
	<tr><td class="piece_title" style="background-color:#e6e6e6;color:#000000"><span class="piece_title_nowrap">雄獅 (Lion, L)</span></td><td class="piece_title" style="background-color:#f7e6ae;color:#000000">晉升後的 <span class="piece_title_nowrap">雄獅 (+L)</span></td></tr>
	<tr><td><img src="../../static/images/BorderlandsGuide/Lion.png" alt="Lion"><br/>Betza: KNAD</td><td><img src="../../static/images/BorderlandsGuide/LionPromoted.png" alt="Lion Promoted"><br/>Betza: KNAD</td></tr>
	<tr><td colspan="2">雄獅在遊戲開始時是防禦性棋子，被限制在己方領地內，且晉升路徑非常有限（需通過雄獅入侵格），很容易被防守。一旦升變，雄獅即獲得遊走整個棋盤的能力。<p/></td><td></td></tr>
</tbody>
</table>

### 棋子價值
<table  style="border-collapse: collapse; border: 1px solid;">
<tbody>
	<tr><td class="piece_values"><b>棋子</b></td><td class="piece_values"><b>代號</b></td><td class="piece_values"><b>價值</b></td><td class="piece_values"><b>棋子</b></td><td class="piece_values"><b>代號</b></td><td class="piece_values"><b>價值</b></td></tr>
	<tr><td class="piece_values">晉升雄獅</td><td class="piece_values">+L</td><td class="piece_values">9.45</td><td class="piece_values">首領</td><td class="piece_values">C</td><td class="piece_values">3.11</td></tr>
	<tr><td class="piece_values">晉升弓箭手</td><td class="piece_values">+A</td><td class="piece_values">8.82</td><td class="piece_values">晉升獵鷹</td><td class="piece_values">+F</td><td class="piece_values">2.51</td></tr>
	<tr><td class="piece_values">晉升戰士</td><td class="piece_values">+W</td><td class="piece_values">6.75</td><td class="piece_values">衛兵</td><td class="piece_values">G</td><td class="piece_values">2.17</td></tr>
	<tr><td class="piece_values">弓箭手</td><td class="piece_values">A</td><td class="piece_values">5.77</td><td class="piece_values">馬</td><td class="piece_values">H</td><td class="piece_values">2.16</td></tr>
	<tr><td class="piece_values">晉升投石手</td><td class="piece_values">+S</td><td class="piece_values">4.88</td><td class="piece_values">戰象</td><td class="piece_values">E</td><td class="piece_values">2.12</td></tr>
	<tr><td class="piece_values">雄獅</td><td class="piece_values">L</td><td class="piece_values">4.14</td><td class="piece_values">晉升掠奪者</td><td class="piece_values">+M</td><td class="piece_values">1.51</td></tr>
	<tr><td class="piece_values">晉升馬</td><td class="piece_values">+H</td><td class="piece_values">3.94</td><td class="piece_values">戰士</td><td class="piece_values">W</td><td class="piece_values">1.00</td></tr>
	<tr><td class="piece_values">投石手</td><td class="piece_values">S</td><td class="piece_values">3.81</td><td class="piece_values">獵鷹</td><td class="piece_values">F</td><td class="piece_values">0.90</td></tr>
	<tr><td class="piece_values">晉升戰象</td><td class="piece_values">+E</td><td class="piece_values">3.61</td><td class="piece_values">掠奪者</td><td class="piece_values">M</td><td class="piece_values">0.65</td></tr>
</tbody>
</table>
<img src="../../static/images/BorderlandsGuide/PieceValues.png" alt="Piece Values">

## 策略
TODO.

《邊境之地》玩法教學影片：
TODO

遊戲範例 1：
<iframe width="560" height="315" src="https://www.youtube.com/embed/NsAGUMWxyCo" frameborder="0" allowfullscreen></iframe>
遊戲範例 2：
<iframe width="560" height="315" src="https://www.youtube.com/embed/y88_OAx8bRk" frameborder="0" allowfullscreen></iframe>
