# ![Sittuyin](https://github.com/pychess/pychess-variants/blob/master/static/icons/sittuyin.svg) Sittuyin

![Sittuyin](https://github.com/pychess/pychess-variants/blob/master/static/images/SittuyinGuide/Sittuyin.png?raw=true)

El *Sittuyin*, o Ajedrez Birmano, es un juego de tablero clásico nativo de Myanmar y es muy similar al Makruk. Es jugado en Myanmar, y aunque el Ajedrez occidental es más popular allí, se están llevando a cabo esfuerzos para revitalizar el juego. Las piezas tienen los mismos movimientos que el Makruk (Ajedrez Tailandés), pero las reglas son ligeramente diferentes. El juego está lleno de diversión, con sus propias dinámicas/equilibrio. El ritmo ligeramente más lento puede servir para cultivar la paciencia, y desarrollar el pensamiento estratégico.

## Reglas

Las reglas generales son extremadamente similares al Ajedrez, así que esta guía se enfocará en las pocas diferencias que hay. Los tableros son ligeramente diferentes, con el de Sittuyin disponiendo dos grandes líneas diagonales que dividen el tablero. Los bandos son también Rojo y Negro, con el jugador Rojo moviendo en primer lugar. La disposición inicial de las piezas en Sittuyin es muy diferente comparada con el Ajedrez o el Makruk. Las diferencias clave son las siguientes:

* Los Señores Feudales (Peones) empiezan en filas escalonadas (como puedes ver en el tablero arriba).
* Para empezar la partida, los jugadores (empezando por el Rojo) alternan colocando el resto de sus piezas en sus mitades del tablero.
* La promoción del Peón (Señor Feudal) funciona muy diferente. Véase la sección sobre el movimiento más abajo.

Condiciones adicionales para tablas:

* La partida se declara tablas cuando el jugador al que le toca no dispone de ninguna jugada legal y el Rey no está en jaque. Se dice que la partida termina en 'ahogado'. La partida termina inmediatamente, siempre que la jugada que produce el ahogado sea legal.
* La partida se declara tablas cuando se llega a una posición en la que ningún jugador puede dar jaque mate al Rey rival con ninguna serie de jugadas legales. Se dice que la partida termina en una 'posición muerta'. La partida termina inmediatamente, siempre que la jugada que produce la posición sea legal.
* La partida se declara tablas bajo mutuo acuerdo entre los jugadores durante la misma. La partida termina inmediatamente.
* La partida puede declararse tablas si cada jugador ha hecho al menos los últimos 50 movimientos consecutivos sin haber movido ningún Peón ni realizado ninguna captura.
* Tan pronto como a un jugador le queda solamente un Rey, debe observarse el número de piezas restantes del rival. La partida puede declararse tablas si el jugador que solamente tiene un Rey es capaz de escapar en un determinado número de jugadas (se realiza una cuenta que empieza desde el momento que el Rey se queda solo). Para determinar el límite de movimientos de los que el bando fuerte dispone para dar jaque mate, se usan estas reglas según el material del que dispone:
  * Rey solitario vs. Rey & una Torre	- 16 moves
  * Rey solitario vs. Rey & un Elefante & un General	- 44 moves 
  * Rey solitario vs. Rey & un Caballo & un General	- 64 moves

## Las Piezas

### Rey

![Rey](https://github.com/pychess/pychess-variants/blob/master/static/images/SittuyinGuide/King.png?raw=true)

El Rey mueve exactamente igual que en Ajedrez.

### General

![General](https://github.com/pychess/pychess-variants/blob/master/static/images/SittuyinGuide/General.png?raw=true)

A diferencia de la Dama del Ajedrez, el General es una pieza relativamente débil que solo mueve una casilla en diagonal. Se pueden conseguir Generales adicionales a través de la promoción de Peones.

El General vale entre 1.5 y 2 Peones en general. También es la única pieza que se puede renovar. El General es una buena pieza para liderar los ataques, útil para perseguir piezas enemigas de más valor. A veces, pueden también ser sacrificados a cambio de Peones enemigos bien posicionados, para abrir paso a una invasión.

Dado que es raro para un bando tener una ventaja de dos piezas, el General obtenido por promoción suele estar presente en muchos finales, apoyando al bando fuerte para dar jaque mate.

Para el bando débil, un General puede ser un buen señuelo que normalmente debe ser atrapado y capturado antes de que el Rey solitario pueda ser sometido a un jaque mate. El Rey puede permanecer cerca del General para una protección extra o, si esto no es posible, lo más lejos posible. Desperdigar las piezas enemigas de este modo le costará valiosos tiempos para reorganizarse, dando al bando débil opciones adicionales de salvar la partida según las reglas de conteo.

### Elefante

![Elefante](https://github.com/pychess/pychess-variants/blob/master/static/images/SittuyinGuide/Elephant.png?raw=true)

El Elefante mueve una casilla en diagonal o una casilla hacia adelante, exactamente igual que un General de Plata en Shogi.

El Elefante es una pieza poderosa para controlar las casillas inmediatamente enfrente, y para codear a las fuerzas enemiga. También es un buen defensor alrededor de su Rey.

El Elefante vale más que la Dama, pero generalmente no tanto como el Caballo. La justificación puede ser que un Caballo aislado tiene poco problema para escapar de un Rey enemigo, mientras que un Alfil aislado puede caer fácilmente.

Los Elefantes pueden resultar a veces torpes o lentos para maniobrar o retroceder. Es por tanto recomendable tener piezas amigas cerca para protegerlos y rescatarlos. En el final, es normalmente más seguro tener un Rey solitario detrás del Alfil enemigo que delante.

### Caballo

 ![Caballo](https://github.com/pychess/pychess-variants/blob/master/static/images/SittuyinGuide/Horse.png?raw=true)

El Caballo mueve exactamente como el Caballo en el Ajedrez.

Los Caballos no son "piezas menores" en Sittuyin. Son fuerzas mayores. Centralízalos y utilízalos.

### Carruaje

 ![Carruaje](https://github.com/pychess/pychess-variants/blob/master/static/images/SittuyinGuide/Chariot.png?raw=true)

El Carruaje mueve exactamente igual que la Torre del Ajedrez.

En ausencia de las poderosas Damas del Ajedrez, los Carruajes dominan el tablero. Los jaques laterales del Carruaje pueden ser especialmente molestos. Intenta llegar con el Carruaje a la séptima fila o incluso a la sexta.

### Señor Feudal

![Señor Feudal](https://github.com/pychess/pychess-variants/blob/master/static/images/SittuyinGuide/Pawn.png?raw=true)

El Peón, o Señor Feudal, mueve y ataca al igual que un Peón en el Ajedrez. Sin embargo, no puede mover dos casillas al principio.

**Promoción**: Después de que un Señor Feudal llega a la línea diagonal en el lado enemigo del tablero, el jugador puede escoger promocionarlo a un General en vez de moverlo. Esto se permite solamente *si* el general ya fue capturado previamente. La promoción no ocurre en el movimiento en el que el Señor Feudal llega a la casilla de promoción, sino en cualquier movimiento posterior. En el acto de promoción, el Señor Feudal puede promocionar en donde está situado o en cualquiera de las casillas adyacentes en diagonal. Sin embargo la promoción no puede ocurrir en una casilla en la cual el nuevo General se encontraría en posición de ataque (amenazando cualquier pieza enemiga). Si queda un Señor Feudal en el tablero, entonces tiene la capacidad de promocionar en su turno.

Finalmente, puedes decidir no promocionar un Señor Feudal que llega a la última fila, lo cual producirá un ahogado si esta era la última pieza que quedaba.

## Makruk vs Sittuyin
 
El Makruk es un juego muy similar al Sittuyin, pero jugado en Tailandia. En cierto sentido, el Sittuyin puede ser percibido como una especie de Makruk acelerado, que potencialmente ahorra alrededor de una docena de jugadas de apertura. La mitad de los Peones comienzan en la cuarta fila en Sittuyin, a diferencia del Makruk donde todos comienzan en la tercera fila.
 
Los jugadores de Makruk deben trabajar desde cero para conseguir una buena disposición de piezas en la apertura, una habilidad fundamental para el Makruk. Los jugadores de Sittuyin comienzan ya con una disposición ideal. La experiencia ganada en cualquiera de estas variantes es útil en la otra.
 
El Makruk permite promocionar Peones a múltiples Damas, lo cual puede volverse peligroso muy rápidamente. Esto hace que los Peones sean más valiosos en Makruk que en Sittuyin.

## Estrategia
 
El ritmo es más bien lento, con la mayoría de piezas avanzando solamente una casilla en cada jugada. Es buena idea organizar y agrupar juntas las piezas. Moverlas en formación como un grupo para protegerse mutuamente. No es recomendable abrir la partida en muchos frentes. La coordinación es clave.

## Táctica
 
**Los Carruajes son las únicas piezas que pueden hacer clavadas o enfiladas. El resto de tácticas se limitan fundamentalmente a ataques dobles.**

La mayoría de las partidas de Sittuyin y Makruk llegarán hasta el final de todo.
Cuando a un bando le queda solamente un Rey solitario, hay ciertas "reglas de conteo" (ver arriba) que se aplican y ponen presión al jugador con ventaja. Dichas reglas ofrecen al jugador en desventaja un incentivo para seguir jugando la partida completa. Por lo tanto es de vital importancia dominar todos los mates básicos contra un Rey solitario. No tiene mucho sentido jugar partidas si no eres capaz de rematar al Rey solitario al final.
 
Dado que no hay promoción a piezas mayores, resulta más difícil dar jaque mate cuando hay pocas piezas en el tablero. Es importante planear con esto en mente y conservar en la medida de lo posible el material suficiente para poder dar jaque mate.
 
También es recomendable gestionar bien el tiempo y reservar parte del mismo para esta fase de búsqueda del jaque mate, ya que suele requerir precisión.
 
