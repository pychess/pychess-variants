# ![Sittuyin ikon](https://github.com/pychess/pychess-variants/blob/master/static/icons/sittuyin.svg) Sittuyin (Burmai sakk)

![Sittuyin ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/SittuyinGuide/Sittuyin.png?raw=true)

A sittuyin (စစ်တုရင်), avagy a burmai sakk egy klasszikus táblajáték, mely Mianmarban őshonos, és habár az ország északnyugati területein még mindig sokan játsszák, mára a nyugati sakk beárnyékolta népszerűségét. A játék kissé lassabb tempójú, de jó lehetőséget ad arra, hogy türelmet gyakoroljunk és a stratégiai gondolkodásunkat fejlesszük.

## Szabályok

A szabályok általánosságban véve nagyon hasonlóak a sakkéhoz (a cél itt is mattolni az ellenfél királyát), ezért ez az útmutató inkább a különbségekre fókuszál. A tábla itt is 8x8-as, de két átlós vonal keresztezi, ami a gyalogok átváltoztatásával van kapcsolatban. A játékosok színe piros és fekete (ez utóbbi zöld is lehet), és a piros lép először. A bábuk pozíciója a sittuyinban a makrukhoz vagy a sakkhoz képest teljesen más. A főbb különbségek:

* A gyalogok lépcsőzetes elrendezésben kezdenek (lásd a fenti képen).
* A játszma elején a játékosok a bábuikat felváltva helyezik a táblára (a saját térfelükön belül). A piros játékos először, aztán a fekete, és így tovább. A szekér csak a leghátsó sorba tehető.
* A gyalogok átváltoztatása másképp működik (erről bővebben később).

Döntetlenre vonatkozó szabályok:

* A játszma döntetlen patthelyzet esetén, amikor a patthelyzetben lévő játékos királya nincs sakkban, de nincs szabályos lépése.
* A játszma döntetlen, ha a játékosok az utolsó 50 lépést úgy tették meg, hogy egyik gyalog sem lépett és nem történt ütés sem.
* Amikor egy játékosnak csak egy királya maradt, akkor életbe lép a lépésszámlálási szabály (az egyedüli király első lépésével indul a számolás). Ha az ellenfél nem tudja mattolni a királyt egy adott lépésszámban, akkor a játszma döntetlen. A lépések száma attól függ, hogy a támadó játékosnak milyen bábui vannak a táblán:

  * Király és szekér	- 16 lépésben kell mattolni
  * Király és elefánt és vezér - 44 lépésben kell mattolni
  * Király és ló és vezér - 64 lépésben kell mattolni
  
Ez a szabály arra ösztönzi a vesztére álló játékos, hogy meneküljön a királlyal és döntetlent próbáljon elérni, ahelyett, hogy feladná a játszmát.

## Bábuk

### Király

![Király ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/SittuyinGuide/King.png?raw=true)

A király ugyanúgy lép és üt, mint a sakkban: egyet bármelyik irányba.

### Vezér

![Vezér ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/SittuyinGuide/General.png?raw=true)

A vezér itt sokkal gyengébb bábu, mint a sakkban, mert csak egy mezőt tud lépni átlóban. Értéke nagyjából 1,5 - 2 gyalognak felel meg. A vezér megfelelő a támadások vezetésére és hasznos lehet az ellenfél fenyegetésére. Ha a vezér leütésre került, egy gyalog átváltoztatásával újabb vezér szerezhető.

### Elefánt

![Elefánt ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/SittuyinGuide/Elephant.png?raw=true)

Az elefánt egy mezőt léphet átlósan, vagy egy mezőt előre (mint a sógiban az ezüsttábornok). Erős bábu arra, hogy az ellőtte lévő mezőket kontrollálja, de a király védelmezésére is megfelelő lehet.

Az elefánt itt értékesebb, mint a vezér, de általánosságban elmondható, hogy kevésbé értékes, mint a ló, mert az elefánt nem tud olyan könnyen elmenekülni a veszélyes helyzetekből, mint a ló.

### Ló

 ![Ló ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/SittuyinGuide/Horse.png?raw=true)

A ló ugyanúgy mozog, mint a sakkban (L-alakzatban és képes átugrani a köztes bábukat). Értékes és erős, központi figura.

### Szekér (Bástya)

 ![Szekér ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/SittuyinGuide/Chariot.png?raw=true)

A szekér ugyanúgy mozog, mint a sakkban a bástya (akárhány mezőt vízszintesen vagy függőlegesen). Erős vezér hiányában a bástya a domináns egység.

### Gyalog

![Gyalog ábra](https://github.com/pychess/pychess-variants/blob/master/static/images/SittuyinGuide/Pawn.png?raw=true)

A gyalog (eredeti fordításban: hűbérúr) ugyanúgy lép, mint a sakkban (egyet előre), és úgy is üt (átlóban előre egyet), azonban első lépésben nem léphet kettőt.

**Átváltoztatás**: Miután a gyalog elér egy olyan mezőt az ellenfél térfelén amin az átlós vonal áthalad, a következő lépésben átváltoztatható vezérré (helyben, vagy átlóban lépéssel, ahelyett, hogy előre lépnénk). 

Megkötések az átváltoztatással kapcsolatban:

* Gyalog csak csak akkor változtatható át, ha előtte a vezérünk már leütésre került.
* Gyalog csak akkor változtatható át, ha azzal nem támadja/üti az ellenfél bábuját. Átlóban ütéssel nem változtatható át, csak átlóban lépéssel üres mezőre.
* Gyalog nem változtatható át, ha ezzel közvetlen vagy felfedett sakkot ad.
* Amennyiben már csak egy gyalog maradt a táblán, az tetszőleges mezőn állva átváltoztatható.
* Az utolsó soron egyedül maradt gyalogot nem kötelező átvátoztatni ha nincs más szabályos lépés, azaz az állás patt.

## Stratégia
 
A játék tempója lassúnak mondható, a legtöbb bábu csak egy mezőt tud lépni valamilyen irányba. Érdemes a bábukat csoportokba szervezni és úgy mozgatni őket, hogy kölcsönös támogatást nyújtsanak egymásnak. Nem érdemes egy időben több frontot megnyitni. A kulcs a megfelelő koordináció.

Egyedül a bástya képes kötést létrehozni. Ezen kívül leginkább a kettős támadás (villa) fordul még elő.
