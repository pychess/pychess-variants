# ![Janggi ikon](https://github.com/pychess/pychess-variants/blob/master/static/icons/Janggi.svg) Janggi (Koreai sakk)

![Janggi tábla](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Boards.png)

A janggi (장기), avagy a koreai sakk egy klasszikus táblajáték, mely Koreában őshonos. A játék a kínai sakkból (xiangqi) eredeztethető és nagyon hasonló ahhoz.

## Tábla és kezdőpozíciók

Az egyik oldal itt piros színű (melynek neve *Han*), a másik pedig kék (melynek neve *Cho*). A kék helyett zöld szín is használatos. Ez a két oldal a kínai történelemből ismert Chu-Han belviszályt reprezentálja. A bábukra a nevek kínai írásjegyekkel (handzsa) vannak felfestve, de a kék bábukon a folyóírásos (kézírásos) változatuk szerepel, ezért a piros és a kék bábuk nem ugyanúgy néznek ki.

A kezdőállás a fenti képeken látható (azonban a ló és az elefánt felcserélhető, lásd lentebb). A játékot a kínai sakkhoz hasonlóan 9x10-es táblán játsszák, a bábuk pedig a mezők metszéspontjain állnak/mozognak, nem pedig a mezőkön belül. A 3x3-as terület a tábla alján a *palota*. A király és a testőrei csak a palotán belül tudnak mozogni.

A játszma megkezdése előtt mindkét játékos megválaszthatja a lovak és az elefántok kezdőpozícióját. Négy opció közül lehet választani:

1. *Külső lovak*: mindkét ló a tábla széléhez van közelebb (*won ang ma*)
2. *Belső lovak*: mindkét ló a királyhoz van közelebb (*yang gwee ma*)
3. *Bal belső, jobb külső ló*: a bal oldali ló a királyhoz, a jobb oldali pedig a tábla széléhez van közelebb (*gwee ma*)
4. *Bal külső, jobb belső ló*: a bal oldali ló a tábla széléhez, a jobb oldali pedig a királyhoz van közelebb (*mat sang jang gi*)

## Bábuk

A tradicionális készletek a kínai írásjegyeket használják, de a könnyebb érthetőség végett ez az útmutató a nemzetközi bábukészleten alapul (melyen a figurák ábrái láthatók).

Több bábunak is van speciális lépéslehetősége a palotákon belül (erről később lesz szó részletesen). Az ábrákon ezek világosabb árnyalatú zölddel vannak jelölve.

### Király

![Király bábuk](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Kings.png)

A *király* (vagy a kínai neve alapján: *tábornok*) csak a palotán belül tud mozogni (egyszerre egy mezőt), ami azt jelenti, hogy ha a közepén áll, akkor maximum 8 lehetséges lépése van. Ha bármely más helyen áll, akkor maximum 3 lehetséges lépése marad.

*Speciális szabály:* amikor a két király szemben áll egymással (egy vonalban), úgy, hogy nincs köztük bábu, akkor a soron következő játékosnak el kell lépnie a királyával vagy a két király közé kell léptetnie egy bábut, különben döntetlennel véget ér a játszma. Ezt a szabályt **bikjang**-nak nevezik.

### Testőr

![Testőr bábuk](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Advisors.png)

A *testőr* is ugyanúgy mozoghat, mint a király: egy lépést, kizárólag a palotán belül.

![Király és a testőrei ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Palace.png)

### Ló

 ![Ló bábuk](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Horses.png)
 
 ![Ló ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/HorseDiagram.png)

A *ló* hasonlóan mozog, mint a sakkban a huszár. Azonban az L-alakzattól eltérően inkább úgy tekintsünk a mozgására, hogy egyet lép vízszintesen vagy függőlegesen, majd átlóban egyet valamelyik irányba, egy Y-alakzatra emlékeztetve. Ennek az az oka, hogy a ló blokkolható, ha egy bábu mellette áll.

### Elefánt

 ![Elefánt bábuk](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Elephants.png)
 
 ![Elefánt ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/ElephantDiagram.png)

Az *elefánt* nagyon más, mint ami a kínai sakkban megtalálható. Hasonló a lóhoz, de az elefánt két mezőt lép átlóban, ezért a mozgása inkább egy nyújtott Y-alakzatot ír le. A lóhoz hasonlóan az elefánt is blokkolható a köztes mezőkön álló bábukkal.

