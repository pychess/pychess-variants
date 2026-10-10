# ![Shogi](https://github.com/pychess/pychess-variants/blob/master/static/icons/shogi.svg) Shogi

![Boards](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Boards.png)

El *Shogi* (将棋), o Ajedrez Japonés, es un juego de tablero clásico nativo de Japón y es descendiente cercano del Chaturanga, el mismo antepasado común al ajedrez. En su forma moderna, ha estado presente desde el siglo XVI. El juego es muy popular en Japón, donde se juega más que el Ajedrez occidental y tiene una escena profesional en alza. El juego es a la vez similar y diferente al Ajedrez occidental, introduciendo la capacidad de soltar piezas capturadas de nuevo en el tablero.

## Por qué aprender Shogi?

Si disfrutas del Ajedrez, definitivamente vale la pena probar el Shogi. Aunque es ligeramente más lento que el Ajedrez, el juego también es más dinámico y complejo, llevando a una experiencia totalmente diferente. El Shogi se encuentra entre el Ajedrez y el Go en términos de complejidad, pero no permitas que ello te desanime. Al igual que otras variantes, mejorar tus habilidades en Shogi también te puede ayudar a mejorar tus habilidades en Ajedrez, así como abrir tu mente a nuevas formas de pensamiento. [Lee esto para más información al respecto.](https://chessbase.in/news/peter-heine-nielsen-on-shogi)

## Reglas

Las reglas son similares al Ajedrez, así que esta guía se centrará en las diferencias. El Shogi se juega en un tablero de 9x9. Los jugadores toman turnos moviendo piezas para intentar dar jaque mate al rey enemigo. El jugador negro, o *sente* (先手 primer jugador), mueve primero, seguido por el blanco, o *gote* (後手 segundo jugador), al contrario que en Ajedrez. Estos colores son arbitrarios y no reflejan el color real de las piezas.

Una diferencia importante con respecto al Ajedrez, pero similar al Crazyhouse, es que puedes soltar las piezas capturadas en el tablero como piezas propias en vez de hacer un movimiento normal. Hay unas pocas restricciones a la hora de soltar peones, que comentaremos más adelante, pero en principio las piezas pueden ser soltadas en cualquier casilla. Las piezas son promocionadas en cuanto entran en la zona de promoción / campo enemigo (últimas tres filas) o al mover una pieza que ya estaba en el campo enemigo. Cuando capturas una pieza que había sido promocionada, vuelve a tu mano en su forma original no promocionada.

## Piezas

Esta guía se basará en el juego de piezas internacionalizado. Los juegos tradicionales usan caracteres Chinos, *kanji*, y los juegos de piezas vienen o bien en forma completa (2-kanji) o abreviada (1-kanji). A día de hoy necesitas tener conocimiento de estos kanji si quieres utilizar los recursos que puedes encontrar en inglés.

En general, las piezas de Shogi son mucho menos flexibles que las de Ajedrez. Las piezas menores (es decir, no la Torre ni el Alfil) suelen moverse hacia adelante en general.

Acerca de las piezas promocionadas, la mayoría de juegos de piezas, incluyendo los utilizados en este sitio, las distinguen coloreándolas en rojo. Hay dos reglas básicas que harán el aprendizaje de las piezas **mucho más** sencillo. Todas las piezas *menores* mueven como un General de Oro cuando se promocionan. En segundo lugar, las dos piezas *mayores* (Torre y Alfil), ambas ganan los movimientos del Rey cuando promocionan. El Rey no promociona.


### Rey

![Reyes Negros](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/BlackKings.png)

![Reyes Blancos](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/WhiteKings.png)

![Movimientos del Rey](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/King.png)

El Rey mueve exactamente como un Rey de Ajedrez: un paso en cada dirección. En los juegos de piezas kanji, el Rey con un punto, 玉將 gyokushō, es el jugador Negro, mientras que el Rey sin punto, 王將 ōshō, es el jugador Blanco.

Esta es la única pieza en el juego internacionalizado que mantiene su forma kanji, 王. En estos juegos, el color Negro o Blanco también es mostrado en esta pieza. Los juegos de madera usan una barra debajo del 王. 

### Torre

![Torres](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Rooks.png)

![Movimientos de la Torre](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Rook.png)

La Torre mueve exactamente igual que una Torre de Ajedrez: cualquier número de casillas ortogonalmente. La pieza internacional tiene el aspecto de un Carruaje, en referencia al nombre Japonés "Carruaje Volador". En inglés, el nombre Torre se basa en la palabra persa para Carruaje. Es la pieza no promocionada más valiosa del juego, a excepción del Rey.

### Alfil

![Alfiles](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Bishops.png)

![Movimiento del Alfil](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Bishop.png)

El Alfil mueve exactamente igual que un Alfil de Ajedrez: cualquier número de casillas en diagonal. La pieza internacional tiene el aspecto de un oficial Japonés con un sombrero tradicional. Es la segunda pieza no promocionada más valiosa, excluyendo al Rey.

### Rey Dragón (Dragón, Torre Promocionada)

![Dragones](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Dragons.png)

![Movimientos del Dragón](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Dragon.png)

El Rey Dragón es una Torre promocionada, es decir una Torre con los movimientos del Rey a mayores. Esta es la pieza más valiosa del juego, a excepción del Rey.

### Caballo Dragón (Alfil Promocionado)

![Caballos Dragones](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Horses.png)

![Movimientos del Caballo Dragón](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Horse.png)

El Caballo Dragón es un Alfil promocionado, es decir un Alfil con los movimientos del Rey a mayores. Esta es la segunda pieza más valiosa del juego, excluyendo el Rey.

Nota: Aunque algunos principiantes de ajedrez confunden los términos para referirse al Caballo en inglés ("Knight" y "Horse"), en Shogi no existe dicha confusión pues se trata de piezas diferentes ("Knight" se refiere al Caballo, y "Horse" al Caballo Dragón).


### General de Oro (Oro)

![Oros](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Golds.png)

![Movimientos del Oro](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Gold.png)

Aunque el patrón de movimiento del General de Oro pueda parecer confuso al principio, la forma más sencilla de recordarlo es que mueve **una casilla ortogonalmente en cualquier dirección**… o a cualquiera de las tres casillas enfrente. En el juego internacionalizado, las protuberancias del casco (incluyendo el símbolo circular dorado) también apuntan en todas esas direcciones.

**Todas las piezas menores promocionadas mueven como un General de Oro.**

### General de Plata (Plata)

![Platas](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Silvers.png)

![Movimientos del Plata](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Silver.png)

Aunque el patrón de movimiento del General de Plata pueda parecer confuso al principio, la forma más sencilla de recordarlo es que mueve **una casilla en diagonal en cualquier dirección** o a cualquiera de las tres casillas enfrente. En el juego internacionalizado, las protuberancias del casco también apuntan en todas esas direcciones.

### Caballo

![Caballos](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Knights.png)

![Movimientos del Caballo](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Knight.png)

Similar al Caballo del Ajedrez, pero solamente puede mover a las dos casillas enfrente, es decir, mueve 2 casillas hacia adelante y una hacia alguno de los 2 lados. Al igual que el Caballo de Ajedrez, esta pieza puede saltar sobre otras.

### Lanza

![Lanzas](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Lances.png)

![Movimientos de la Lanza](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Lance.png)

Una Lanza solamente puede mover hacia adelante, cualquier número de casillas (similar a una Torre).

### Peón

![Peones](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawns.png)

![Movimientos del Peón](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawn.png)

El Peón mueve y captura una casilla hacia adelante. En esto se diferencia del Peón de Ajedrez. El sombrero puntiagudo en el juego de piezas internacional es un recordatorio de esto.

### Piezas menores promocionadas

![Platas Promocionadas](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PSilvers.png)

![Caballos Promocionados](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PKnights.png)

![Lanzas Promocionadas](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PLances.png)

![Tokins](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Tokins.png)

A diferencia del Rey Dragón y el Caballo Dragón, estas piezas no tienen nombres especiales. La excepción es el Peón, al que a veces se le denomina por su nombre japonés, *Tokin*. Al igual que arriba, mueven del mismo modo que el General de Oro. Nótese que las versiones kanji son todas diferentes variantes de estilo del carácter para el Oro.


## Reglas Adicionales

*Soltar piezas* - Las principales excepciones a la hora de soltar piezas tienen que ver con Peones.
1) Los Peones no pueden ser soltados en la misma columna que otro de tus Peones no promocionados (si los hay promocionados no pasa nada).
2) Un Peón no puede ser soltado dando jaque mate, pero sí se puede dando jaque.
3) Ninguna pieza menor puede ser soltada en una forma tal que la pieza no se pueda mover (normalmente significa que la estamos soltando en la última fila, o las últimas dos filas en el caso de un Caballo).

