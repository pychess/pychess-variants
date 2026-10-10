# ![Shogi](https://github.com/pychess/pychess-variants/blob/master/static/icons/shogi.svg) Sógi (Shogi)

![Boards](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Boards.png)

A sógi (将棋), avagy a japán sakk egy klasszikus táblajáték, mely Japánban őshonos és a [csaturangából](https://hu.wikipedia.org/wiki/Csaturanga) eredeztethető, akárcsak a sakk. Modern formájában körülbelül a 16. századtól van jelen. A játék nagyon népszerű Japánban, ahol többen játsszák mint a nyugati sakkot, és a professzionális sógi is virágzó. A játék maga egyszerre hasonló és nagyon más is, mint a nyugati sakk, aztáltal, hogy a leültött bábukat vissza lehet helyezni a táblára.

## Miért érdemes megtanulni sógizni?

Ha élvezed a sakkot, akkor a sógit határozottan megéri kipróbálni. Miközben egy kicsit lassabb tempójú és hosszabbra nyúló játék, mint a sakk, a sógi dinamikusabb és a komplexebb, egészen másféle élményt nyújt. A sógi a sakk és a go között helyezkedik el komplexitás tekintetében, de ne hagyd, hogy ez elriasszon. Ahogyan más sakkvariánsok esetében is, a sógiban szerzett tapasztalat is segíthet fejleszteni a képességeidet a sakkban, és egyben új gondolkodásmódot is adhat. [Erről többet itt olvashatsz angol nyelven.](https://chessbase.in/news/peter-heine-nielsen-on-shogi)


## Szabályok

A szabályok hasonlóak a sakkhoz, így ez az útmutató a különbségekre fókuszál. A sógit egy 9x9-es táblán játsszák. A játékosok felváltva lépnek, a cél itt is az ellenfél királyának mattolása. A sakkal ellentétben a "sötét" játékos (melynek neve *sente* (ejtsd: szente) 先手 , első játékos) lép először, aztán a "világos" játékos (melynek neve *gote* 後手 , második játékos). A színek itt csak jelzésértékűek, nem a bábuk valódi színét tűkrözik.

Jelentős különbség a sakkhoz képest, de hasonló a Crazyhouse variánshoz, hogy a leütött bábukat vissza lehet helyezni a táblára egy-egy lépés helyett. Vannak behozási szabályok (különösen a gyalogok esetében, amiről később lesz szó), de általánosságban elmondható, hogy bárhova el lehet helyezni a bábukat. Továbbá, szinte minden bábut át lehet változtatni. A bábuk akkor változtathatók át, amikor elérik az átváltoztatási zónát (az utolsó három sort), vagy már ebben a zónában/zónából lépnek. A bábu ekkor átfordul (az átváltoztatott felét mutatva). A leütött bábuk az eredeti (nem átváltoztatott) formájukban kerülnek a játékoshoz, illetve így is helyezhetők vissza a táblára.

## Bábuk

Ez az útmutató a nemzetközi bábukészleten alapul. A tradicionális készletek a kínaiktól átvett írásjegyeket, azaz kandzsikat használnak, és a bábukészletek vagy 2 kandzsival, vagy rövidített formában 1 kandzsival vannak ellátva. Jelenleg a kandzsik ismerete szükséges ahhoz, hogy minden angol nyelvű forrást fel tudj használni a tanuláshoz. (Megjegyzés: ezek legtöbbje magyar nyelven nem is érhető el).

Általánosságban elmondható, hogy a sógibábuk mozgása sokkal korlátozottabb, mint a sakkbábuké. A könnyűtisztek inkább előrefelé mozoghatnak, hátrafelé sokkal kevésbé.

Az átváltoztatott bábukat a legtöbb készlet pirossal különbözteti meg (többek között az ezen az oldalon használtak is). Két alapvető szabály van ami segít abban, hogy a bábuk megtanulása sokkal könnyebb legyen. A gyalogok és a könnyűtisztek aranytábornokká változtathatók át. Ebből következik, hogy az aranytábornok már nem átváltoztathatók át. A nehéztisztek (a bástya és a futó) a király lépéslehetőségeit is megkapják átváltoztatás után (az eredeti lépéseiken felül). A király természetesen nem változtatható át.


### Király

![BlackKings](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/BlackKings.png)

![WhiteKings](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/WhiteKings.png)

![KingDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/King.png)

A király pontosan ugyanúgy lép, mint a sakkban: egy lépés bármelyik irányba. A kandzsi készleteknél a "vonással" jelölt király az "alacsonyabb rangú játékos" királya (玉將 gyokushō), a sötét játékosé. A "vonás" nélküli király a "magasabb rangú játékos" királya, a világos játékosé.

A nemzetközi készletben ez az egyetlen bábu, amely megtartotta az eredeti, kandzsival jelzett formáját. Ebben a készletben a "sötét" játékos bábuja sötét, a "világos" játékos bábuja pedig világos hátterű. A famintázatú készletben ennek megfelelően egy sötés vagy világos vonal látható a 王 kandzsi alatt.

### Bástya (Szekér)

![Rooks](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Rooks.png)

![RookDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Rook.png)

A bástya pontosan ugyanúgy mozog, mint a sakkban: tetszőleges számú mezőt függőlegesen vagy vízszintesen. A nemzetközi bábu egy szekeret ábrázol, ami a bábu eredeti japán nevére utal: "égi szekér". Ez a legértékesebb alapbábu a királyt leszámítva.

### Futó

![Bishops](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Bishops.png)

![BishopDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Bishop.png)

A futó pontosan ugyanúgy mozog, mint a sakkban: akárhány mezőt átlósan. A nemzetközi bábu egy egy tradicionálisan kalapot ábrázol, amit a japán tisztek hordtak. Ez a második legértékesebb alapbábu a királyt leszámítva.

### Sárkánykirály (Sárkány, átváltoztatott bástya)

![Dragons](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Dragons.png)

![DragonDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Dragon.png)

A sárkánykirály az átváltoztatott bástya, mely megkapja a király lépéslehetőségeit is a bástya lépésein felül. Ez a legértékesebb bábu a királyt leszámítva.

### Sárkányló (Ló, átváltoztatott futó)

![Horses](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Horses.png)

![HorseDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Horse.png)

A sárkányló az átváltoztatott futó, mely megkapja a király lépéslehetőségeit is a futó lépésein felül. Ez a második legértékesebb bábu a királyt leszámítva.

Megjegyzés: A sakkban a huszárt szokták lónak is nevezni, de a sógiban a ló a sárkányló rövidített elnevezése. Nem összekeverendő az L-alakzatban mozgó lovassal.


### Aranytábornok (Arany)

![Golds](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Golds.png)

![GoldDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Gold.png)

Az aranytábornok lépései szokatlannak tűnhetnek elsőre. Talán a legkönnyebb úgy megjegyezni, hogy egyet léphet vízsintesen vagy függőlegesen, vagy átlósan előre egyet. A nemzetközi készletben a sisak hegyes részei (és az aranyszínű kör a sisak tetején) a lehetséges lépések irányait szimbolizálják.

**Minden alapbábu (a bástya és a futó kivételével) aranytábornokká változtatható.**

### Ezüsttábornok (Ezüst)

![Silvers](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Silvers.png)

![SilverDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Silver.png)

Az ezüsttábornok lépései szokatlannak tűnhetnek elsőre. Talán a legkönnyebb úgy megjegyezni, hogy egyet léphet átlósan, vagy egyet előre. A nemzetközi készletben a sisak élei a lehetséges lépések irányait szimbolizálják.

### Lovas

![Knights](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Knights.png)

![KnightDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Knight.png)

Hasonló a sakk huszárjához, de annál kötöttebb a mozgása: csak előrefelé tud mozogni, azaz két mezőt lép előre és egyet balra vagy jobbra. A sakk huszárjához hasonlóan a lovas is át tudja ugrani a köztes bábukat.

### Lándzsás (Lándzsás szekér)

![Lances](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Lances.png)

![LanceeDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Lance.png)

A lándzsás tetszőleges számú mezőt léphet előre. Hasonló a bástyához, de oldalirányba illetve visszafele nem léphet.

### Gyalog

![Pawns](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawns.png)

![PawnDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawn.png)

A gyalog csak előre léphet egyet, és csak így üthet. Ebben különbözik a sakk gyalogjától.

### Átváltoztatott könnyűtisztek

![PSilvers](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PSilvers.png)

![PKnights](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PKnights.png)

![PLances](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PLances.png)

![Tokins](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Tokins.png)

Az átváltoztatott bábuk (a sárkánykirályt és a sárkánylovat leszámítva) úgy lépnek, mint az aranytábornok.

A sárkánykirályt és a sárkánylovat leszámítva csak az átváltoztatott gyalognak van más neve, ezt a bábut úgy nevezik, hogy **tokin**. 


## További szabályok

*Visszahelyezés / Behozás*
1) Gyalog nem helyezhető vissza a táblára egy olyan oszlopra, amelyen az adott játékosnak már van egy másik gyalogja. Tehát két saját gyalog nem lehet egy oszlopban (kivéve, ha a másik egy átváltoztatott gyalog, azaz *tokin*).
2) Behozott gyaloggal nem lehet mattod adni, de sakk adható.
3) Nem helyezhető vissza bábu olyan mezőre, ahonnan utána nem lenne szabályos lépése. Ez általában az utolsó sort jelenti, vagy az utolsó kettőt a lovas esetében.