### Szekér (Bástya)

 ![Szekér bábuk](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Chariots.png)
 
 ![Szekér ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/ChariotDiagram.png)

A *szekér* (vagy más néven: *bástya*) ugyanúgy mozog, mint a sakkban a bástya: akárhány mezőt vízszintesen vagy függőlegesen. A királyt leszámítva ez a legértékesebb bábu.

*Mozgás a palotán belül*: a palotán belül az átlók mentén is tud mozogni.

### Ágyú

![Ágyú bábuk](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Cannons.png)

![Ágyú ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/CannonDiagram_HU.png)

Az ágyú hasonlóan mozog és üt, mint a szekér: akárhány mezőt vízszintesen vagy függőlegesen, de a mozgáshoz és az ütéshez is egy köztes bábura van szüksége, amit "átugrik", és csak az azt követő bábut tudja leütni, vagy csak az azt követő üres mezők valamelyikére tud lépni. Tehát az ágyú a hozzá legközelebbi bábut nem tudja leütni. Ha az ágyú vonalában nincs bábu, akkor az lépni sem tud.

*Fontos szabály*: Az ágyú egy másik ágyút nem tud sem átugrani, sem leütni.

*Mozgás a palotán belül*: a palotán belül az átlók mentén is tud mozogni, ha valamelyik sarokban áll és a palota közepén van egy bábu, amit átugorhat.

### Gyalog

![Gyalog bábuk](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Pawns.png)

![Gyalog ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/PawnDiagram.png)

A *gyalog* előre vagy oldalirányba egyet tud lépni és így is tud ütni.

*Mozgás a palotán belül*: a palotán belül az átlók mentén mentén is mozoghatnak egy mezőt, de csak előrefelé.

## Játszmajegyzés

A koordinátákat csak számokkal jelölik. A kék játékos nézőpontjából a sorok fentről lefelé 1-10-ig vannak számozva, de a 10. sor *0*-val jelölve. Az oszlopok balról jobbra 1-9-es számokkal vannak jelölve. Egy bábu helyét (a legtöbb sakkváltozattal ellentétben) először a *sor* majd az *oszlop* számával határozzuk meg. Például, ha a kék szekér a bal alsó sarokban áll, akkor a **01**-gyel írjuk le a helyét. A felette lévő mező a **91**-es. A kék király kezdőpozíciója a **95**-ös.

A jegyzésnek nincs egy standardizált nemzetközi változata. Az eredeti, koreai jegyzésmódszer a következő: 

**(mező)(a bábu neve koreaiul)(célmező)**

Ezen az oldalon a következő jegyzésmódszer van használatban: 

**(a bábu angol nevének rövidítése)(mező)-(célmező)**

A további jelzések itt is a sakkban már megszokottak:

ütés: **x**

sakk: **+**

matt: **#**

Példa: ha a bal oldali szekér három mezőt lép előre a kezdőhelyéről, akkor azt így jelöljük: **R01-71**. Az "R" a bástya (szekér) angol nevének rövidítése.

### Rövidítések

K = Király

A = Testőr

E = Elefánt

H = Ló

C = Ágyú

R = Szekér (Bástya)

P = Gyalog

## Szabályok: játékmenet

Akárcsak a sakkban, a cél itt is mattot adni a királynak. Más sakkváltozatokkal ellentétben azonban a janggiban passzolni is lehet, így patthelyzet nem alakulhat ki. **Ezen az oldalon úgy lehet passzolni egy játszma közben, hogy a Ctrl gombot lenyomva tartva kattintunk a királyra**.

Amikor a két király szemben áll egymással (egy vonalban), úgy, hogy nincs köztük bábu, akkor a soron következő játékosnak el kell lépnie a királyával vagy a két király közé kell léptetnie egy bábut, különben döntetlennel véget ér a játszma. Ezt a szabályt **bikjang**-nak nevezik. Azokon a versenyeken, ahol a döntetlen nem megengedett, a táblán maradt bábuk értékét összeszámolják és a magasabb értékkel rendelkező játékos nyer.

Jelenleg az oldalon a versenyszabályok vannak érvényben, amik nem engedik meg a döntetlent. Ebből adódóan *bikjang* esetén pontszámításra kerül sor.

Bábu | Érték 
------------ | ------------- 
Szekér | 13
Ágyú | 7
Ló | 5
Elefánt | 3
Testőr | 3
Gyalog | 2

