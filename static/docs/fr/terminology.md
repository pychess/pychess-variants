# Terminologie

Sur ce site, y compris dans les guides, on trouve partout des mots et des expressions peut-être moins connus, tout en faisant partie du lexique des variantes d'échecs que vous trouverez ici ou ailleurs. Certains termes sont d'usage global ; d'autres se voyent utilisés seulement dans le cadre de quelques jeux en particulier (ex. le *byô-yomi* pour le shogi) ; encore d'autres s'appliquent pour plusieurs jeux, mais sont de sens différent selon le jeu (ex. le concept du *pat*). Tout terme qui est spécifique à une variante particulière sera discuté à la page consacré à ladite variante. Ceci dit, cette page sera une référence pour démystifier tout le reste du lexique des variantes d'échecs.

# "Variantes d'échecs"

Il vaut mieux d'abord clarifier ce que l'on entend par une **variante d'échecs**. Si l'on pense au jeu d'échecs classique à l'occident, des jeux comme le Blitz à 4 et le Crazyhouse, basés sur les échecs occidentaux, valent evidémment l'appellation "des variantes d'échecs". Moins évidents sont les jeux régionaux comme le xiangqi (échecs chinois), le shogi (échecs japonais), le janggi (échecs coréens) et le makruk (échecs thaïlandais), qui sont parfois appelés aussi des variantes d'échecs, bien qu'ils ressemblent à peine aux échecs occidentaux.

