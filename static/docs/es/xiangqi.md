# ![Xiangqi](https://github.com/pychess/pychess-variants/blob/master/static/icons/xiangqi.svg) Xiangqi

![Tableros](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Boards.png)

El *Xiangqi* (象棋, pronunciado como “*shiang-chi*”), o Ajedrez Chino, es un juego de tablero clásico procedente de China que se supone derivado del Chatturanga, el mismo ancestro que el Ajedrez, aunque algunos han teorizado lo opuesto. El juego es muy popular en China y Vietnam, y se ha dicho que es el juego más jugado en el mundo. El juego es muy similar al Ajedrez, pero guarda diversas diferencias.

## Por qué aprender Xiangqi?

If you enjoy Chess, Xiangqi is definitely worth trying. While slightly slower paced and longer than Chess, the game starts more open and is more geared towards fast-paced play leading to a quick endgame. Compared to Chess, Xiangqi is also far more tactical (as opposed to strategic). As with other chess variants, improving your skill in Xiangqi can also improve your skills in Chess (tactics, in particular) as well as open up new ways of thinking! [See here for more about that.](https://en.chessbase.com/post/why-you-need-to-learn-xiangqi-for-playing-better-chess)
Si disfrutas del Ajedrez, definitivamente vale la pena probar el Xiangqi. Aunque es ligeramente más lento que el Ajedrez, el juego abre más abierto y está orientado a un ritmo rápido que lleva a un final pronto . Comparado con el Ajedrez, el Xiangqi es también más táctico (menos estratégico).  Al igual que otras variantes, mejorar tus habilidades en Xiangqi también te puede ayudar a mejorar tus habilidades en Ajedrez (táctica en particular), así como abrir tu mente a nuevas formas de pensamiento. [Lee esto para más información al respecto.](https://en.chessbase.com/post/why-you-need-to-learn-xiangqi-for-playing-better-chess)

## Las Reglas

Las reglas generales son similares al Ajedrez, así que esta guía se centrará en las pocas diferencias. La diferencia más notable es que las piezas se encuentran en las intersecciones en vez de en los cuadrados, lo cual es principalmente una diferencia estética. Los jugadores toman turnos moviendo sus piezas en el tablero con el objetivo de dar jaque mate al Rey rival. El jugador Rojo empieza jugando tradicionalmente, seguido por el jugador Negro, aunque el orden no es crucial dado que el tablero es simétrico. La única otra diferencia con el Ajedrez es que los ahogados suponen la derrota para el jugador que resulta ahogado.
Al respecto de los jaques perpetuos, el jugador que da jaque perpetuo al otro pierde tras tres repeticiones.

## El Tablero

El tablero de Xiangqi es un poco diferente que el resto de juegos de Ajedrez. Además de ser jugado en las intersecciones, hay ciertas secciones importantes en el tablero. En primer lugar el Río, que divide el tablero en dos. El Río afecta al movimiento del Elefante y los Peones. En segundo lugar tenemos los Palacios, que son cuadrados de 3 x 3 en el borde del tablero correspondiente a cada bando, con líneas diagonales dentro. El Rey y sus Consejeros están confinados en este Palacio.

## Las Piezas

Esta guía se basará en el juego de piezas internacionalizado. Los juegos tradicionales usan caracteres Chinos, y muchos sitios, incluyendo Wikipedia, explican las reglas en base a ellos. A día de hoy necesitas tener conocimiento de estos kanji si quieres utilizar los recursos que puedes encontrar en inglés o jugar en un escenario real. Comparado con el Shogi (que es el otro juego principal que usa caracteres Chinos), el Xiangqi tiene menos caracteres que aprender, y varios de ellos son pictográficos, lo que los hace más fáciles de aprender.

Las piezas de Xiangqi han tenido dos nombres tradicionalmente: su denominación en Chino y un equivalente occidental. En esta guía usaremos los nombres y abreviaturas escogidos por la Federación Asiática de Xiangqi (AXF), que utiliza una mezcla de ambos. Desafortunadamente, ambos son muy comunes, por lo que deberías familiarizarte con ambos.

### Rey

![Reyes](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Kings.png)

El Rey (también conocido por su nombre Chino, el **General**) solamente puede mover una casilla ortogonalmente. A mayores, está confinado en el Palacio.

*Regla especial*: Los Reyes no pueden estar enfrentados sin piezas de por medio. Se deben considerar piezas capaces de atacar al otro como si fuesen Torres (también denominados "Generales Voladores"). Esto es útil para preparar jaques mates en el final.

![Movimiento de Rey y Consejero](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/KingAdvisorDiagram.png)

### Consejero

![Consejeros](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Advisors.png)

El **Consejero** (también conocido por su nombre occidental, el **Guardián** o menos frecuente **Ministro**) solamente puede mover una casilla a lo largo de las diagonales del palacio. Hay solamente cinco posiciones para un Consejero.

### Elefante

 ![Elefantes](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Elephants.png)
 
 ![Movimiento del Elefante](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/ElephantDiagram.png)

El Elefante (raramente llamado por su nombre occidental, el **Alfil**) puede mover en diagonal exactamente dos casillas. Hay dos restricciones adicionales: 1) El Elefante puede ser bloqueado si hay una pieza en el medio. 2) El Elefante no puede cruzar el Río.

