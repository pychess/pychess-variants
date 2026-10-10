# ![960](https://github.com/pychess/pychess-variants/blob/master/static/icons/960.svg) Chess960 (Fischer’s Random Chess)

Chess960 a été créé par Bobby Fischer pour rendre le jeu plus variable et supprimer une grande partie de la mémorisation par cœur des ouvertures à laquelle les échecs standard vous obligent. C'est l'une des variantes les plus populaires, et elle séparera ceux qui maîtrisent vraiment la stratégie et les tactiques de ceux qui comptent sur la mémorisation des lignes d'ouverture.

Cette variante peut être jouée en cochant l'option "960" lors de la création d'une partie d'échecs standard.

## Règles

Les rangées initiales sont composées aléatoirement, en respectant les contraintes suivantes :

* Les fous doivent être placés sur des cases de couleurs différentes.
* Le roi doit être placé entre les tours.

Le roque est l'autre règle majeure à prendre en compte. Fondamentalement, peu importe où se trouvent les tours, si vous roquez la position finale sera la même que si les tours étaient en position standard. Par exemple, un grand roque avec initialement une tour en b1 et un roi en c1 sera déclenché en "capturant la tour" avec le roi, et résultera en un unique déplacement de tour puisque le roi est déjà à sa place.

Toutes les autres règles sont inchangées.

## Stratégie

Les tactiques et strétégies usuelles s'appliquent, sauf dans l'ouverture ! Puisque la position initiale est aléatoire, les débuts habituels n'existent pas.
[https://nine-sixty.netlify.app/](https://nine-sixty.netlify.app/) par visualdennis est recommendé pour tout le monde.