*Örökös sakk*: Ha négyszer megismétlődik az állás és ezáltal a sakkadás, akkor a folyamatosan sakkot adó játékos veszít.

*Lépésismétlés*: Hasonlóan az előzőhöz, ha négyszer megismétlődik ugyanaz az állás (beleértve a leütött, azaz kézben lévő bábukat is), akkor döntetlennel ér véget a játék.

*Időmérés*: A sógiban úgynevezett bjójomi (byo-yomi) (visszaszámlálás) is része az időmérésnek. Amikor egy játékos ideje letelik, akkor következik a bjójomi, azaz onnantól mindig egy fixen meghatározott ideje marad egy-egy lépésre (pl. 30 másodperc). Ha lép, akkor ez az idő újra rendelkezésre áll majd a következő lépésben, ha kifut az időből, akkor elveszíti a játszmát.

### Játszmajegyzés és koordináták

Különféle jegyzésmódszerek vannak használatban, ezen az oldalon a Hodges-jegyzést használjuk, ami a sakkban is használt algebrai jegyzésmódszerből ered. Szembetűnő különbség a sakkhoz képest, hogy a koordináták fel vannak cserélve. Az oszlopok számokkal, a sorok pedig betűkkel vannak jelölve. Például a világos (második játékos) királya az 5a mezőn áll. (Ez a *Hodges*-jegyzés)