Como nota al margen, el carácter chino para el Elefante Rojo significa "Ministro", pero sin embargo sigue siendo denominado Elefante en inglés.

### Caballo

 ![Caballos](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Horses.png)
 
 ![Movimiento del Caballo](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/HorseDiagram.png)

El **Caballo** mueve casi exactamente igual que un Caballo de ajedrez. Sin embargo, en lugar de las típicas "dos casillas ortogonalmente y una casilla hacia un lado", es mejor pensar en ello como *un paso ortogonal, y luego otro diagonalmente hacia adelante en cualquier dirección*, como formando una Y. La razón para ello es que el Caballo **puede ser bloqueado** si una pieza se encuentra adyacente a él. Dicha pieza bloqueará ambos extremos de la Y. Por lo tanto, puede haber situaciones donde 2 Caballos se amenazan mutuamente pero solo uno puede atacar mientras que el otro está bloqueado. Hay jugadas fuertes que aprovechan el bloqueo de un Caballo y limitan sus movimientos.

### Carruaje

 ![Carruajes](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Chariots.png)
 
 ![Movimiento del Carruaje](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/ChariotDiagram.png)

El **Carruaje** (también conocido por su nombre occidental, la **Torre**, y raramente por su traducción moderna literal, **Coche**) se mueve exactamente igual que una Torre de ajedrez: cualquier número de casillas ortogonalmente. Esta es la pieza más valiosa del juego, excluyendo al rey.

### Cañón

![Cañones](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Cannons.png)

![Movimiento del Cañón](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/CannonDiagram.png)

El Cañón es una pieza única en Xiangqi. Puede mover exactamente igual que el Carruaje. Sin embargo, para capturar necesita una pieza (amiga o enemiga) en medio, denominada pantalla.

### Peón

![Peones](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Pawns.png)

![Movimiento del Peón](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/PawnDiagram.png)

The pawn (also called by its Chinese name, the **soldier**) moves and captures by moving forward one square. This is different than the chess pawn. The pointy hat in the internationalized piece is a reminder.
El **Peón** (también conocido por su nombre chino, el **Soldado**) se mueve y captura hacia adelante una casilla. Esto es diferente del peón de Ajedrez. El sombrero puntiagudo en la pieza internacionalizada sirve de recordatorio.

*Regla especial*: Después de cruzar el Río, el Peón puede mover y capturar también hacia los lados una casilla. El aspecto de la pieza no cambia para reflejar este hecho.

## Reglas adicionales - Jaques Perpetuos y Persecuciones

* Un jugador haciendo jaque perpetuo con una o varias piezas puede ser declarado perdedor a menos que pare de dar dichos jaques.
* El bando que persigue perpetuamente una pieza desprotegida del rival con una o más piezas, a excepción de Generales y Soldados, puede ser declarado perdedor a menos que pare dicha persecución.
* Si un bando da jaques perpetuos mientras el otro hace una persecución perpetua, el bando que da los jaques debe parar de hacerlo o aceptar la derrota.
* Cuando ninguno de los bandos viola las normas y ambos persisten en no hacer un movimiento alternativo, la partida puede ser declarada tablas.
* Cuando ambos bandos violan la misma regla al mismo tiempo y ambos persisten en no hacer una jugada alternativa, la partida puede ser declarada tablas.

## Notación

Actualmente Pychess usa la misma notación algebraica que en Ajedrez. Una notación más usada habitualmente no está implementado de momento en Pychess.

### Símbolos

K = Rey (**K**ing)

A = Consejero (**A**dvisor)

E = Elefante (**E**lephant)

H = Caballo (**H**orse)

C = Cañón (**C**annon)

R = Carruaje (Cha**R**iot)

P = Peón (**P**awn)


## ¿Dónde puedo encontrar recursos para aprender Xiangqi?

