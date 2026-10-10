# ![Makruk ikon](https://github.com/pychess/pychess-variants/blob/master/static/icons/makruk.svg) Makruk (Thai sakk)

![Makruk ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Makruk.png?raw=true)

A *makruk*, avagy a thai sakk egy klasszikus táblajáték, mely Thaiföldön őshonos és a [csaturangából](https://hu.wikipedia.org/wiki/Csaturanga) eredeztethető, akárcsak a sakk.
A játékot Kambodzsában is játsszák (apró szabálymódosításokkal), ott *Ouk Chatrang* vagy *Ok* néven ismert.

Makrukot játszva megtapasztalhatjuk, hogy milyen volt a sakk, mielőtt még a modern időkben bevezetett szabályok felgyorsították volna a játékot. A kissé lassabb tempó jó lehetőséget ad arra, hogy türelmet gyakoroljunk és a stratégiai gondolkodásunkat fejlesszük.

Vlagyimir Kramnyik azt mondta, hogy *"a thai makruk stratégiaibb, mint a nemzetközi sakk. A lépéseidet teljes odafigyeléssel kell megtervezned, mert a makruk a sakk végjátékához hasonlítható.”*
 
## Szabályok

A szabályok általánosságban véve nagyon hasonlóak a sakkéhoz, ezért ez az útmutató inkább a különbségekre fókuszál. A legfontosabb különbségek, hogy a bábuk egy része másképpen mozog, a gyalogok a 3. sorban kezdenek, illetve a király mindig a bal oldalon áll, színtől függetlenül. A cél itt is az ellenfél királyának mattolása, a patthelyzet pedig itt is döntetlent eredményez.

## Bábuk

Zárójelben a bábuk eredeti neve.

### Király (*Kun*)

![király ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/King.png?raw=true)

A király ugyanúgy lép és üt, mint a sakkban, azonban nem sáncolhat.

### Vezér (*Met*)

![vezér ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Queen.png?raw=true)

A vezér itt sokkal gyengébb bábu, mint a sakkban, mert csak egy mezőt tud lépni átlóban. Értéke nagyjából 1,5 - 2 gyalognak felel meg. A vezér megfelelő a támadások vezetésére és hasznos lehet az ellenfél fenyegetésére.

### Futó (*Kon*)

![futó ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Bishop.png?raw=true)

A futó egy mezőt léphet átlósan, vagy egy mezőt előre (mint a sógiban az ezüsttábornok).

A futó egy erős bábu arra, hogy az ellőtte lévő mezőket kontrollálja, de a király védelmezésére is megfelelő lehet.

A futó itt értékesebb, mint a vezér, de általánosságban elmondható, hogy kevésbé értékes, mint a huszár, mert a futó nem tud olyan könnyen elmenekülni a veszélyes helyzetekből, mint a huszár.

### Huszár (*Ma*)

 ![Huszár ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Knight.png?raw=true)

A huszár ugyanúgy mozog, mint a sakkban (L-alakzatban és képes átugrani a köztes bábukat). Értékes és erős, központi figura.

### Bástya (*Rua*)

 ![Bástya ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Rook.png?raw=true)

A bástya ugyanúgy mozog, mint a sakkban (akárhány mezőt vízszintesen vagy függőlegesen). Erős vezér hiányában a bástya a domináns egység.

### Gyalog (*Bia*)

![Gyalog ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Pawn.png?raw=true) ![Átváltoztatott gyalog ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/ProPawn.png?raw=true)

A gyalog ugyanúgy mozog, mint a sakkban (egyet előre), és úgy is üt (átlóban előre egyet). Nem léphet kettőt első lépésként. Amikor a gyalogok elérik a 6. sort (illetve a a másik oldalról a 3. sort), akkor átváltoznak és úgy lépnek/ütnek, mint a vezér (átlóban egyet).

Az átváltoztatott gyalog gyakori a végjátékokban, ahol a mattadásban nyújthat segítséget. Továbbá jó csali lehet, akit először el kell fogni ahhoz, hogy az általa védett király mattolható legyen. Szerepe lehet az ellenséges erők szétszakításában, ami után az újraszervezés értékes időt vehet el. Ez a vesztésre álló, védekező oldal számára esélyt adhat arra, hogy döntetlenre hozza ki a játszmát a lépésszámlálási szabály értelmében (lásd lentebb).

## Lépésszámlálási szabályok

Kétféle lépésszámlálási szabály van: a "táblás" és a "bábus" számolás.

Ha az utolsó gyalog is leütésre került (tehát egyik félnek sincs gyalogja a táblán), akkor megkezdődik a számolás, és 64 lépésben kell győzelmet elérni (ennyi mező van a táblán, ezért a tábla tiszteletére vonatkozó számolásnak is nevezik). A hátrányban lévő játékos számol, és bármikor abbahagyhatja a számolást, de ha ezután újrakezdi, akkor megint 1-ről kell kezdenie. Ha a hátrányban lévő játékos úgy ad mattot, hogy előtte nem hagyta abba a számolást, akkor az eredmény döntetlen.

A második számolási szabály akkor lép érvénybe, amikor a vesztésre álló játékos utolsó bábuja is leütésre került (azaz csak egy királya maradt). Ekkor a nyerésre álló játékosnak a táblán lévő bábuitól függően egy megadott számú lépésben kell mattot adnia, különben az eredmény döntetlen (ezt a bábuk tiszteletére vonatkozó számolásnak is nevezik).

Meglévő bábu	| Ennyi lépésben kell győzni
-- | -- 
Két bástya | 8 
Egy bástya | 16 
Nincs bástya, de van két futó | 22 
Nincs bástya, nincs futó, de van két huszár | 32 
Nincs bástya, de van egy futó | 44
Nincs bástya, nincs futó, de van egy huszár | 64 
Nincs bástya, nincs futó, nincs huszár, csak vezér | 64 

Miután a számolás a fentiek alapján megkezdődött, a maximális lépések száma (és a számolás is) rögzítetté  válik, az nem változik meg akkor sem, ha közben egy bábu leütésre kerül. Ha például az egyedül maradt király leütné a két támadó bástya közül az egyiket, a számolás nem kezdődne újra és a maximális lépések száma sem változna meg, azaz a bástyának ugyanúgy 8 lépésen belül kellene mattolnia, a 9. lépésben pedig már döntetlen lenne a játszma.

## Stratégia

A játék tempója lassúnak mondható, a legtöbb bábu csak egy mezőt tud lépni valamilyen irányba. Érdemes a bábukat csoportokba szervezni és úgy mozgatni őket, hogy kölcsönös támogatást nyújtsanak egymásnak. Nem érdemes egy időben több frontot megnyitni. A kulcs a megfelelő koordináció.

## Taktika

Egyedül a bástya képes kötést létrehozni. Ezen kívül leginkább a kettős támadás (villa) fordul még elő.

Amikor az egyik oldalnak már csak egy királya marad, akkor az életbe lépő számlálási szabályok nyomás alá helyezik a támadó oldalt. A vesztésre álló játékost ez arra ösztönzi, hogy végigjátssza a játékot, ahelyett, hogy feladná. Ezért fontos, hogy minden alapvető mattolási módszert megtanuljunk az egyedüli királlyal szemben.