*Jaque Perpetuo* - Un jaque continuado que resulta en la misma posición cuatro veces seguidas supone la derrota del jugador que causa el jaque perpetuo. En Ajedrez estándar serían tablas.

*Repetición* - Similar a la regla anterior, repetir la misma posición (incluyendo las piezas en mano) resulta en tablas.

*Reloj* - El Shogi usa un reloj byo-yomi. Una vez que el tiempo principal se acaba, el jugador entre en byo-yomi. Si está configurado a 30 segundos, el jugador solamente dispondrá de 30 segundos para realizar cada movimiento a partir de ese momento o si no, perderá la partida.

## Notación

Existen diferentes notaciones, incluida la japonesa. Nosotros usamos una forma de la notación occidental (la notación de Hodges), que es similar a la del Ajedrez.

### Coordenadas

Una diferencia característica es que las coordenadas del tablero se utilizan de forma diferente que en Ajedrez. Las columnas son numeradas y las filas usan letras. El punto de origen es el inferior izquierdo del jugador Blanco. Sin embarfo, como la mayoría de diagramas están orientados para el jugador Negro (primer jugador), parece que las coordenadas se inician en la esquina superior derecha. Por ejemplo, la casilla del Rey es 5a.

En la notación de Hoskings solo se utilizan números. En lugar de 5e se diría 55 (quinta fila, quinta columna). Esto es similar al estilo Japonés, que también utiliza números.