A *Hoskings*-jegyés során a betűk helyett is számok vannak, tehát pl. az 5e helyett 55-ot jegyzünk, ami az 5. sort és 5. oszlopot jelenti. Ez hasonló a japánok jegyzésmódszeréhez, ahol szintén csak számokat használnak.

### Bábuk

K = király

G = aranytábornok

S = ezüsttábornok

N = lovas

L = lándzsás

R = bástya

B = futó

P = gyalog

+R vagy D = sárkánykirály (átváltoztatott bástya)

+B or H = sárkányló (átváltoztatott futó)

+S, +N, +L, +P jelölések a fenti bábuk átváltoztatott formáját jelenti.

### Szimbólumok

* A behozások jelölése egy **\*** vagy egy **‘** karakterrel történik. Mi a **\*** karaktert használjuk (Hodges-jegyzés). Például egy gyalog behozásának jelölése **P\*5e** lenne.
* Azok a lépések, melyek átváltoztatással végződnek egy **+** karakterrel vannak jelölve. Például ha egy gyalog az 1c mezőre érkezve átváltozik, akkor annak a jelölése **P1c+**.
* Ha a bábut nem változtatunk át, akkor azt egy **=** karakterrel jelöljük. Például ha az ezüsttábornok üti *5c*-t és nem változtatjuk át, akkor annak a jelölése **Sx5c=**
* A sakk és a matt nincs jelölve.

## Források a sógi megtanulásához