A kék játékos (Cho) kezdi a játszmát, ezért kompenzációként a piros (Han) 1,5 többletpontot kap a játszma elején. Ezt a szabályt úgy nevezik, hogy **deom**. A fél pont a döntetlenek elkerülése végett adódik hozzá a pontszámhoz.

Lehetséges egyszerre sakkot adni és bikjangot előidézni. Ebben az esetben a bikjang élvez prioritást.

A lépésismétlésre és a játszma végére vonatkozó szabályok:
* Az örökös sakkadás nem megengedett, az a játékos, aki folyamatosan sakkot ad, a harmadik ismétlés után veszít.
* A harmadik lépésismétlés után pontszámítással ér véget a játszma.
* Ha 50 lépés alatt egyetlen bábu sem kerül leütésre, akkor pontszámítással dől el a játszma.

## Különbségek a kínai sakkhoz (xiangqi) képest

A fenti szabályokon kívül még:

* A janggiban nincs folyó (ami elválasztja a két oldalt a tábla közepén). Ebből következik, hogy a gyalogok már a kezdettől fogva tudnak oldalra is lépni és nem változtathatók át. Az elefántok teljesen másképp mozognak és itt nincsenek a saját térfelükre korlátozva.
* A bábuk nyolcszög formájúak, nem pedig kör alakúak. Továbbá a nagyságuk attól is függ, mennyire értékesek (pl. a király a legnagyobb, mert az a legértékesebb),
* A táblán a kezdőpozíciók megjelölésére **x**-et használnak, nem pedig keresztet.
* A király a palota közepén kezd, nem a hátuljában.
* Az ágyúnak a lépéshez és az ütéshez is kell egy bábu, amit átugrik (a xiangqiban tud lépni átugrás nélkül is). Az ágyú nem üthet le másik ágyút (a xiangqiban igen).
* A palotán belül a szekér, az agyú és a gyalog is tud az átlók mentén mozogni. 
* A király és a testőrök minden irányban tudnak mozogni (a xiangqiban a testőrök csak átlóban, a király pedig vagy vízszintesen vagy függőlegesen tud lépni).

## Stratégia

[Amphibian Hoplite youtube csatornája (angol nyelvű)](https://www.youtube.com/playlist?list=PL9corMEVRvP-HUJcF7I670pEqV3XNbkKM) nagyon hasznos lehet a kezdőknek.

[Egy másik angol nyelvű videó](https://www.youtube.com/watch?v=pX_ZDjeqlJs), ami az alapvető megnyitásokat mutatja be.

(Megjegyzés: magyar nyelvű tartalomról jelenleg nincs tudomásunk.)

### Általános koncepciók

* A gyalogok struktúrája nagyon fontos. Mivel képesek oldalirányba is lépni, akkor a legerősebbek, ha párban vannak és védik egymást. A hármas csoportba szervezett gyalogok nem előnyösek. Továbbá a gyalogokat itt nem ajánlott előrefelé vinni, ha nem muszáj.

![Rossz gyalogformáció](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/BadPawns.png)

* A játszma kezdetén megválasztott elefánt-ló pozíciók nagyban befolyásolják a megnyitásokat. A külső elefánt képes a tábla közepe felé lépni a két gyalog közé. A belső elefánt számára nincs szabad mező, mert ott állnak a gyalogok (viszont így védi azokat).

* A fentiből következik, hogy az elefánt pozíciója meghatározza azt, hogy **melyik oldalt nyitjuk meg**. Például, ha bal oldalon külső elefánttal játszunk (és az ellenfél szemben lévő elefántja is a külső oldalon van), akkor ajánlott a bal szélső gyalogot oldalra léptetni ezzel megnyitva az utat a szekérnek. Ez azért előnyös, mert az ellenfél szélső gyalogja nem léphet el onnan (hiszen akkor leüthetnénk a szekerét). Ha a másik gyalogját az ágyúja elé lépteti (ezzel is védve a szélső gyalogot), akkor az elefánttal megtámadhatjuk ezt az ágyú előtti gyalogot, hiszen ha a szélső gyaloggal ütné az elefántunkat, akkor megnyílna az út a bal szélen és a szekerünkkel leüthetnénk az ellenfél szekerét.

![Támadó elefánt ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/ActiveElephant2.png)