### Piezas

K = Rey (**K**ing)

G = General de Oro (**G**old General)

S = General de Plata (**S**ilver General)

N = Caballo (K**n**ight)

L = Lanza (**L**ance)

R = Torre (**R**ook)

B = Alfil (**B**ishop)

P = Peón (**P**awn)

+R o D = Rey Dragón (**D**ragon King, Promoted**+** **R**ook)

+B o H = Caballo Dragón (Dragon **H**orse, Promoted**+** **B**ishop)

+S, +N, +L, +P para el resto de piezas promocionadas (Plata, Caballo, Lanza y Peón, respectivamente).

### Símbolos

* Soltar una pieza se indica con \* (notación de Hodges) o ‘ (notación de Hosking). Aquí usamos \*, por lo que soltar un Peón en 5e sería P*5e.
* Las jugadas que terminan en promoción se indican con + al final. Un Peón promocionando en 1c sería P1c+.
* Si escoges no promocionar, se pone = al final en vez de +.
* Los jaques y jaques mate no se anotan.

## Recursos para Aprender Shogi

[El Canal de Youtube de Hidetchi](https://www.youtube.com/playlist?list=PL587865CAE59EB84A) es un excelente lugar para principiantes y jugadores intermedios. El material está en inglés y explica muy cuidadosamente los distintos aspectos del juego. Nótese que al igual que otros recursos, tendrás que conocer las piezas kanji para entender los vídeos (aunque también incluye vídeos de introducción a las piezas para principiantes).

[81dojo.com](http://www.81dojo.com) es un sitio donde puedes jugar internacionalmente contra jugadores fuertes. Sin embargo, por el momento no soporta el juego por correspondencia.

## Estrategia

### Valor de las Piezas

A diferencia del Ajedrez, no hay un valor estándar para las piezas en Shogi. Sin embargo, es importante tener en mente que los valores no importan mucho, ya que perder piezas no es permanente y la posición es mucho más importante que el material. Dicho esto, existe un sistema básico de valoración de las piezas, aunque los jugadores profesionales también han hecho sistemas más específicos; mostramos a continuación los sistemas de Tanigawa y Satoh:

Pieza | Básico | Tanigawa | Satoh 
------------ | ------------- | ------------- | -------------
P | 1 | 1 | 1
L | 3 | 5 | 6
N | 3 | 6 | 6
S | 5 | 8 | 10
G | 5 | 9 | 11
B | 7 | 13 | 17
R | 8 | 15 | 19
*H* |  | 15 | 20
*D* |  | 17 | 22
*+P* |  | 12 | 
*+L* |  | 10 | 
*+N* |  | 10 | 
*+S* |  | 9 | 

### Principios de Apertura

En general, hay dos tipos de estilo de apertura: *Torre Estática* y *Torre Dinámica*. En Torre *Estática*, la Torre no se mueve. Los ataques, por tanto, se dirigen en el lado derecho del tablero. En Torre *Dinámica*, la Torre se mueve al lado izquierdo (típicamente a las columnas de la 2 a la 5), desplazando la ofensiva a ese lado del tablero.

Esta diferencia es importante porque las jugadas de apertura (denominadas *joseki*) son clasificadas en uno de esos dos grupos y pueden cambiar drásticamente el tipo de partida que se está jugando. Ciertas aperturas de Torre Estática están pensadas contra aperturas de Torre Estática del enemigo, mientras que otras se dirigen contra aperturas de Torre Dinámica.

### Castillos

Los Castillos en Shogi son formaciones defensivas que requieren varios pasos para ser formadas. El conocimiento de Castillos es esencial porque un Rey débil puede ser explotado rápidamente con piezas soltadas en tu territorio. Es también importante conocer las fortalezas y debilidades de cada Castillo.

Igual que antes, los Castillos dependen de las configuraciones de Torre Estática / Dinámica. En aperturas de Torre Estática, los Reyes se enrocan hacia la izquierda. En aperturas de Torre Dinámica, se enrocan hacia la derecha. Existen muchos tipos de Castillo, muchos de los cuales están cubiertos en los vídeos de Hidetchi (ver abajo). Aquí están tres de los más importantes que hay que conocer:

**Yagura (o Fortaleza)**

![Yagura](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Yagura.png)

El Castillo Yagura es uno de los más poderosos Castillos de Torre Estática, usado contra Torre Estática. Una regla mnemotécnica que puede ser útil para recordar las posiciones de los generales es “S G | G B”, o quizás recordar que el Rey es protegido por el General de Oro, una fuerte pieza defensiva. Yagura es fuerte por el frente, pero débil por los lados.

Para el desarrollo del Yagura, recuerda que los generales siempre muevan en diagonal para una máxima eficiencia. Hay diferentes josekis para desarrollar el Castillo, pero ten en mente que en cualquier punto las Blancas pueden atacar y tienes que reaccionar en el medio de tus movimientos de desarrollo. El joseki estándar de 24 movimientos es como sigue (Fuente: Hidetchi):

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

**Castillo Mino**

![Castillo Mino](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Mino.png)

El Castillo Mino es un Castillo de Torre Dinámica clásico, usado contra Torre Estática. El Rey mueve hasta la posición de partida de la Torre, el General de Oro izquierdo mueve arriba a la derecha, y luego el General de Plata derecho avanza para hacer una formación en V “G G S”. Este Castillo es fuerte por la izquierda, pero débil por el frente y el borde.

Ejemplo de apertura para Negras usando una Torre en columna 4:

* P76
* B77 (protege la casilla 86/8f) 
* P66 (rechaza el cambio de Alfiles si las Blancas abren su Alfil)
* R68 (Torre a columna 4)
* S78 
* K48 -> K38 -> K28
* S38 (avance del General de Plata)
* G58 (General de Oro arriba a la derecha)
* P16 (crea ruta de escape para el Rey)
* P46

A partir de este punto, eres libre de cambiar Alfiles y tantas piezas como quieras, incluyendo Torres para generar un ataque.

**Anaguma**

![Anaguma](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Anaguma.png)

Anaguma (es decir “Oso en el agujero”) es otro Castillo de Torre Dinámica, y es uno de los más impenetrables en el juego. Sin embargo, lleva mucho tiempo formarlo.

**Ataque de Doble Flanco**

No es un Castillo en sí mismo, pero es una apertura de Torre Estática. Ambos bandos intentan avanzar sus Peones de Torre, lo cual lleva a un intercambio. Para del joseki consiste en que los Generales de Plata deben defender a los Peones de Alfil antes de que los Peones enemigos lleguen a su objetivo. Nótese que esta es la apertura favorita de AlphaZero, empleada en más de la mitad de las partidas jugadas como Negras.

## Hándicaps

A diferencia del Ajedrez y similar al Go, los Hándicaps son una parte importante en la enseñanza del juego y no debe ser visto como un jugador teniendo pena por el otro. Son una gran herramienta de aprendizaje, e incluso hay diferentes estrategias estándares para distintos tipos de Hándicap. En Shogi, las partidas con Hándicap son bastante habituales, y las configuraciones más habituales se muestran a continuación.

Mientras que en las partidas normales las Negras (*sente*) juegan primero, **las Blancas juegan primero en las partidas con Hándicap**. Las Blancas se denominan *uwate* y las Negras *shitate*. A pesar del Hándicap, la diferencia de material puede compensarse al soltar piezas. Y dado que hay pocas piezas poderosas, las Negras/*shitate* pierden mucho más cuando una pieza es capturada.

Nombre | Piezas omitidas
-- | --
Lanza | Lanza izquierda
Alfil | Alfil
Torre | Torre
Torre–Lanza | Torre, Lanza izquierda
2-Piezas | Torre, Alfil
4-Piezas | Torre, Alfil, ambas Lanzas
6-Piezas | Torre, Alfil, ambas Lanzas, ambos Caballos
8-Piezas | Torre, Alfil, ambas Lanzas, ambos Caballos, ambos Generales de Plata
9-Piezas | Torre, Alfil, ambas Lanzas, ambos Caballos, ambos Generales de Plata, General de Oro izquierdo
10-Piezas | rook, Alfil, ambas Lanzas, ambos Caballos, ambos Generales de Plata, ambos Generales de Oro