[YouTube: Hidetchi](https://www.youtube.com/playlist?list=PL587865CAE59EB84A): kiváló csatorna kezdőknek és haladóknak egyaránt. Angol nyelvű, de részletes magyarázatokkal szolgál. A kandzsis bábukat ismerni kell a videók megértéséhez, de azokat is bemutatja a kezdőknek szóló videókban.

[Youtube: Shogi Harbour](https://www.youtube.com/channel/UCRnXG7CkKfEN6IINKcO_uBg/videos): Karolina Styczyńska, egy Japánban élő lengyel profi játékos csatornája. Weboldala a [shogi.pl](http://www.shogi.pl)

[81dojo.com](http://www.81dojo.com) az egyik legnagyobb sógi oldal, ahol tapasztaltabb játékosok ellen játhatsz a világ minden tájáról. Gép elleni, illetve "levelező" játékra nincs lehetőség.

## Stratégia

### A bábuk értéke

A bábuknak nincs egy "standard" értéke, mint a sakkban. Érdemes azt is megjegyezni, hogy ezek az értékek nem annyira fontosak, hiszen a leütött bábuk visszahozhatók a játszmába és a jól felépített állás sokkal fontosabb lehet. Ennek ellenére van egy alap értékrendszer, de a profi játékosok is kialakították a saját értékrendszerűket. Az alábbiakban Kōji Tanigawa és Yasumitsu Satoh értéktáblázata látható.


Bábu | Alap | Tanigawa | Satoh 
------------ | ------------- | ------------- | -------------
P | 1 | 1 | 1
L | 3 | 5 | 6
N | 3 | 6 | 6
S | 5 | 8 | 10
G | 5 | 9 | 11
B | 7 | 13 | 17
R | 8 | 15 | 19
*+B* |  | 15 | 20
*+R* |  | 17 | 22
*+P* |  | 12 | 
*+L* |  | 10 | 
*+N* |  | 10 | 
*+S* |  | 9 | 


### Megnyitási alapelvek

Általánosságban kétféle megnyitási módszerről beszélhetünk: *statikus bástya* és *mozgó bástya*. A statikus bástya esetétben a bástya a kezdőhelyén marad megnyitáskor, ezáltal a támadás a tábla jobb oldalára koncentrálódik. A mozgó bástya esetében a bástya középre vagy a bal oldalra lép, ott támogatva a támadást. Ez a különbség azért is fontos, mert a megnyitási lépések (*dzsoszeki*, 定跡) általában ebbe a két osztályba vannak sorolva, és drasztikusan más játékstílust eredményezhetnek.


### A védelem kiépítése

A védelem kiépítése a sógiban több lépést vesz igénye (és nem lehet sáncolni, mint a sakkban). A megfelelő védelem kiépítése nagyon fontos, mert a gyengén védett király nagyon gyorsan támadhatóvá válik a behozott bábukkal. Fontos ismerni a kiépített védelmek erősségeit és gyengeségeit.

A védelem kiépítése a statikus vagy mozgó bástya megnyitástól is függ. A statikus esetében a király számára a tábla bal oldalán kerül kialakításra a védelem, míg a mozgó bástya esetében a tábla jobb oldalán. Sokféle védelem van, melyeket [Hidetchi be is mutat a youtube csatornáján](https://www.youtube.com/playlist?list=PL587865CAE59EB84A) (angol nyelven). A három legfontosabb védelem, amit fontos ismerni:


**Yagura (Erőd)**

![Yagura](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Yagura.png)

A Yagura az egyik legerősebb védelem, amikor mindkét játékos statikus bástyát játszik. A kialakításhoz jó emlékeztető lehet, ha ezt a pozíciót megjegyezzük: “S G | G B”. A Yagura erős védelem szemből, de oldalirányból már gyengébb.

A Yagura kialakításához érdemes megjegyezni, hogy a leghatékonyabb, ha a tábornokok átlóban mozognak. Többféle dzsoszeki is létezik a védelem kialakítására, de fontos észben tartani, hogy az ellenfél bármikor támadásba lendülhet, amire a védelem kialakítása közben reagálni kell. Egy 24 lépéses standard dzsoszeki például így néz ki ([forrás: Hidetchi](https://www.youtube.com/watch?v=h7jPat3_WG4)):

1. ☗P-7f
2. ☖P-8d
3. ☗S-6h
4. ☖P-3d
5. ☗P-6f
6. ☖S-6b
7. ☗P-5f
8. ☖P-5d
9. ☗S-4h
10. ☖S-4b
11. ☗G4i-5h
12. ☖G-3b
13. ☗G-7h
14. ☖K-4a
15. ☗K-6i
16. ☖P-7d
17. ☗G5h-6g
18. ☖G-5b 
19. ☗S-7g
20. ☖S-3c
21. ☗B-7i
22. ☖B-3a
23. ☗P-3f
24. ☖P-4d

Ezzel még nem teljes a védelem, a királynak és a futónak további lépésekre van szüksége.


**Mino védelem**

![Mino Castle](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Mino.png)

A Mino egy klasszikus mozgó bástyás védelem a statikus bástya ellen (de alakalmazható más esetekben is). A király a bástya kezdőhelyére mozog, a bal oldali aranytábornok egyet átlóban jobbra, a jobb oldali ezüsttábornok pedig egyet előre lép, hogy egy "G G S" formáció alakuljon ki V-alakzatban. Ez a védelem erős bal oldalon, de gyengébb a szemből érkező támadások ellen.

Példa megnyitás a "sötét" játékosnak a 4. mezőre mozgó bástya esetében:

* P-7f
* B-7g (védi a 8f mezőt) 
* P-6f (védekezik a futók cseréje ellen, ha a "világos" játékos megnyitná az utat a futójának)
* R-6h (4. mezőre lépő bástya)
* S-7h 
* K-4h -> K-3h -> K-2h (a bástya kezdőhelyére mozog a király)
* S-3h (az ezüsttábornok előre mozog)
* G6i-5h (a bal oldali aranytábornok jobb átlóban előre lép)
* P-1f (menekülési útvonalat nyit a királynak)

**Anaguma**

![Anaguma](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Anaguma.png)

Az Anaguma ("Medvebarlang") egy másik mozgóbástyás védelem, amikor a király a jobb sarokban bújik meg. Ez az egyik legnehezebben áttörhető védelem, azonban sok időbe telik kialakítani. 

Kialakítható a másik oldalon is, amikor statikus bástyával játszuk, ilyenkor a király a bal sarokban bújik meg.

**Kétszárnyú támadás**

Nem egyfajta védelem, hanem egy statikus bástya megnyitás (ami ellen védekezni kell). Mindkét fél előretolja a bástyája előtti gyalogot mely kölcsönös leütéshez (cseréhez) vezet. A dzsoszeki része, hogy az ezüsttábornoknak védenie kell a futó előtti gyalogot, mielőtt az ellefél bástya előtti gyalogja elérné azt.

## Előnyadás

Az előnyadás fontos része a tanításnak és nem úgy kell rá tekinteni, mintha egy játékos könyörületet tanusítana ellenfele irányába. Nagyszerű módja a játék megtanulásának és vannak "standard" stratégiák is a kölönböző előnyadásos játszmákra.

Míg normál esetben a "sötét" játékos (*sente*) lép először, az előnyadásos játszmákban a "világos" játékos kezd. Az előnyadás ellenére az anyag miatti különbség kiküszöbölhető a behozási szabály miatt.

A leggyakoribb előnyadások:

Név | Hiányzó bábu(k)
-- | --
Lándzsás | bal oldali lándzsás
Futó | futó
Bástya | bástya
Bástya-Lándzsás | bástya és a bal oldali lándzsás 
2 bábu | bástya, futó
4 bábu | bástya, futó, mindkét lándzsás
6 bábu | bástya, futó, mindkét lándzsás, mindkét lovas
8 bábu | bástya, futó, mindkét lándzsás, mindkét lovas, mindkét ezüsttábornok
9 bábu | bástya, futó, mindkét lándzsás, mindkét lovas, mindkét ezüsttábornok, bal oldali aranytábornok
10 bábu | bástya, futó, mindkét lándzsás, mindkét lovas, mindkét ezüsttábornok, mindkét aranytábornok

<iframe width="560" height="315" src="https://www.youtube.com/embed/AVSLOcdDj1M" frameborder="0" allowfullscreen></iframe>
