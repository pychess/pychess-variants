# ![Orda ikon](https://github.com/pychess/pychess-variants/blob/master/static/icons/orda.svg) Orda sakk (Horda sakk)

![Orda ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Orda.png)

![Orda ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/OrdaLegend_HU.png)

Az Orda sakk egy sakkvariáns, amit [*Couch Tomato*](https://github.com/CouchTomato87) tervezett 2020-ban. A cél egy asszimetrikus sakkjáték megteremtése volt két különböző sereggel. A játékot [Ralph Betza sakkvariánsa](https://en.wikipedia.org/wiki/Chess_with_different_armies) inspirálta, de a cél az volt, hogy a játék tematikája is visszaköszönjön a játékmenet során. A tematika ebben az esetben a Mongol Birodalom lovas hadseregei, melyeket Hordának (Ordának) hívtak. Ebből következik, hogy a Horda mozgása a huszárlépésen alapul, így az erősebb egységek L-alakzatban lépnek. A játékban a Horda aranyszínű, ez az [Arany Hordát](https://hu.wikipedia.org/wiki/Arany_Horda) szimbolizálja, mely a Mongol Birodalom része volt.

A másik fél a standard sakkból ismert készlettel játszik, fehér színnel, ezt a készletet jelen esetben *Királyság*nak nevezzük, hogy a tematikába jobban illeszkedjen.
 
## Általános szabályok
1. A kezdőállás a fenti képen látható. Az új bábuk ellenére a Horda bábui a standard sakk bábuit tükrözik (az előretolt gyalogsor kivételével).
2. A közös tulajdonságú bábuk a két sereg között a gyalogok és a királyok (a Horda királyát *Kán*nak nevezzük).
3. A Királyság (fehér) lép először.
4. A Horda (arany) nem sáncolhat.
5. Mivel a Horda gyalogjai a 3. sorban kezdenek, ezért nekik nincs lehetőségük kettőt lépni, illetve *en passant* sem lehet őket leütni. A Királyság gyalogjai a sakkból már ismert módon léphetnek kettőt kezdetben, illetve *en passant* is leüthetők.
6. Mindkét sereg gyalogjai csak vezérré vagy kesikké változtathatók át.
7. Egy új módja is van a győzelem megszerzésének, melyet úgy nevezünk, hogy **tábormatt**. Ez akkor következik be, ha a saját királyunkat az utolsó sorba (az ellenfél táborába) bevisszük, anélkül, hogy ott sakkban lenne.
8. A többi szabály, mint pl. a patt illetve a lépésismétlés ugyanúgy érvényben van itt is.

## Horda bábuk
Négy sajátos egysége van a Hordának: a lándzsás, a lovas íjász, a jurta és a kesik. Ez utóbbi viszont kivétel, mert a Királyság kesikhez juthat egy gyalog átváltoztatása által. A kesik a Horda legerősebb egysége (huszár + király kombinációja). A jurta relatíve gyenge egység a vezérhez képest (egyet átlóban vagy előre tud lépni/ütni). A Horda királyának neve **kán**, mely ugyanúgy lép és üt, mint a sakk királya, az egység sajátos neve és kinézete pusztán esztétikai, hogy a tematikába jobban illeszkedjen. A lándzsás és az íjász abból a szempontból egyediek, hogy másképpen lépnek és másképpen ütnek. Mivel a Horda lovas hadseregen alapul, ezért a lándzsás és az íjász is huszárlépésben (L-alakzat) mozog. Azonban a lándzsás úgy üt, mint a bástya (vízszintesen és függőlegesen), az íjász pedig úgy üt, mint a futó (átlóban).

**Horda** bábu	| Lépés | Ütés | Megfelelője a standard készletben (**Királyság**)
-- | -- | -- | -- 
Jurta | “Egyet átlóban vagy előre” | “Egyet átlóban vagy előre” | Vezér
Íjász | Huszár | Futó | Futó
Lándzsás | Huszár | Bástya | Bástya
Kesik | Huszár+Király | Huszár+Király | Huszár

A részletes ábrák lentebb. A zöld pontok a lépést jelölik, a pirosak az ütést a sárgák pedig mindkettőt.
 
### Jurta (Y)

![Jurta ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Yurt.png)
 
A *jurta* (angolul: *yurt*) egyet lép/üt átlóban vagy előre (ugyanúgy, mint az ezüsttábornok a sógiban). Ebből a bábuból csak egy van a táblán, a vezér vonalában, de a vezérrel ellentétben az a leggyengébb bábu a gyalogot leszámítva. Ugyanakkor nem kell alábecsülni, mert ugyanúgy tud lépni és ütni is, és hasznos lehet a gyalogok védelmezésére.

A jurta a mongolok mobilizálható otthona volt. A seregek támogatásában is fontos szerepe volt, ezt hivatott szimbolizálni ez a bábu.

### Kesik (H)

![Kesik ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Kheshig.png)
 
A *kesik* (angolul: *khesig*) egy hibrid bábu, amely a huszár és a király lépés- és ütéslehetőségeivel is rendelkezik. (Ez a bábu *kentaur* néven is ismert más, nem standard sakk készletekben). A huszárral egyvonalban kezd és a Horda legerősebb egysége. Kettő van belőlük és érdemes vigyázni rájuk, mert fontos szerepük van a közép- és végjátékban.

A *kesik*ek a mongol uralkodói családok elit testőrsége volt. Ennek megfelelően, a játékban *kán* mattolása rendkívül nehéz anélkül, hogy legalább az egyik kesik leütésre kerülne.

### Lovas íjász (A)

![Lovas íjász ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Archer.png)
 
A lovas íjász (vagy röviden csak *íjász*) (angolul: *archer*) L-alakzatban lép (mint a huszár), de átlóban üt (mint a futó). Mivel az íjász mozgása nem kötődik mindig azonos színű mezőhöz, ezért értékesebb, mint a futó.

A lovas íjászok a mongol sereg egyik alapvető egységei voltak. A bátorságuk és a sebességük (mint lovasok) komoly fenyegetést jelentettek.
 
### Lándzsás (L)

![Lándzsás ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Lancer.png)
 
A lándzsás (angolul: *lancer*) L-alakzatban lép (mint a huszár), de vízszintesen vagy függőlegesen üt (mint a bástya). A lándzsás általánosságban a bástyánál gyengébbnek tekinthető, ami a végjátékban hangsúlyos lehet, hiszen ütés hiányában kevesebb mezőt tud lépni, mint a bástya. A játszma elején azonban, amíg a bástya nem tud olyan gyorsan támadásba lendülni, a lándzsás a mozgása miatt előnyös lehet, amit érdemes kihasználni.

A lándzsások a mongol sereg egyik alapvető egységei voltak az íjászok mellett.
 
## A bábuk értéke

A pontos értékek nem ismertek. Az alábbi értékek a számítógép (Fairy-Stockfish) által használt értékek és nem feltétlenül Orda-specifikusak.

Királyság | Érték (korai / késői) | Horda | Érték (korai / késői)
-- | -- | -- | --
Gyalog | 120 / 213	| Gyalog | 120 / 213
Vezér | 2538 / 2682	| Jurta | 630 / 630
Futó | 825 / 915	| Lovas íjász	| 1100 / 1200
Huszár | 781 / 854	| Kesik | 1800 / 1900
Bástya | 1276 / 1380	| Lándzsás | 1050 / 1250

Vagy egyszerűsített értékekkel kifejezve (megközelítőleg):

Királyság	| Érték | Horda	| Érték
-- | -- | -- | --
Gyalog | 1	| Gyalog | 1
Vezér	| 9	| Jurta | 2
Futó | 3 | Lovas íjász | 4
Huszár | 3 | Kesik | 7
Bástya | 5 | Lándzsás | 4

## Stratégia

A játék még friss, tehát még nincsenek kiforrott stratégiák. Az adatok nagy része a számítógépes (Fairy-Stockfish) játszmákon illetve elemzéseken alapulnak.

A Horda kánja nem sáncolhat. Azonban a Horda megnyitások alapvető összetevője a kán g7-re juttatása, ideálisan az első négy lépésen belül. A számítógép a játszmák 56%-ban Kf7-tel nyitott.

A Királyság számára a d4, g3 és a b3 a leggyakoribb megnyitás, ebben a sorrendben.

A Horda legnagyobb gyengesége, hogy a lándzsások és az íjászok nem tudják fenntartani a fenyegetést, hiszen ha közben őket támadják és vissza kell lépniük, elveszítik az előző ütési lehetőségüket (az eltérő ütések és lépések miatt). Ezt a Királyságnak fontos kihasználni a játszma során.

### Megnyitások

Az alábbiak az első néhány lépés elemzésén alapulnak, melyeket a számítógép (Fairy-Stockfish) játszott önmaga ellen.

Fehér = Királyság

Arany = Horda

Fehér megnyitás	| Játszmák % (db) | Fehér győzelem % | Arany győzelem % | Arany válaszlépés
-- | -- | -- | -- | --
d4 | 38%	(47) | 45% | 38% | Kf7 ~= c5 >> Hb7
g3	| 24% (30)	| 33% | 43% | Kf7 >> d5
b3 | 14% (18) | 33% | 44% | Kf7 >> Lc7
e3 | 11% (14) | 50% | 50% | Kf7 ~50%-ban
d3 | 6% (8) | 25% | 25% | e5 ~=Kf7
Nf3 | 3% (4) | 25% | 50% | e5 minden esetben
e4 | 2% (3) | 33% | 67% | d5
c4 | 1% (1) | 100% | 0% | Kf7

Alább a leggyakoribb megnyitások. Az utolsó, zárójelbe tett lépések azok, ahol leginkább elkezdődnek a variációk.

**Benkő megnyitás** - Leggyakoribb megnyitás
1. g3 Kf7
2. e4 Kg7
3. (Bd3 vagy Nf3) ...

![Benkő megnyitás ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/BenkoCastle.png)

*Kán védelmezése a g7-re lépéssel*

**Stockfish védelem - Zárt variáció**
1. d4 c5
2. dxc5 *bxc5*
3. c4 Kf7
4. (Nc3) ...

**Stockfish védelem - Nyílt variáció**
1. d4 c5
2. dxc5 *dxc5*

**Stockfish védelem - Vezérszárnyon támadás**
1. d4 c5
2. *e3* cxd4
3. exd4 b5
4. b3 Kf7
5. c4

![Stockfish Védelem Vezérszárny ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/QueensidePush.png)
