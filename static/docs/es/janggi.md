# ![Janggi](https://github.com/pychess/pychess-variants/blob/master/static/icons/Janggi.svg) Janggi

![Tableros](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Boards.png)

*Janggi* (장기, pronunciado como “*yang-ji*”), o Ajedrez Coreano, es un juego de tablero clásico procedente de Corea. El juego es derivado del Xiangqi y es muy similar a él.

## Reglas: Tablero y Posición Inicial

Hay dos lados, uno de color rojo (llamado Han), y el otro de color azul (llamado Cho). El lado azul también puede ser verde. Estos dos lados representan las dos caras de la Contención Chu-Han de la historia china. Las piezas rojas se escriben usando caracteres chinos (hanja), mientras que las piezas azules se escriben en hanja cursiva.

La posición inicial excepto por el Caballo y el Elefante es como se muestra en la figura arriba. Al igual que el xiangqi, el janggi se juega en un tablero de 9 x 10, donde las piezas se colocan en las intersecciones en vez de en las casillas. El cuadrado de 3x3 con la X a cada lado es llamado el *Palacio*. A diferencia de la mayoría de variantes, en el janggi los jugadores pueden escoger las posiciones iniciales de los Caballos y los Elefantes. Hay cuatro tipos a escoger:

1. Ambos Caballos cerca del borde (*won ang ma*)
2. Ambos Caballos cerca del general (*yang gwee ma*)
3. Caballo izquierdo interior, Caballo derecho exterior (*gwee ma*)
4. Caballo izquierdo exterior, Caballo derecho interior (*mat sang jang gi*)

El Rojo (Han) escoge las posiciones primero, a continuación el Azul (Cho) escoge. Sin embargo, el Azul es el primero en mover las piezas.

Para las repeticiones y otros escenarios de finalización del juego:
* El jaque perpetuo supone la derrota del jugador que hace jaque tras la tercera repetición
* Las repeticiones que no son perpetuas son adjudicadas por material contando después de la tercera repetición
* Cuando se llega a la regla de los 50-movimientos (100 medias-jugadas sin capturas), la partida es adjudicada contando el material

## Las Piezas

Esta guía se basará en el juego internacional de piezas. Los juegos tradicionales de piezas usan caracteres chinos (hanja), y muchos sitios, incluida Wikipedia, explican las reglas con ellos.

Muchas piezas tienen movimientos especiales utilizando las diagonales en cada palacio, lo cual será discutido a continuación. En el diagrama, usaremos un ligero tono verde.

### Rey

![Reyes](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Kings.png)

El **Rey** (también conocido por su nombre chino, el **general**) está restringido a su palacio y puede mover en las líneas del palacio. Esto significa que cuando el Rey está en el centro, tiene 8 posibles movimientos. Pero en cualquier otro lugar del palacio tiene solamente 3 movimientos.

*Reglas especiales:* Cuando un Rey se enfrenta al otro Rey, esto causa *bikjang*. El siguiente jugador debe apartar su rey o si no la partida terminará. Véanse más abajo las reglas de los bikjang.

![Rey y consejero](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Palace.png)

### Consejero

![Consejeros](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Advisors.png)

El **Consejero** (también conocido por su nombre occidental, el **Guardián**) mueve exactamente como el Rey, es decir un espacio por las líneas del palacio. Al igual que el Rey, el Consejero está confinado en el palacio.

### Caballo

 ![Caballos](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Horses.png)
 
 ![Movimiento del Caballo](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/HorseDiagram.png)

El **Caballo** mueve casi exactamente igual que un Caballo de ajedrez. Sin embargo, en lugar de las típicas "dos casillas ortogonalmente y una casilla hacia un lado", es mejor pensar en ello como *un paso ortogonal, y luego otro diagonalmente hacia adelante en cualquier dirección*, como formando una Y. La razón para ello es que el Caballo **puede ser bloqueado** si una pieza se encuentra adyacente a él. Dicha pieza bloqueará ambos extremos de la Y. Por lo tanto, puede haber situaciones donde 2 Caballos se amenazan mutuamente pero solo uno puede atacar mientras que el otro está bloqueado. Hay jugadas fuertes que aprovechan el bloqueo de un Caballo y limitan sus movimientos.

### Elefante

 ![Elefantes](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Elephants.png)
 
 ![Movimiento del Elefante](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/ElephantDiagram.png)

