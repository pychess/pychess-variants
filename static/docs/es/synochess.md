# ![Synochess](https://github.com/pychess/pychess-variants/blob/master/static/icons/synochess.svg) Synochess

![Synochess](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Synochess.png)

El Synochess es una variante de Ajedrez diseñada en 2020 por Couch Tomato. La idea del juego era crear una variante donde el ejército del Ajedrez occidental luchara contra el ejército del Xiangqi (Ajedrez Chino) de una forma equilibrada. Dado que las circunstancias en Xiangqi son muy distintas (tablero más grande, piezas en general más débiles), era difícil conseguirlo sin añadir grandes mejoras al ejército basado en Xiangqi. Sin embargo, fue posible hacerlo, sin perder la sensación de estar jugando Xiangqi cuando se juega con ese bando. En este juego las Blancas representan el Ajedrez occidental y reciben el nombre de Reino, mientras que el ejército Rojo representa la mezcla de Xiangqi y Janggi (Ajedrez Coreano) y se denomina Dinastía. Todas las piezas de la Dinastía recuerdan a su contrapartida bien en Xiangqi o bien en Janggi y deberían resultar familiares para quienes hayan practicado dichos juegos.
El nombre Synochess se basa en un nombre previo, Sinochess, pero fue cambiado porque la Dinastía se convirtió en menos "Sino" (como en Chino) y más una mezcla de Chino y Coreano. En cambio el prefijo syn- significa "juntos", y el juego representa dos ramas históricas diferentes del ajedrez juntas en una.
 
## Reglas Generales
1.	La posición inicial es como se ve arriba.
2.	Las únicas piezas que los bandos tienen en común son los Reyes, Caballos y Torres (llamadas Carruajes en el bando de la Dinastía).
3.	El Reino (Blancas) siempre mueve primero.
4.	La Dinastía (Rojas) no puede enrocar.
5.	Los Peones del Reino solamente pueden promocionar a sus propias piezas (Dama, Torre, Caballo, Alfil). Los soldados de la Dinastía no promocionan.

\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*

¡Hay cinco reglas adicionales que los nuevos jugadores deben tener especialmente en cuenta! (Además de aprender las nuevas piezas)

\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*

1.	**Reyes Enfrentados** – Al igual que en Xiangqi, **los Reyes no pueden estar enfrentados (en la misma columna o fila) sin piezas por el medio**, como si fuesen dos Torres atacándose mutuamente. Ten esto en cuenta, porque las piezas pueden estar clavadas en el medio, y también pueden ser protegidas por el Rey aliado.
2.	**Refuerzos de Soldados** – Las Rojas empiezan con dos Soldados en mano. En vez de mover una pieza en el tablero, la Dinastía puede soltar un Soldado en cualquier casilla vacante en la fila 5 (fila 4 de la Dinastía), la misma fila donde los Soldados comienzan.
3.	**Camp mate** – Un Rey que llega a la última fila (sin ponerse en jaque) gana la partida.
4.	**Ahogado** – Como en Xiangqi, el ahogado supone la derrota (en Ajedrez, serían tablas).
5.	**Jaque perpetuo** – Como en Xiangqi, el jaque perpetuo (repetir la misma posición tres veces, con todas las jugadas siendo jaque) suponen la derrota (en Ajedrez, serían tablas).

## Piezas de la Dinastía

Hay cuatro nuevas unidades propias de la Dinastía: 6 Soldados (2 comienzan en mano), 2 Cañones, 2 Elefantes y 1 Consejero.
Los Carruajes son iguales a las Torres y usan la misma abreviatura (R) - la diferencia es puramente estética. De modo similar, los Reyes son lo mismo, pero su aspecto es diferente. A pesar de que el Caballo ("Horse") son diferentes en Xiangqi y Janggi, la versión de la Dinastía se denomina Caballo ("Knight") y mueve exactamente igual que el Caballo del Reino.
La Dinastía no tiene ninguna pieza tan fuerte como la Dama; sin embargo tiene más piezas menores que el Reino.
Los detalles y diagramas de cada pieza se muestran a continuación.

### Soldado (S)

![Soldado](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Soldier.png)

El Soldado puede mover un espacio hacia adelante o hacia los lados. Es exactamente lo mismo que un Soldado que ha cruzado el Río en Xiangqi y lo mismo que un Soldado de Janggi. El Soldado, a diferencia del Peón, no puede promocionar.
Dado que el Soldado no puede mover hacia atrás, solamente puede mover hacia los lados en la última fila. Evita ponerlos en esta situación a menos que te sirva para llegar a jaque mate o camp mate. Los Soldados son más fuertes cuando van en pares de forma que se protegen mutuamente.

### Elefante (E)

![Elefante](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ElephantDynasty.png)
 
El Elefante es una pieza "saltadora" que se mueven diagonalmente una o dos casillas. Puede saltar en diagonal sobre una pieza para mover o capturar en la segunda casilla. La pieza es esencialmente una versión mejorada del Elefante de Xiangqi; es exactamente lo mismo que el Elefante del Shako.