Sur le grand site des variantes d'échecs, chessvariants.com, il y a un article entièrement dédié au sujet [« Qu'est-ce qu'une variante d'échecs ? » (en anglais)](https://www.chessvariants.com/what.html). Ici sur Pychess, nous sommes du même avis. Nous proposons que par le terme **variante d'échecs** nous entendons tout jeu de stratégie au tour par tour, dérivé du chaturanga, où les différentes types de pièces possèdent des mouvements distincts, et dont le but est de mater le roi (ou son analogue) adverse. Les jeux d'échecs d'Asie ne sont pas dérivés des échecs occidentaux ; pourtant, ils ont tous un ancestre commun (à savoir le chaturanga), et sont tous considérés *le* jeu d'échecs dans leur pays.

Remarquons que ainsi, le mot « échecs » ne s'agit pas que du jeu d'échecs réglé par la FIDE mais à un concept abstrait d'un jeu d'« échecs ». Le terme « variante d'échecs » comprend aussi donc des variantes basées sur le xiangqi ou le shogi, par exemple. Nous utilisons alors le terme « jeu d'échecs » sans qualification pour designer n'importe quelle variante d'échecs régionale de manière générale. Si l'on veut parler d'une variante en particulier, on la precisera.

# Pièces

**Pièce féerique** -- Toute pièce qui n'est pas dans les échecs occidentaux, le mot « féerique » ayant le sens de « inventée, pas ordinaire ». Il n'est pas évident si des pièces appartenant aux échecs régionaux sont considérées « féeriques », mais nous préférons considérer qu'elles ne le sont pas dans le contexte de leur jeu d'origine. Pourtant, un canon du xiangqi apparaissant dans un variante des échecs occidentaux (voir le Shako) ou bien une dame dans une variante du shogi seront « féeriques », n'étant pas présentes dans le jeu de base.

On note bien que certaines pièces sont identiques mais s'appellent différemment dans des variantes différentes. Par exemple, la tour des échecs occidentaux et le chariot du xiangqi sont les mêmes. Il sera mieux d'utiliser le nom d'une pièce propre à la variante dont il est question.

## Classification

Parce qu'il existe des centaines de pièces féeriques, il en existe aussi un système de classification. Des [systèmes de notations pour décrire leurs mouvements](https://en.wikipedia.org/wiki/Fairy_chess_piece#Notations) existent aussi, mais ce n'est pas notre sujet ici. Abordons trois catégories de pièces « simples » :

**Coureurs** peuvent se déplacer dans le même sens et direction indéfiniment, jusqu'à ce qu'ils atteignent une case occupée. La tour (coureur orthogonal) et le fou (coureur diagonal) des échecs occidentaux sont des exemples canoniques. Aux problèmes d'échecs féeriques, la noctambule (*Nightrider* en anglais) est un autre exemple très connu, un coureur dans le sens d'un cavalier.

**Bondisseurs** peuvent faire un bond entre leur case de départ et leur case d'arrivée, sans être empêchés par aucune pièce en route. L'exemple classique est le cavalier aux échecs occidentaux. Le cheval du xiangqi et du janggi est un bondisseur qui par contre peut être bloqué en route, parfois appelé un *bondisseur décomposé* (parce que son bond peut être décomposé en deux parties, avec une case au milieu ou la pièce peut se faire bloquer). L'éléphant du janggi en est un autre exemple.

**Sauteurs** se déplacent comme des coureurs, mais doivent sauter par-dessus une pièce pendant leur trajectoire. Le canon du janggi (sauteur orthogonal) est l'exemple canonique ; au monde de problèmes d'échecs occidentaux, il y a la Sauterelle (comme une Dame, pourtant ce n'est pas un coureur mais un sauteur).

En plus, des pièces **hybrides** combine à la fois deux mouvements simples. Par exemple, la dame aux échecs occidentaux combine les mouvements d'une tour (coureur orthogonal) et d'un fou (coureur diagonal). Le canon du xiangqi se déplace (sans capture) comme une tour (coureur orthogonal), mais il ne capture qu'en sautant (sauteur orthogonal). Beaucoup de pièces féeriques sont des hybrides.

# Cadence du jeu

La cadence du jeu, aussi appelé le contrôle du temps, s'agit des limitations de temps de réflexion accordés aux joueurs ; si on le dépasse, on perd la partie. Il en existe plusieurs types.

Les parties **correspondance** fixent une durée maximale pour chaque coup joué, typiquement de l'ordre de quelque jours par coup. Elles ne sont pas offertes sur Pychess en ce moment, où les parties sont censées être jouées en une seule session.

Les parties jouées en une session précisent souvent une durée de temps principale pour achever la partie, typiquement entre 1 et 60 minutes. Chaque joueur a son propre horloge qui affiche le temps qu'il lui reste ; il ne décompte que pendant son tour. Selon le contrôle du temps, le joueur pourrait gagner plus de temps pendant la partie. Il y a trois types de cadence qui règlent si et comment ce temps en plus est donné :

1. **Incrément (cadence Fischer)** -- Quand un joueur termine son tour, il gagne une durée de temps fixe. Sur Pychess, une partie de « 10+15 » indique un temps principal de 10 minutes chacun au début, et un incrément de 15 secondes par coup joué. Le cadence Fischer et le standard pour la majorité des variantes.

2. ***Byô-yomi*** -- Ce terme vient du japonais, littéralement « comptage de secondes ». Quand un joueur a dépensé tout son temps principal, commence la phase de byô-yomi. Le joueur aura une nouvelle limitation : un temps maximal par coup à ne pas dépasser. Ce système est utilisé pour le shogi et le janggi. Il existe aussi la possibilité d'avoir plusieurs périodes de byô-yomi, typiquement pour le janggi. Par exemple, s'il y a trois périodes de byô-yomi de 30 secondes chacune, chaque joueur a le droit de finir son temps principal, puis dépasser la limite de 30 secondes par coup deux fois. La troisième fois qu'il utilise plus que 30 secondes pour un coup, il perd. Les périodes se voyent commodes face à une position critique, où une seule période ne serait pas suffisante pour bien évaluer la situation. Sur Pychess, une partie de « 10+3x30(b) » indique un temps principal de 10 minutes, puis trois périodes de byô-yomi de 30 secondes.

3. **Mort subite** -- Il n'y a pas de temps en plus ; les joueurs n'auront que le temps principal pour achever la partie. Une peut se jouer en morte subite en choissisant un íncrément ou byô-yomi de 0 secondes.

# Concepts généraux

**Échec** -- Une menace sur le roi adverse avec une pièce qui pourrait le prendre le tour suivant.

**Mat** -- Le but principal du jeu d'échecs, où le roi ne peut s'échapper d'un échec. Le joueur qui se fait mater, perd.

**Pat** -- Quand le roi n'est pas en échec, mais le joueur n'a aucun coup légal. Aux échecs occidentaux, le pat conduit à une partie nulle, mais pour certaines variantes (ex. le xiangqi), le joueur qui s'est mis en pat, perd.

**Répétition** -- Quand une position apparaît plusieurs fois (souvent trois fois). L'état du jeu comprend les pièces, la position sur l'échiquier, le côté à jouer, et les droits au pouvoirs spéciaux (ex. le roque). Des jeux différents statuent différemment sur la répétition ; par exemple elle amène à partie nulle aux échecs occidentaux, mais elle est interdite au janggi (en parties officielles). Même pour le même jeu, des fédérations différentes peuvent statuer différement (ex. le xiangqi en Chine et le xiangqi en Asie de Sud-Est).

**Échec perpetuel** -- Comme la répétition, mais où un joueur donne des échecs sans cesse. Encore une fois, les règles concernant l'échec perpetuel diffèrent selon la variante et la fédération qui le gouverne.

**Rangée** -- Une ligne de cases horizontale sur le plateau.

**Colonne** -- Une ligne de cases verticale sur le plateau.

**Notation** -- Le(s) système(s) pour noter la position sur l'échiquier, l'abbréviations des pièces (ex. D = Dame, C = Cavalier), ainsi que les coups joués.

**Notation algébrique (Standard Algebraic Notation, SAN)** -- Le système de notation utilisé pour les échecs occidentaux. Chaque coup est noté par la pièce qui est joué, suivi par sa case d'arrivée. Des caractères additionnels sont utilisés pour enlever des ambiguïtés, si nécessaire.

**Coup** -- Un *coup complet* comprend deux *demi-coups* ou deux mouvements, un par chaque joueur. Cependant, au shogi, la définition de « coup » correspond à celle de « demi-coup », d'où la notion de « *tsume* en 1/3/5/7 coups » correspondant à « mat en 1/2/3/4 coups » aux échecs occidentaux. Une subtilité de langage.

**Parachutage** -- Quand on replace une pièce adverse prise sur l'échiquier en tant que la sienne, cet acte constitue un coup de parachutage. Il est la mécanique centrale du shogi et du crazyhouse. Des variantes qui permettent le parachutage s'appellent des « drop variants » en anglais (variantes avec du parachutage), dont plusieurs sont offertes sur Pychess (celles avec le suffix « -house »).

**Zone de promotion** -- La région de l'échiquier où les pièces peuvent se promouvoir. Aux échecs occidentaux, seuls les pions ont droit de promotion, et seulement en atteignant la dernière rangée. Au shogi, la zone de promotion contient les trois dernières rangées, et presque toutes les pièces peuvent se promouvoir en entrant, en sortant ou en se déplaçant dans la zone de promotion. D'autres variantes pourraient définir leurs propres zones de promotion.

# Tactiques

**Fourchette** -- Une double attaque d'une pièce sur deux pièces. Dans beaucoup de variantes, le cavalier est par excellence la pièce qui donne des fourchettes. Dans des variantes avec le parachutage, les fous et les tours sont aussi doués.

![Fork example](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Fork.png)

**Clouage** -- L'attaque d'une pièce coureure sur une autre pièce, de telle sorte que la pièce attaquée ne peut s'échapper sans ouvrir la ligne d'attaque vers une pièce plus importante derrière (souvent le roi).

![Pin example](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Pin.png)

**Enfilade** -- Comme un clouage, mais la pièce la plus importante est devant.

![Skewer example](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Skewer.png)

**Attaque (à la) découverte** -- Une pièce coureure est empêchée d'attaquer une pièce adverse à cause d'une pièce alliée qui s'interpose. En déplaçant la pièce intervenant (qui elle-même pourrait menacer d'autres choses, par ailleurs), la ligne de la pièce coureure est ouverte et elle attaque la pièce adverse, d'où le nom (l'attaque était couverte ; on découvre l'attaque). Cette tactique arrive souvent au xiangqi.

![Discovered attack example](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Discovery.png)

Dans cette situation, on bouge le cavalier afin de menacer la dame noire, en même temps en découvrant un échec sur le roi noir par la tour. Comme les noirs doivent répondre à l'échec, les blancs gagnent ainsi une dame.

**Sacrifice** -- Une perte de matériel pour une compensation d'une autre sorte, souvent une meilleure position.

![Sacrifice example](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Sacrifice.png)

Dans cet exemple, si la dame blanche prend le cavalier noir, elle sera attaquée par le pion noir. Toutefois, les blancs pourraient ensuite donner mat avec le cavalier (flèche rouge). La dame se serait sacrifiée pour une compensation beaucoup plus grande.
