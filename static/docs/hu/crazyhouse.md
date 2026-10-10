# ![Crazyhouse ikon](https://github.com/pychess/pychess-variants/blob/master/static/icons/Crazyhouse.svg) Crazyhouse

A Crazyhouse egy népszerű sakkvariáns, ahol a leütött bábuk saját bábuként visszahelyezhetők a táblára (mint a sógiban). Ez teljesen más játékhoz vezet, mint a standard sakk.

## Szabályok

A leütött bábuk saját bábuként visszahelyezhetők a táblára, ezt nevezzük behozási szabálynak. Egy bábu behozása lépésnek számít. A jegyzés során a behozást **@** karakterrel jelöljük, tehát pl. egy leütött bástya visszahelyezése az e4 mezőre: **R@e4**.

 Behozási (visszahelyezési) szabályok:

* Bábut nem lehet úgy behozni, hogy az azonnal mattot adjon.
* Gyalogot nem lehet az utolsó sorba behozni (mert utána nem lenne szabályos lépése).
* Egy átváltoztatott gyalog (pl. vezér) leütés után visszaváltozik gyaloggá és csak úgy lehet újra játékba hozni.
* A 2. sorba (fehér esetén) és a 7. sorba (fekete esetén) visszahelyezett gyalogok nem léphetnek kettőt első lépésként.
* Behozott bástya nem sáncolhat.

## Stratégia

(Az eredeti szöveg forrása a [Lichess](https://lichess.org/variant/crazyhouse))

* A gyalogok és a huszárok relatív értéke magasabb a Crazyhouse-ban, míg a bástya, a vezér vagy a futó relatív értéke alacsonyabb. Például ha a király sakkot kap a kettő vagy több mező távolságban lévő bábutól, akkor a király védelmére visszahelyezhetünk egy gyalogot a tűzvonalba. A huszárt viszont így sem lehet blokkolni, ezért nagyon értékes támadó egység.
* Ha a vezérek már korán kölcsönösen leütésre kerültek, nem ajánlott őket túl korán újra játszmába hozni, amennyiben azok más bábuk által könnyen támadhatóvá válnak.
* A gyalogok behozásával az ellenfél területére könnyen olyan helyzetek teremthetők, amikor a gyalog egyszerre két értékesebb egységet támad, vagy esetleg sakkot ad.
