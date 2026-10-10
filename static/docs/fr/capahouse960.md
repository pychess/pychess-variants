# ![Capahouse960](https://github.com/pychess/pychess-variants/blob/master/static/icons/Capahouse960.svg) Capahouse 960

Capahouse960 est une variante combinant les règles des échecs Capablanca, Crazyhouse et Chess960, dont toutes les règles s'appliquent. Comme cela est considéré comme un dérivé des échecs Capablanca, veuillez lire les règles de cette variante dans son guide séparé. Les règles de Crazyhouse et Chess960 sont les suivantes pour rappel.

Cette variante peut être jouée en cochant l'option "960" lors de la création d'une partie Capahouse.

## Règles du Crazyhouse

Au lieu d'effectuer un coup normal, on peut parachuter une pièce adverse capturée sur l'échiquier. En notation algébrique, le parachutage est noté par une arobase (@). Par exemple, R@e4 indique une tour parachutée sur la case e4. Les règles gouvernant le parachutage sont les suivantes :

* Il est permis de donner échec et mat avec un parachutage, même avec un pion (contrairement au shogi).
* Il est illégal de parachuter un pion sur la 1ère ou la 8ème rangée.
* Un pion promu puis capturé se parachutera en tant que pion.
* Un pion blanc (resp. noir) parachuté sur la 2ème rangée (resp. 7ème rangée) peut avancer de deux cases lors de son premier coup après être parachuté.
* Il est illégal de roquer avec une tour parachutée.

## Règles 960

Les rangées initiales sont composées aléatoirement, en respectant les contraintes suivantes :

* Les fous et évêques doivent être placés sur des cases de couleurs différentes.
* Le roi doit être placé entre les tours.

Le roque est l'autre règle majeure à prendre en compte. Fondamentalement, peu importe où se trouvent les tours, si vous roquez la position finale sera la même que si les tours étaient en position standard.