### Cañón (C)

![Cañón](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/CannonDynasty.png)
 
 El Cañón también es una pieza que salta. Es esencialmente una Torre que para moverse necesita la intervención de una pieza intermedia (denominada "pantalla") para saltar sobre ella y poder mover o capturar a lo largo de la misma línea. *****Un Cañón no puede saltar sobre otro Cañón.***** Esta versión del Cañón es exactamente la misma que en Janggi. Dado que requiere de otra pieza para mover o capturar, el Cañón tiene menos valor en los finales.
 
### Consejero

![Consejero](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Advisor.png)

El Consejero mueve y captura exactamente como un Rey. A diferencia del Rey, puede ser capturado. Aunque no hay ninguna pieza equivalente en Xiangqi o Janggi, no hay Palacio en Synochess. Por tanto, el Consejero necesitaba ser más fuerte para proteger a su propio Rey, y uno puede pensar en sus movimientos como una combinación de la fuerza de los dos Consejeros del Xiangqi para cubrir las 8 casillas.

 
## Valor de las Piezas

Los valores precisos de las piezas son desconocidos. Sin embargo, estos son los valores usados por Fairy Stockfish, con la aclaración de que son valores genéricos, no necesariamente específicos a Synochess.

Pieza del Reino	| Valor (Temprano / Tarde) | Pieza de la Dinastía | Valor (Temprano / Tarde)
-- | -- | -- | --
Peón | 120 / 213	| Soldado | 200 / 270
Dama | 2538 / 2682	| Consejero | 700 / 900
Alfil | 825 / 915	| Elefante | 700 / 650
Caballo | 781 / 854	| Cañón | 700 / 650
Torre | 1276 / 1380	| Caballo | 781 / 854
 | | | Carruaje | 1276 / 1380

Para aquellos que quieren una aproximación más simplificada, esta tabla puede servir:

Pieza del Reino	| Valor | Pieza de la Dinastía	| Valor
-- | -- | -- | --
Peón | 1 | Soldado | 2
Dama	| 9 | Elefante | 2.75
Alfil | 3 | Consejero | 2.75
Caballo | 3 | Cañón | 3
Torre | 5 | Caballo | 3
 | |  | Carruaje | 5

## Estrategia

El juego es todavía reciente, así que la estrategia está en desarrollo. La mayoría de información disponible se basa en el juego del ordenador. Como la mayoría de juegos, se puede aprender mucho jugando contra una I.A. de alto nivel, perdiendo y analizando las causas de la derrota.

### Aperturas

Al igual que en Xiangqi, las primeras pocas jugadas de la apertura son muy limitadas antes de que se abran multitud de ramas. En una gran mayoría de las partidas (~90%), Stockfish abre con 1. e3. 1. b3 es la jugada más habitual después de e3. Otras jugadas incluyen g3, f3 y c3, pero son extremadamente raras. Todas las demás aperturas para el primer movimiento son subóptimas. b3 es la segunda jugada más habitual para las Blancas, aunque c3 es jugada también ocasionalmente. Para el tercer movimiento de las Blancas hay ya mucha variedad, aunque Bb2 es la jugada más común.
Respecto a la Dinastía, la primera jugada más habitual es Nc6 (70%), o en menor medida, Nf6 (30%). Ninguna otra jugada ha sido intentada por Stockfish. La segunda jugada consiste en avanzar el otro Caballo o mover un Cañón a una posición central (Ce6+ > Cd6). A partir de ese punto existe una gran ramificación de posibilidades.

Por tanto, la "apertura estándar de Nc6" es como sigue:
1.	e3 Nc6
2.	b3 …Nf6/Ce6+/Cd6

La línea más habitual es:

1.	e3 Nc6
2.	b3 Nf6
3.	Bb2 Ee7

Para jugadores que prefieren Nf6, la línea más habitual es:

1.	e3 Nf6
2.	b3 Ce6+
3.	Be2 Nc6

Como en Xiangqi, los ataques descubiertos son habituales. ¡Presta atención a los mismos!

También como en Xiangqi y quizás incluso con más frecuencia, utilizar los Reyes de forma ofensiva es importante. Es muy sencillo clavar una pieza entre los Reyes. Por ejemplo, un Peón solitario entre los Reyes no puede atacar.

El jugador de la Dinastía debe jugar agresivamente. Comienza con una posición avanzada, pero con piezas en general más débiles. Debe buscar cambios de piezas en su favor. Los Soldados valen más que los Peones, así que la Dinastía debería intentar que al Reino le cueste eliminar a cada Soldado.

Como Dinastía, trata de evitar mover los Soldados mucho. Su formación inicial ya es una estructura óptima (en pares que se protegen mutuamente). Puedes deslizarlos para abrir líneas o crear ataques para tus Cañones o Carruajes. Puedes usarlos como refuerzo para reemplazar a Soldados perdidos. Si los sueltas demasiado temprano, puedes estar bloqueando tu propio juego.

### Consejos para el Reino (Blancas)