[Xiangqi en inglés] (http://www.xqinenglish.com/) es un buen sitio para principiantes. El dueño del sitio, Jim Png Hau Cheng, ha escrito también varios libros, la serie “Xiangqi Primer”, que puede ser una inversión valiosa para estudiantes serios.

[Club Xiangqi](https://www.clubxiangqi.com/) es un sitio donde puedes jugar contra jugadores fuertes, la mayoría vietnamitas.

## Estrategia

### Valores de las Piezas

Los valores consensuados de las piezas se muestran a continuación

Pieza | Valor
------------ | ------------- 
K | Infinite
R | 9
H | 4
C | 4.5
P | 1 antes del Río o en la última fila, 2 después del Río
A | 2
E | 2.5

### Principios Generales

* De forma similar al Caballo y Alfil en Ajedrez, el Caballo y el Cañón tienen valores opuestos en función de la situación en el tablero.
  * El Caballo es más defensivo y menos poderoso en el principio del juego porque muchas piezas restringen sus movimientos. Se vuelve mucho más poderoso en el final (al contrario que el Caballo de Ajedrez), cuando hay pocas piezas en su camino.
  * El Cañón es más ofensivo y poderoso en el principio del juego porque puede usar sus propias piezas como pantallas. En el final, cuando el tablero está más vacío, su poder disminuye significativamente.
* Como hemos comentado, usa tus piezas para bloquear al Caballo y los Elefantes.
* No pienses en un Elefante como un Alfil; no tienen roles similares a pesar de lo parecido de su movimiento y posición inicial. Es una pieza estrictamente defensiva. Su utilidad ofensiva puede ser servir de pantalla a un Cañón.
* Los *ataques descubiertos* son más frecuentes en Xiangqi que en Ajedrez o Shogi debido a las piezas bloqueables. Presta atención para usarlos o defenderte de ellos.
* Los *jaques dobles* también son más frecuentes, especialmente con el tandem Carruaje/Cañón.

### Principios de Apertura

La siguiente información es cortesía de [este sitio](http://www.shakki.info/english/openings.html)

El movimiento de apertura más común es el Cañón central, que es un movimiento bastante obvio porque lanza una agresión por la columna central. Alrededor del 70% de las partidas comienzan de este modo, así que es probablemente el mejor modo de empezar a aprender el juego.

![Apertura de Cañón](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/CannonOpening.png)

Hay cuatro defensas muy populares, y una quinta que también mencionaremos.

**1. Caballos pantalla / Defensa Dos caballos**

![Caballos pantalla](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Screen_Horses.png)

Esta es la defensa más común. El objetivo por supuesto es tener ambos Caballos protegiendo el Peón central. Hay múltiples variaciones.

**2. Fan Gong Ma / "Caballos Sandwich"**

Un Caballo se desarrolla normalmente, pero antes de que el otro sea desarrollado, un Cañón se mueve a una posición de "esquina de palacio" ("palcorner" en inglés, significando que va la esquina del palacio a su mismo lado), y después finalmente se mueve el segundo Caballo. Las Negras a continuación conectarán los Elefantes para completar la defensa. Es una apertura relativamente reciente.

![Fan Gong Ma](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Fan_Gong_Ma.png)

**3. Cañón en Misma Dirección**

Las Negras mueven el Cañón del mismo lado que las Rojas han movido. Capturar el indefenso Peón central por parte de las Rojas es considerado un movimiento de amateurs porque pierde tiempo e iniciativa.

**4. Cañón de Dirección Contraria**

Como la anterior, pero con el otro Cañón. La práctica moderna consiste en mover el Cañón más tarde en lo que podíamos denominar "Cañón de Dirección Contraria Retrasado".

**5. Tigre en Tres Pasos**

![Tigre en Tres Pasos](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Three_Step_Tiger.png)

Las Negras desarrollan su Carruaje rápidamente moviendo su Cañón al borde del tablero. Una secuencia típica sería avanzar el Caballo primero, luego el Cañón al borde, y finalmente seguir con el Carruaje a la columna del Cañón.

Cualquier otra defensa es considerada rara.

Al margen de la apertura de Cañón, las Rojas tienen otras opciones también. Son denominadas "aperturas suaves" porque no abren con una amenaza inmediata.

**Apertura de Peón** - Avanzando el segundo o cuarto Peón. Es una apertura flexible que permite a las Rojas reaccionar a la jugada de las Negras. Las Negras normalmente no responden con el Cañón central porque las Rojas podrían entonces jugar cualquiera de las defensas de la apertura de Cañón con colores cambiados y el movimiento de Peón como ventaja adicional.

**Apertura de Elefante** - Avanzando un Elefante al Palacio en lugar de un Cañón. Es una apertura sólida y defensiva, donde el Rey va a estar a salvo.

**Apertura de Caballo - Avanzando un Caballo hacia el centro. A partir de aquí, las Rojas pueden jugar la Defensa Dos Caballos, Fan Gong Ma o Tigre en Tres Pasos con colores cambiados.

Las Rojas también puede jugar su Cañón a la esquina frontal del Palacio ("Palcorner Cannon") o a la esquina contrario ("Crosspalace Cannon"). Estos movimientos son jugadas de desarrollo útiles.

Otras jugadas de apertura de Rojas son muy raras.
