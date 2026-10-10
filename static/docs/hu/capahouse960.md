# ![Capahouse960](https://github.com/pychess/pychess-variants/blob/master/static/icons/Capahouse960.svg) Capahouse 960

A Capahouse 960 egy sakkvariáns, ami a Capablanca-sakkot kombinálja a Crazyhouse behozási szabályaival és a Sakk960 (más néven Fischer random sakk) szabályaival.

Mivel ez a játék a Capablanca-sakk egy változata, annak szabályai az arra vonatkozó leírásban megtalálhatók. 

Ezt a játékot egy Capahouse játszma indítása előtt a 960-as opciót bepipálva lehet játszani.

A 960 és a Crazyhouse szabályai emlékeztetőnek:

## Crazyhouse szabályok

A leütött bábuk saját bábuként visszahelyezhetők a táblára, ezt nevezzük behozási szabálynak. Egy bábu behozása lépésnek számít. A jegyzés során a behozást **@** karakterrel jelöljük, tehát pl. egy leütött bástya visszahelyezése az e4 mezőre: **R@e4**.

 Behozási (visszahelyezési) szabályok:

* Bábut nem lehet úgy behozni, hogy az azonnal mattot adjon.
* Gyalogot nem lehet az utolsó sorba behozni (mert utána nem lenne szabályos lépése).
* Egy átváltoztatott gyalog (pl. vezér) leütés után visszaváltozik gyaloggá és csak úgy lehet újra játékba hozni.
* A 2. sorba (fehér esetén) és a 7. sorba (fekete esetén) visszahelyezett gyalogok nem léphetnek kettőt első lépésként.
* Behozott bástya nem sáncolhat.

## A 960 szabályai

A hátsó sor bábui véletlenszerűen vannak összekeverve két szabály betartásával:

A két futó nem állhat azonos színű mezőn (tehát az egyik egy világos, a másik pedig egy sötét mezőn áll, mint a standard sakkban).
A királynak egy olyan mezőn kell állnia, ami a két bástya között van.
A sötét bábuk a megfelelő világos bábukkal szemben kezdenek.

A sáncolás a standard sakk szabálya szerint működik, azaz mindegy, hogy a bástya melyik mezőn áll, a sáncolás során a király és a bástya ugyanarra a mezőre érkezik, mint a standard sakkban. Ha például a király a vezérszárnyra sáncol, akkor a c1 mezőre érkezik, a bástya pedig a d1 mezőre.
