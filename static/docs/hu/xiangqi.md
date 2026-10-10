# ![Xiangqi ikon](https://github.com/pychess/pychess-variants/blob/master/static/icons/xiangqi.svg) Xiangqi (Kínai sakk)

![Xiangqi tábla](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Boards.png)

A xiangqi (象棋), avagy a kínai sakk egy klasszikus táblajáték, mely Kínában őshonos és úgy tartják, hogy [csaturangából](https://hu.wikipedia.org/wiki/Csaturanga) eredeztethető, akárcsak a sakk, bár egyesek ezt vitatják, és úgy gondolják, hogy az ellenkezője történt. A játék nem csak Kínában, de Vietnámban is népszerű.

## Miért érdemes megtanulni a kínai sakkot?

Ha élvezed a sakkot, akkor a xiangqit határozottan megéri kipróbálni. Miközben egy kicsit lassabb tempójú és hosszabbra nyúló játék, mint a sakk, a xiangqi nyitottabban indul és az idő előrehaladtával begyorsul, ami gyors végjátékhoz vezethet. A sakkal összevetve a xiangqi inkább taktikai játék (nem annyira a stratégiai). Ahogyan más sakkvariánsok esetében is, a xiangiban szerzett tapasztalat is segíthet fejleszteni a képességeidet a sakkban, és egyben új gondolkodásmódokat is megnyithat. [Erről bővebben itt olvashatsz angol nyelven.](https://en.chessbase.com/post/why-you-need-to-learn-xiangqi-for-playing-better-chess)

## Szabályok

A szabályok hasonlóak a sakkéhoz, így ez az útmutató a különbségekre fókuszál. A két játékos színe itt piros és fekete, hagyományosan pedig az előbbi kezdi a játékot. A cél itt is az ellenfél királyának mattolása, azonban a patthelyzet itt nem döntetlen, hanem a patthelyzetben lévő játékos veszít. Az örökös sakk nem megengedett, az a játékos, aki folyamatosan sakkot ad, a harmadik ismétlés után veszít.

## Tábla

A játékot 9x10-es táblán játsszák, a bábuk pedig a mezők metszéspontjain állnak/mozognak, nem pedig a mezőkön belül. A 3x3-as terület a tábla alján a palota. A király és a testőrei csak a palotán belül tudnak mozogni. A táblát a folyó szeli ketté, ami hatással van a gyalogok és az elefánt mozgására is (ezekről részletesen később).

## Bábuk

A tradicionális készletek a kínai írásjegyeket használják, de a könnyebb érthetőség végett ez az útmutató a nemzetközi bábukészleten alapul (melyen a figurák ábrái láthatók).

### Király

![Király bábuk](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Kings.png)

A király (vagy a kínai neve alapján: tábornok) csak a palotán belül tud mozogni, egy mezőt vízszintesen vagy függőlegesen.

*Speciális szabály*: a két király nem állhat szemben egymással (egy vonalban) úgy, hogy nincs köztük bábu. Ezt a szabályt hasznos ismerni a végjátékban, mert segíthet a mattadásban.

### Testőr

![Testőr bábuk](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Advisors.png)

A testőr csak a palotán belüli átlók mentén léphet egyet, így maximum 5 lehetséges pozíciója van egy testőrnek.

![Király és testőrök ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/KingAdvisorDiagram.png)

### Elefánt

 ![Elefánt bábuk](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Elephants.png)
 
 ![Elefánt ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/ElephantDiagram.png)

Az elefánt csak átlósan tudod mozogni pontosan két mezőt. Az elefánt blokkolható, ha az útjában áll egy bábu, ilyenkor nem tud lépni. További megkötés, hogy az elefánt nem tud átkelni a folyón, ezért csak a saját térfelén képes mozogni.

*Megjegyzés*: a piros játékos bábuja eredetileg nem elefánt, hanem "miniszter", de angol nyelven (és magyarul is) az egyszerűsítés miatt elefántként hivatkozunk rá.

### Ló

 ![Ló bábuk](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Horses.png)
 
 ![Ló ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/HorseDiagram.png)

A ló hasonlóan mozog, mint a sakkban a huszár. Azonban az L-alakzattól eltérően inkább úgy tekintsünk a mozgására, hogy egyet lép vízszintesen vagy függőlegesen, majd átlóban egyet valamelyik irányba, egy Y-alakzatra emlékeztetve. Ennek az az oka, hogy a ló blokkolható, ha egy bábu mellette áll.

### Szekér (Bástya)

 ![Szekér bábuk](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Chariots.png)
 
 ![Szekér ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/ChariotDiagram.png)

A szekér (vagy más néven: bástya) ugyanúgy mozog, mint a sakkban a bástya: akárhány mezőt vízszintesen vagy függőlegesen. A királyt leszámítva ez a legértékesebb bábu.

### Ágyú

![Ágyú bábuk](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Cannons.png)

![Ágyú ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/CannonDiagram.png)

Az ágyú hasonlóan mozog és üt, mint a szekér: akárhány mezőt vízszintesen vagy függőlegesen, de az ütéshez egy köztes bábura van szüksége, amit "átugrik", és csak az azt követő bábut tudja leütni.

### Gyalog

![Gyalog bábuk](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Pawns.png)

![Gyalog ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/PawnDiagram.png)

A gyalog csak előrefelé tud lépni/ütni egyet. Amikor átkel a folyón, akkor képes lesz oldalirányba is lépni/ütni.

## További szabályok: Örökös sakk és üldözés

* Az örökös sakk nem megengedett. Az örökös sakkot adó játékos veszít, ha nem lép mást.
* Az a játékos, amelyik egy védtelenül álló bábut örökösen kerget, veszít. A kivételek ez alól a gyalogok és a királyok, őket lehet üldözni.
* Ha az egyik játékos örökösen sakkot ad, míg a másik örökösen üldöz egy bábut, akkor az örökösen sakkot adónak kell mást lépnie, különben veszít.
* Ha egyik fél sem szegi meg ezeket a szabályokat, de nincs más, alternatív lépésük, akkor a játszma döntetlennel ér véget.
* Ha mindkét fél egyidejűleg szegi meg ezeket a szabályokat, vagy nincs más lépési lehetőségük, akkor a játszma döntetlennel ér véget.

## Játszmajegyzés

Többféle jegyzésmódszer van használatban, ez az oldal a sakkhoz hasonló, algebrai jegyzésmódszert használja.

### Rövidítések

K = Király

A = Testőr

E = Elefánt

H = Ló

C = Ágyú

R = Szekér

P = Gyalog

## Milyen forrásokból tanulhatok még a xiangqiról?

Néhány angol nyelvű forrás (magyar nyelvűek jelenleg nem ismertek):

[xqinenglish.com](http://www.xqinenglish.com/) ideális a kezdőknek. A weboldal tulajdonosa, Jim Png Hau Cheng több könyvet is írt a játékról (pl. a 'Xiangqi Primer' könyvsorozatot), ezek azoknak lehetnek hasznosak, akik magasabb szinten is szeretnének játszani.

[Learning Chinese Chess](https://www.youtube.com/channel/UCXlJz54YEworgVbOFw3_bXg/playlists) youtube csatorna.

A [Club Xiangqi](https://www.clubxiangqi.com/) egy olyan weboldal, ahol erős játékosok ellen lehet játszani (legtöbbjük vietnámi).

## Stratégia

### A bábuk értéke

Bábu | Érték 
------------ | ------------- 
Szekér | 9
Ló | 4
Ágyú | 4,5
Testőr | 2
Elefánt | 2
Gyalog | 1, a folyó átlépése után 2

### Általános alapelvek

* Kezdetben a ló inkább védekező egység, mert túl sok bábu állja az útját. A végjáték felé haladva azonban erősebbé válik, mert akkor már nincs annyi akadály számára. (A sakk huszárjának ellenkezője ebből a szempontból.)
* Az ágyú a játszma elején sokkal erősebb, mert akkor még több bábu van, amiket átugorva támadhat. A végjátékban, amikor már nincs annyi bábu a táblán, a haszna jelentősen csökken.
* Az elefánt szigorúan védelmi egység, támadásban az ágyúnak segíthet (köztes egységként).
* A fentebb elhangzottak értelmében, érdemes a bábukkal blokkolni a lovat és az elefántot.
* A blokkolható bábuk miatt nagyon gyakoriak a felfedett támadások.
* A dupla sakk elég gyakori, főleg a szekér és az ágyú párosításával.

### Megnyitási alapelvek

Az alábbi információk [erről az oldalról származnak](http://www.shakki.info/english/openings.html).

A leggyakoribb megnyitás a "központi ágyú", amikor a király vonalába visszük az ágyút, ezzel nyomás alá helyezve az ellenfelet. A játszmák kb. 70%-a így kezdődik.

![Ágy megnyitás ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/CannonOpening.png)

**A leggyakoribb megnyitások:**

**1. Két lovas védelem**

Ez a leggyakoribb védelem. A cél természetesen, hogy mindkét ló védelmezze a középső gyalogot. Többféle variáció is létezik erre.

![Két lovas védelem ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Screen_Horses.png)

**2. Fan Gong Ma / "Szendvics lovak"**

Az egyik lovat előrehozzuk, de a másik ló léptetése előtt az ágyút a palota közelebbi sarkába visszük, csak ezután következik a másik ló. Így az ágyú a két ló közé kerül. Ez egy viszonylag új megnyitás.

![Fan Gong Ma ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Fan_Gong_Ma.png)

**3. Azonos oldali ágyúk**

A piros játék középre mozgatja az ágyúját, a fekete játékos pedig az ugyanazon oldalon lévő ágyúját viszi középre.

![Azonos oldali ágyúk ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/SameDirectionCannon.png)

**4. Ellentétes oldali ágyúk**

Az előzőnek az ellentettje, amikor a fekete az ellentétes oldalon lévő ágyúját viszi középre.

![Ellentétes oldali ágyúk ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/OppositeDirectionCannon.png)

**5. "A tigris három lépése"**

A fekete játékos gyorsan mozgásba hozza a szekerét azzal, hogy az ágyút a tábla szélére viszi. Ez általában 3 lépésből áll, ebben a sorrendben: a ló előrelép, az ágyú a tábla szélére mozog, aztán a szekér az ágyú kezdővonalába megy.

![A tigris 3 lépése ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Three_Step_Tiger.png)

Az ágyús megnyitásokon kívül a piros játékosnak más opciói is vannak. Ezeket "lágy megnyitásoknak" nevezzük, mert nem járnak azonnali fenyegetéssel.

**Gyalogos megnyitás** - A 2. vagy a 4. gyalog előretolása. Ez egy rugalmas megnyitás, mely segít a piros játékosnak lereagálni a fekete játékos lépését. A fekete játékos általában nem központi ágyúval válaszol, mert utána a piros is a középső vonalra hozhatná az ágyúját, miközben egy előretolt gyaloggal előnyben lenne.

**Elefántos megnyitás** - Ez egy védekező megnyitás, ahol az elefánt kerül a középvonalra az ágyú helyett.

**Lovas megnyitás** - A ló előreléptetése a tábla közepe felé. Innen játszhatók a fentebb már ismertetett lovas védelmek vagy a "tigris három lépése".

Egyéb megnyitások nagyon ritkának számítanak.