El **Elefante** es muy diferente de su contraparte en el xiangqi. El movimiento es similar al del Caballo en el sentido de que mueve según un patrón en Y. Mientras que el Caballo mueve una casilla ortogonalmente y otra más en diagonal, el Elefante mueve una casilla ortogonal y luego *dos* casillas en diagonal. El Elefante, al igual que el cabllo, puede ser bloqueado en cualquier punto a lo largo de su camino.

### Carruaje

 ![Carruajes](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Chariots.png)
 
 ![Movimiento del Carruaje](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/ChariotDiagram.png)

El **Carruaje** (también conocido por su nombre occidental, la **Torre**) se mueve exactamente igual que una Torre de ajedrez: cualquier número de casillas ortogonalmente. Esta es la pieza más valiosa del juego, excluyendo al rey.

*Movimiento de Palacio*: Cuando se encuentra en el palacio, el Carruaje también se puede mover diagonalmente.

### Cañón

![Cañones](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Cannons.png)

![Movimiento del Cañón](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/CannonDiagram.png)

El **Cañón** es ligeramente diferente que su contraparte en xiangqi. Se mueve ortogonalmente como el Carruaje, pero necesita la intervención de otra pieza (denominada una "pantalla") para poder impulsarse. Puede entonces capturar la siguiente pieza en la misma línea. A diferencia del xiangqi, el Cañón no se puede mover sin una pantalla.

*EXCEPCIÓN*: El cañón no puede usar otro cañón como pantalla. Además, no puede capturar el cañón enemigo.

*Movimiento de Palacio*: Cuando se encuentra en el palacio, el cañón también se puede mover en diagonal. En la práctica, el cañón debe encontrarse en una esquina, donde puede mover o atacar la esquina contraria si una pieza que no sea un cañón se encuentra en el centro (como en el diagrama).

### Peón

![Peones](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Pawns.png)

![Movimiento del Peón](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/PawnDiagram.png)

El **Peón** (también conocido por su nombre chino, el **Soldado**) se mueve y captura hacia adelante o a los lados una casilla. Esto es diferente del peón de xiangqi, que necesita cruzar el río para poder mover hacia los lados.

*Movimiento de Palacio*: Cuando está en el palacio, el peón también se puede mover hacia adelante en las líneas diagonales.

## Notación

La notación de Janggi difiere mucho de otras variantes. En primer lugar, la numeración de las coordenadas. Desde la perspectiva del lado Azul, las filas son numeradas de 1 a 10 de arriba a abajo. Sin embardo la décima fila es llamada 0. Las columnas se numeran de 1 a 9 de izquierda a derecha. Describir la posición de una pieza es justo al contrario que en ajedrez. Una posición se describe primero con *fila* y luego *columna* (en todas las demás variantes es primero columna y luego fila). Así que por ejemplo, el Carruaje azul en la esquina inferior izquierda se encuentra en **01**. La intersección sobre él es **91**. El rey azul se encuentra en **95**.

La descripción de los movimientos no tiene una versión estandarizada internacional. Usamos una modificación de la forma coreana. En la notación coreana, la sintaxis es (posición inicial)(nombre de la pieza en coreano)(posición final). Aquí en Pychess, usamos (abreviatura de la pieza en inglés)(posición inicial)-(posición final). Como en ajedrez, las capturas se denotan con x en lugar de -, el jaque tiene un + al final, y el jaque mate es #.

Por ejemplo, el Carruaje izquierdo moviéndose tres espacios hacia arriba se denotaría R01-71. "R" se refiere al Carruaje. Véanse las abreviaturas de las piezas a continuación.

### Abreviaturas

K = Rey (**K**ing)

A = Consejero (**A**dvisor)

E = Elefante (**E**lephant)

H = Caballo (**H**orse)

C = Cañón (**C**annon)

R = Carruaje (Cha**R**iot)

P = Peón (**P**awn)



## Reglas del juego

Como en ajedrez, el objetivo es dar mate al rey adversario.

A diferencia de muchas otras variants de ajedrez, puedes pasar el turno en Janggi. Por lo tanto, el ahogado es imposible. **Para pasar el turno en Pychess, ctrl+click en tu rey, o simplemente haz click en el botón de pasar el turno a la derecha.**

