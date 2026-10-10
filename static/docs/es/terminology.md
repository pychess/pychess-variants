# Terminología

A lo largo del sitio y en las guías, se utilizan muchos términos diferentes. La mayoría de ellos son globales y se aplican a todas las variantes de Ajedrez, algunos se aplican solo en algunas (byo-yomi), y otros tienen diferentes connotaciones dependiendo de la variante (por ejemplo el "ahogado"). Cualquier término que se aplica a una variante concreta será discutido aquí (por ejemplo muchos términos del Shogi). ¡Usa esta página para aclarar cualquier confusión!

# "Variantes de Ajedrez"

Probablemente el término más importante que aclarar en primer lugar sea el de "**variante de Ajedrez**". No hay duda de que juegos como el Pasapiezas o el Crazyhouse son variantes de Ajedrez, porque derivan del Ajedrez. Sin embargo, juegos regionales como el Xiangqi, Shogi, Janggi y Makruk también son etiquetados como "variantes de Ajedrez", y esto puede causar confusión.

La librería más grande de variantes de Ajedrez, chessvariants.com, tiene un artículo entero dedicado al tema de ["¿Qué es una variante de ajedrez?"](https://www.chessvariants.com/what.html). En Pychess, compartimos los mismos sentimientos. Por brevedad, digamos que "variante de Ajedrez" significa cualquier juego de estrategia por turnos, derivado del Chatturanga, donde las piezas tienen movimientos diferentes, y el objetivo es capturar o "matar" al Rey rival. Aunque las variantes orientales no derivan del Ajedrez, tienen un ancestro común y todos sus nombres para el juego significan "ajedrez". De este modo, el "Ajedrez" en "variante de ajedrez" representa un concepto más general de juego que el definido por la FIDE. Esto es análogo a los deportes, donde la palabra "football" tiene un significado diferente en distintas regiones.

Dado que "variante de ajedrez" puede denotar tanto variantes basadas en el Ajedrez internacional, como cualquier forma de "ajedrez" (el término más general), hay una pequeña ambigüedad aquí. La mayoría de las veces se puede entender por el contexto a qué variante nos estamos refiriendo. Aún así, es una desventaja de tener este término ambiguo, y quizás en el contexto de discusión de todos los tipos de ajedrez, se podrías usar un término más general como "variantes parecidas al ajedrez". Sin embargo, no es la terminología estándar a día de hoy.

# Piezas

**Piezas de fantasía** - Una pieza que no se utiliza en Ajedrez convencional, con la palabra "fantasía" significando "inventada". No está claro si las piezas nativas de las variantes regionales deben considerarse "piezas de fantasía", pero preferimos no usar este término para juegos establecidos. Sin embargo, un Cañón del Xiangqi que aparece en una variante (como en el Shako), o un Alfil que aparezca en una variante del Xiangqi, cuentan como "piezas de fantasía" porque no forman parte del juego nativo.

Nótese que varias piezas tienen el mismo tipo (movimientos/capturas), pero diferentes nombres. Por ejemplo, la "Torre" y el "Carruaje" se refieren a la misma pieza. El nombre debe reflejar el nombre usado en el juego que se está jugando.

## Clasificación

Dado que las piezas de fantasía introducen docenas de piezas posibles, hay un sistema de clasificación para las piezas. También hay notaciones usadas para describir los movimientos, aunque esto queda fuera del alcance de esta página. Hay tres tipos de piezas simples:

**Jinetes ("Riders")** (también denominadas piezas de rango) son piezas que pueden seguir moviendo en una dirección hasta que son obstruidas por otra pieza o llegan al borde del tablero. La Torre y el Alfil de Ajedrez son ejemplos clásicos.

**Saltadores ("Leapers")** son piezas que tienen movimientos fijos que no pueden ser obstruidos. El Caballo de Ajedrez es un ejemplo clásico. El Caballo en Xiangqi y Janggi es un Saltador modificado porque puede ser bloqueado. Piezas similares también son denominadas a veces "saltadores cojos".

**Brincadores ("Hoppers")** son piezas que deben saltar por encima de otra pieza antes de poder mover o capturar. No hay brincadores en Ajedrez, pero el Cañón del Xiangqi (captura ortogonalmente saltando primero sobre otra pieza) así como un Cañón diferente del Janggi (mueve y captura ortogonalmente saltando antes sobre otra pieza) son ejemplos clásicos de brincadores. (Nótese que técnicamente el Cañón del Xiangqi es un híbrido Jinete-Brincador dado su movimiento de rango y su captura de brincador, mientras que el Cañón de Jinetes sería un brincador puro)

Finalmente, las **piezas compuestas** son piezas que combinan los movimientos de dos piezas simples. La Dama de Ajedrez, que combina los movimientos de la Torre y el Alfil, es un ejemplo clásico. Muchas piezas de fantasía son piezas compuestas.

# Control de tiempo

Los controles de tiempo determinan las restricciones de reloj que gobiernan el final de una partida cuando un jugador toma excesivo tiempo para mover. Un tipo de partida, denominado **por correspondencia**, utiliza controles de tiempo largos de al menos varias horas, normalmente días. Los jugadores suelen hacer sus jugadas cuando tienen un hueco en su día. Actualmente el juego por correspondencia no está disponible en Pychess, donde las partidas están pensadas para ser jugadas completamente de una vez.

Las partidas jugadas de una vez usan un reloj principalmente que normalmente va de 1 minuto a 60 minutos, donde cada jugador tiene su propio reloj. Un jugador puede tener o no tiempo extra a lo largo de la partida. Hay tres tipos principales de reloj que dictan cómo asignar el tiempo extra:

1. **Incremento (Fischer)** - Cada vez que un jugador termina su turno, se le añade una cantidad de tiempo fija a su reloj. Una partida en Pychess etiquetada como "10+15" quiere decir que hay 10 *minutos* iniciales en el reloj, y un incremento de 15 segundos. Este es el control de tiempo estándar usado en la mayoría de variantes.

2. **Byo-yomi** - (término japonés para cuenta atrás) Una vez que el reloj principal del jugador termina, tiene una cantidad de tiempo fija disponible para cada jugada a partir de ahí. Este sistema se utiliza en Shogi y Janggi. Se pueden usar múltiples periodos de byo-yomi, normalmente en Janggi. Por ejemplo, si hay 3 periodos, entonces el jugador puede agotar el reloj 2 veces sin perder (la tercera vez perderá). Esto puede ser útil en una jugada crítica, donde un periodo único de byo-yomi puede no ser suficiente para evaluar la situación con cuidado. Una partida de Pychess etiquetada como "10+3x30(b)" quiere decir 10 *minutos* iniciales, y después 3 periodos de byo-yomi de 30 segundos.

3. **Muerte súbita ("Sudden death")** - No hay tiempo extra. Un juego que usa incremento o byo-yomi puede ser jugado con muerte súbita ajustando la respectiva barra de increment/byo-yomi a 0 segundos.

# Conceptos Generales

**Jaque** - Amenazar al Rey contrarion con una pieza que lo capturaría en el siguiente turno si el rival no lo evita.

**Jaque mate** - El objetivo principal del ajedrez, dar un jaque del cual no se pueda escapar con ninguna jugada legal. El jugador que recibe jaque mate pierde.

**Ahorago** - Cuando el Rey no está en jaque, pero el jugador no tiene jugadas legales. En Ajedrez, esto son tablas, pero en muchas variantes (como el Xiangqi), supone la derrota del bando que es ahogago.

**Repetición** - Cuando el estado del tablero se repite, normalmente al menos tres veces. Se suele producir cuando las piezas se persiguen unas a otras. Diferentes variantes gestionan las repeticiones de forma distinta. Incluso dentro del mismo juego, diferentes federaciones tienen reglas distintas para la repetición.

**Jaque perpetuo** - Es como la repetición, pero un jugador continúa dando jaque al Rey rival y eventualmente repitiendo la misma posición. Las reglas para el jaque perpetuo varían de forma similar entre variantes y federaciones.

**Fila** - Una fila en el tablero.

**Columna** - Una columna en el tablero.

**Notación** - Sistema usado en cada partida para referirse a las posiciones del tablero, abreviaturas de las piezas, así como movimientos de cada turno.

**Notación Algebraica Estándar (Standard Algebraic Notation - SAN)** - La notación usada en Ajedrez. Cada jugada se describe por la abreviatura de la pieza movida (excepto el Peón), seguida de las coordenadas de la casilla destino. Algunas letras adicionales se añaden para resolver ambigüedades.

**Jugada** - Una jugada en Ajedrez consiste en un movimiento por ambos jugadores. Sin embargo, en Shogi, describe el movimiento de cada jugador. En Ajedrez, puedes tener "mate en 1" o 2, o 3, etc. Pero en Shogi solamente puedes tener mate en 1, 3, 5, 7, etc.

**Soltar ("drop")** - Un movimiento que consiste en usar una pieza capturada como propia colocándola de nuevo en el tablero. Es la base de variantes como Shogi o Crazyhouse, pero no existe en Ajedrez. Las variants que permiten soltar piezas se denominan "variantes de soltar" ("drop variants" en inglés) y hay varias en Pychess (normalmente con el sufijo "house")

**Zona de Promoción** - La zona del tablero en que las piezas pueden promocionar. En Ajedrez solamente los Peones pueden promocionar en la última fila. Sin embargo, en Shogi, la zona de promoción son las últimas tres filas, y la mayoría de piezas pueden promocionar. Otras variantes tienen distintas zonas de promoción.

# Táctica

**Ataque doble ("Fork")** - Atacar dos piezas al mismo tiempo. Los Caballos suelen hacer este tipo de táctica en todas las variantes. En variantes de soltar, las Torres y Alfiles también son un poco más capaces de hacer ataques dobles, sobre todo los Alfiles.

![Ejemplo de ataque doble](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Fork.png)

**Clavada** - Atacar una pieza de tal forma que no se puede mover, pues de hacerlo expondría a otra pieza más valiosa detrás (normalmente el Rey).

![Ejemplo de clavada](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Pin.png)

**Enfilada** - Similar a una clavada, se trata de atacar dos piezas en una misma línea, pero con la pieza más valiosa enfrente. La pieza más valiosa es forzada a moverse, permitiendo al atacante capturar la segunda pieza ahora expuesta.

![Ejemplo de enfilada](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Skewer.png)

**Ataque descubierto** - Una de tus piezas estaría atacando a una pieza enemiga desde su posición, pero el ataque está bloqueado por una pieza propia. Moviendo esta pieza que bloquea (normalmente generando con ella una segunda amenaza), se abre el ataque de la primera, y se denomina ataque descubierto o ataque a la descubierta. Los ataques a la descubierta son especialmente frecuentes en Xiangqi.

![Ejemplo de ataque descubierto](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Discovery.png)

En esta situación, mover el Caballo para amenazar a la Dama también descubre un jaque al Rey con la Torre. Dado que las Negras deben responder al jaque, las Blancas serán capaces de capturar la Dama.

**Sacrificio** - Perder material a cambio de obtener una ventaja en la posición.

![Ejemplo de sacrificio](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Sacrifice.png)

En este ejemplo, si la Dama Blanca captura al Caballo Negro, puede ser capturada fácilmente por un Peón. Sin embargo, esto permitiría al Caballo dar jaque mate (flecha Roja). La Dama ha sido sacrificada para obtener una recompensa mayor.
