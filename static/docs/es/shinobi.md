# ![Ajedrez Shinobi](https://github.com/pychess/pychess-variants/blob/master/static/icons/shinobi.svg) Ajedrez Shinobi

![Shinobi](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Shinobi.png)

El Ajedrez Shinobi es una variante de Ajedrez diseñada en 2021 por Couch Tomao con ayuda de Fables, cuarto en las series de juegos asimétricos. El ejército de Ajedrez occidental ("el Reino", las Negras) ha invadido la tierra del Clan Sakura (Sakura/Rosas). Aunque comienza con muchas piezas débiles, el Clan tiene muchos recursos y puede instanáneamente reclutar nuevos aliados para defender en situaciones de apuro. El Clan comienza con muchas piezas en mano que pueden ser soltadas en su mitad del tablero. A mayores, pueden promocionar al llegar al final del tablero - estas habilidades son similares al Shogi, con la gran excepción de que las piezas capturadas no van a la mano del jugador, por lo que ¡cada pieza soltada cuenta! El juego en sí mismo es increiblemente balanceado según el ordenador (más incluso que el ajedrez estándar) con un ratio aproximado de 50%/50% de victorias para Reino y Clan.
 
## Reglas Generales
1.	La posición es como se muestra arriba; el jugador del Clan comienza con piezas adicionales en mano.
2.	El Clan (Sakura/Rosas) siempre mueve primero.
3.	Las piezas en mano del Clan solo pueden ser soltadas en las cuatro primeras filas (primera mitad del tablero).
3.	Todas las piezas menores del Clan pueden promocionar cuando llegan a la séptima fila. De modo similar, los Peones del Reino promocionan en la séptima fila en vez de la octava.
5.	Los Peones de ambos bandos pueden promocionar solamente a Capitanes (ver más abajko).
6.	Existe un método adicional de victoria: el **camp mate**. El camp mate se consigue moviendo el propio rey a la última fila sin ponerse en jaque.
7.	Ahogado y repeticiones son ambas derrotas.
8.	El Clan no puede enrocar.
9.	El resto de reglas, incluyendo movimientos del Reino y capturas al paso, son como en Ajedrez Internacional estándar.

Una nota acerca de la promoción. La promoción es opcional si la pieza todavía se puede mover después. Si la pieza no se puede mover después (por ejemplo, un Peón llegando a la octava fila), la promoción es obligatoria. Como en Shogi, si comienzas un movimiento desde la zona de promoción, tienes también la opción de promocionar.

## Piezas del Clan

Hay cinco nuevas unidades en el Clan: el Ninja, el Dragón, las Lanzas, los Caballos de Madera, y los Monjes. Los Capitanes también son una nueva pieza disponible para ambos bandos, pero solo el Clan comienza con uno en el tablero. No te dejes intimidar; todas estas piezas tienen movimientos que son muy similares a las piezas originales del Ajedrez. El Ninja y el Dragón son las piezas más especiales del Clan, mientras que las otras piezas son esencialmente una versión debilitada de sus contrapartidas en el Reino. El Ninja, el Dragón y los Capitanes no promocionan.
El Clan también tiene acceso a las piezas Torre, Alfil y Caballo del Reino a través de la promoción. El Rey del Clan se llama Kage (K) y tiene un símbolo diferente, pero el cambio es puramente estético y temático: se comporta igual que un Rey ortodoxo. Las Torres y Alfiles del Clan tienen un aspecto distinto, pero los cambios son también únicamente estéticos.

### Capitán (C)

![Capitán](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ClanCaptain.png)

El Clan comienza con un Capitán en el lugar de la Dama. Ambos bandos pueden obtener Capitanes adicionales promocionando sus Peones en la séptima fila. El Capitán tiene el mismo movimiento que un Rey. Por supuesto, a diferencia del Rey, capturar un Capitán no termina el juego.

### Ninja (J)

![Ninja](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Ninja.png)

El Ninja es una pieza híbrida que combina los movimientos del Alfil y el Caballo. En muchas variantes se conoce a esta pieza como el Cardenal. El Ninja es la pieza más fuerte del Clan y es una pieza muy peligrosa que puede penetrar las defensas enemigas muy fácilmante. ¡El Ninja es también la única pieza capaz de dar jaque mate por sí sola! El Ninja es ligeramente inferior a la Dama.

El Ninja no promociona.

### Dragón (D)

![Dragón](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Dragon.png)

El Dragón es una pieza híbrida que combina los movimientos de la Torre y el Rey (o para los puristas, Torre y Ferz). Es idéntica al Rey Dragón (Torre promocionada) del Shogi. El Dragón es más débil que el Ninja, pero más fuerte que la Torre.

El Dragón no promociona.

### Lanza (L)

![Lanza](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Lance.png)

La Lanza es como una Torre pero solamente puede mover hacia adelante. Es idéntica a la Lanza de Shogi. Una Lanza comienza en mano y podemos pensar en ella como una enfilada soltable. Dado que no puede retroceder, ¡asegúrate de que valga la pena soltarla! Las Lanzas que empiezan en el tablero son menos flexibles y sirven para controlar el tablero. La Lanza promociona a una Torre al llegar a la séptima fila (opcionalmente) o a la octava (de forma obligatoria). La Lanza vale menos que la típica pieza menor del Reino; sin embargo, su valor oculto reside en su capacidad de promocionar a una de las piezas más fuertes del juego.

### Caballo de Madera (H)

![Caballo de Madera](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Horse.png)

El Caballo de Madera es como un Caballo pero solamente puede mover a las dos casillas más avanzadas. Es idéntica al Caballo en Shogi. Un Caballo de Madera comienza en mano y puede pensarse en él como un ataque doble soltabler. Dado que no puede retroceder, ¡asegúrate de que valga la pena soltarlo! Los Caballos de Madera que empiezan en el tablero pueden ejercer una presión similar, pero deben ser avanzados con cuidado ya que no pueden retroceder. El Caballo de Madera promociona a un Caballo al llegar a la séptima u octava filas (siempre de forma obligatoria). El Caballo de Madera vale menos que la típica pieza menor del Reino; sin embargo, su valor oculto reside en su capacidad de promocionar a un Caballo.

### Monje (M)

![Monje](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Monk.png)

El Monje mueve una casilla en diagonal, tanto hacia adelante como hacia atrás. En otras variantes, esta pieza es conocida como Ferz/Fers. Los monjes pueden promocionar a Alfiles cuando llegan a la séptima u octava filas. El Monje es más débil que la típica pieza menor del Reino; sin embargo, su valor oculto reside en su capacidad para promocionar a un Alfil.
 
## Estrategia
El juego todavía es reciente, así que el conocimiento estratégido está en desarrollo. La mayoría de información está basada en el juego del ordenador.

Los valores de las piezas son difíciles de evaluar dada la capacidad de promoción de las diversas piezas. Nótese que la valoración de Stockfish puede no ser muy precisa al comienzo de la partida debido a dichas promociones. Sin embargo, el juego es bastante equilibrado.

### Aperturas

No existe un análisis completo. Sin embargo, Fairy Stockfish abre mayormente con **1. J@c3 Nc6**. Después de ello, hay mucha variedad en las aperturas que emplea.