A diferencia del Xiangqi, los reyes pueden estar enfrentados en la misma columna en Janggi. Esto crea una situación denominada **bikjang** (generales riéndose). Si el siguiente jugador al que le toque mover, no rompe el bikjang (por ejemplo moviendo el rey o interponiendo una pieza), entonces la partida termina en tablas. Para torneos que no permiten las tablas, se cuenta el valor de las piezas en el tablero, y el jugador con el mayor valor gana.

Pieza | Valor
------------ | ------------- 
Carruaje | 13
Cañón | 7
Caballo | 5
Elefante | 3
Consejero | 3
Peón | 2

Dado que el bando Azul (Cho) comienza la partida, empieza con una ventaja y por lo tanto el bando Rojo (Han) recibe 1.5 puntos adicionales (*deom*) como compensación. El .5 se añade para evitar empates.

Actualmente, Pychess utiliza normas de torneo y no permite las tablas. Por lo tanto, las partidas son decididas por los puntos cuando ocurre un bikjang.

A mayores, es posible causar un bikjang y jaque al mismo tiempo. En este caso, el bikjang tiene prioridad.

La repetición es ilegal; sin embargo, el modo en que esto se gestiona es variable. La repetición no es gestionada en Pychess, por lo que en el caso de una repetición, los jugadores deben adjudicar ellos mismos el resultado de la misma.

## Diferencias con respecto al Xiangqi

Aparte de las reglas mencionadas arriba...

* No hay río en Janggi. En consecuencia, los Peones y Elefantes mueven diferente. Los Peones se pueden mover hacia los lados desde el comienzo. El movimiento de los Elefantes es completamente diferente.
* Visualmente, las piezas están en octágonos en vez de círculos. Los tamaños de las piezas también varían según el valor. Los Reyes (generales) son llamados con los nombres de los bandos en vez de ser llamados "general". Los tableros usan x's en vez de cruces para las piezas al comienzo.
* Los Reyes empiezan en el medio del palacio en vez de en la parte trasera del mismo.
* Los Cañones son diferentes en que mueven y capturan de la misma forma (saltando sobre otra pieza primero). También tienen restricciones adicionales.
* El palacio afecta al movimiento de todas las piezas excepto el Caballo y el Elefante. Los Reyes y Consejeros mueven sobre las líneas en lugar de ortogonalmente o diagonalmente. Los Carruajes, Cañones y Peones pueden mover en esas diagonales.



## Estrategia

[Estos videos por Amphibian Hoplite](https://www.youtube.com/playlist?list=PL9corMEVRvP-HUJcF7I670pEqV3XNbkKM) son un excelente punto de partida en inglés. Al margen de ellos, no hay mucho material disponible en inglés.

[Aquí](https://www.youtube.com/watch?v=pX_ZDjeqlJs) hay otro vídeo por Kolo (también conocido como Galdian) que también se enfoca en los principios de apertura.

### Conceptos Generales

* La estructura de peones es muy importante. Dado que los peones se pueden mover hacia los lados, son más fuertes cuando se protegen unos a otros en pares. Una línea de tres peones es una formación pobre. Debido a ello, no es recomendable avanzar peones en general.

![Formaciones de Peones Malas](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/BadPawns.png)

* Respecto al proceso de escoger la disposición Caballo-Elefante al comienzo, una forma de verlo es enfocarse en cómo tus Elefantes están posicionados, y ello tiene implicaciones significativas para la apertura. Un Elefante en una posición exterior puede moverse hacia el centro entre dos peones. sin embargo, un Elefante en una posición interior está bloqueado por peones (aunque los protege).
* Continuando con el mismo tema, la disposición de tu Elefante determina qué **columna del borde abrir**. Por ejemplo, cuando jugamos con una disposición donde el Elefante izquierdo puede avanzar (y el correspondiente Elefante del rival está también en el exterior), es deseable mover el peón del borde izquierdo del tablero, abriendo la columna del Carruaje. La razón para ello es que ahora el correspondiente peón del rival no se puede mover, así que si atacas a dicho peón con tu Elefante, si ese peón se defiende, tu rival perdería su Carruaje. Nótese que si el rival tuviese dos Elefantes interiores, entonces sería deseable abrir el borde contrario.

![Activando el Elefante y Carruaje](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/ActiveElephant.png)