* **Movimientos de Peones en la apertura – ¡paso a paso!** – Esto se basa en los patrones de Stockfish, que siempre escoge avanzar los peones una casilla en vez de dos en la apertura. Probablemente se debe a que es importante mantener una estructura de Peones sólida para luchar contra los molestos Soldados de la Dinastía.
* **EVITA iniciar un cambio de piezas por el Cañón** - El Cañón, aunque sea muy amenazador al principio de la partida, se devalúa rápidamente a lo largo de la partida. De hecho, eliminar de forma efectiva al resto de piezas elimina a los Cañones, que no dispondrían de piezas que le sirvan de pantalla y quedarían expuestos a ser eliminados fácilmente.
* **¡Protege a la Dama!** - La Dama tiene aún más valor que en Ajedrez estándar, ya que es la única gran baza que el Reino tiene sobre la Dinastía. Si necesitas cambiarla, asegúrate de que al menos uno de los Carruajes enemigos es eliminado con ello.
* **Cambia, cambia, cambia** – Teniendo en cuenta los dos últimos consejos, si sigues cambiando piezas, manteniendo tu Dama y los Cañones del rival, llegarás a un final favorable. La Dinastía tiene una coordinación de piezas compleja, que puede ser rota cuando le quedan pocas piezas. El Reino busca una partida abierta y sencilla, mientras que la Dinastía busca sacar provecho de sus posibilidades de ataque al comienzo.

### Consejos para la Dinastía (Rojas)

* **¡Conoce los movimientos de las piezas!** – Puede sonar obvio, pero muchos principiantes se olvidan de que los Soldados pueden move hacia los lados.
* **Estructura de Soldados – NO MUEVAS TUS SOLDADOS** – Puede sonar contraintuitivo en comparación con los Peones del Ajedrez estándar, pero los Soldados realmente no deberían estar moviéndose como parte de tu desarrollo O para la mayoría de ataques. La posición inicial de tus Soldados es la formación más fuerte posible. Cada uno defiende a otro y previenen que las Blancas coloquen ninguna pieza en la quinta fila. En esta formación, cada par vale seguramente más que una pieza menor. Mantenlos así y úsalos como pantallas para tus Cañones para poner presión contra el desarrollo de las Blancas. Además, a pesar de las palabras "NO MUEVAS" en mayúsculas y negrita, si tienes que hacerlo, obviamente tienes que hacerlo.
* **Soldados de Refuerzo – Hazlo de forma esporádica** – Como hemos dicho, la estructura de Soldados ya es óptima. Añadir refuerzos sin ningún motivo va a dañar tu estructura y arruinar tu tempo. Usa los refuerzos cuando las Blancas estén a punto de atacar un Soldado con un Peón apoyado por otra pieza. Si un Soldado es cambiado por alguna pieza de las Blancas, puedes soltar el refuerzo a continuación para reparar tu estructura.
* **¡Cambia tus Cañones tan rápido como puedas!** – Como hemos mencionado en los consejos para el Reino, el Cañón se devalúa rápidamente a lo largo de la partida. Sí, pueden producir tácticas devastadoras, pero el jugador de la Dinastía debería tener en cuenta que hay una ventana muy pequeña para ello (inicio del mediojuego). Es recomendable cambiar uno de tus Cañones al principio de la partida (en las primeras jugadas). Esto permite al segundo Cañón moverse más libremente.
* **Activa tus Carruajes** – Este consejo recuerda a la estrategia básica del Xiangqi. La Dinastía comienza con columnas abiertas para los Carruajes - asegúrate de usarlas para poner los Carruajes en juego. Una vez que las Torres enemigas salen a jugar, esta ventaja desaparece rápidamente.

### Táctica

**El Mate del Loco**

Si eres Blancas, evita esta situación. No pierdas de vista a los Cañones.

![Mate del Loco](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/FoolsMate.png)

En parte esto explica por qué 1. e3 es una apertura estándar. Y cuando no se hace 1. e3, se suele hacer 2. e3. Después, si un Cañón ataca, puede ser bloqueado por un Alfil o Caballo, que quedará clavado durante un rato. 1. e4 no es recomendablte porque de hecho no amenaza nada (el Peón está clavado debido a los Reyes enfrentados).

**MataDamas**

Esta es una táctica especialmente devastadora que puede causar la derrota inevitable de las Blancas. La situación se produce cuando un Carruaje tiene una columna abierta (con la cual ya cuenta al comienzo), y el Cañón tiene un camino abierto hacia la primera fila (b1 o g1). Esa casilla puede o no contener un Caballo, pero si está vacía la táctica solo funciona si el Caballo no la cubre.

![MataDamas](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Queenslayer.png)

Una vez que esta posición ocurre, el Carruaje puede tomar el Peón, forzando a la Torre a retomar el carruaje. Esto expone la casilla b1/g1 para el Cañón, que o bien amenazará Y clavará la Dama en el caso de b1, o bien hará una enfilada a la Dama con el jaque desde g1. En cualquier caso, se pierde la Dama.
