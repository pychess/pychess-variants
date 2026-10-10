# ![Shogun](https://github.com/pychess/pychess-variants/blob/master/static/icons/shogun.svg) Ajedrez Shogun

![Shogun](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ShogunPromotions3.png)

El Ajedrez Shogun es una variante de Ajedrez diseñada en 2019-2020 por Couch Toato. Mientras que el juego es una mezcla de Ajedrez occidental y Shogi, la idea original para el mismo era introducir las piezas híbridas (normalmente conocidas como Cardenal y Mariscal) de una forma distinta a la habitual en otras variantes. Por ejemplo, manteniendo un tablero de 8x8 en lugar de agrandar el tablero, de modo que el valor de las piezas menores no disminuye, o introduciéndolas en un tablero que no esté tan ocupado como en S-Chess. La idea evolucionó a introducir estas piezas a través de la promoción de piezas menores y Torre en una fila más cercana que la octava. Después, se introdujo la opción de soltar piezas para incrementar las capacidades ofensivas y así compensar la naturaleza defensiva introducida por la necesidad de protegerse de las promociones. Las promociones únicas de Peones y Caballos, así como incluso la degradación de la Dama fueron añadidas para completar el tema y la simetría.

El nombre tentativo original fue "Ajedrez de los Generales", basado en lo que entonces era el nombre para la promoción de los Peones, que actualmente es el nombre para la promoción de los Caballos. Sin embargo, con la opción de soltar piezas y las zonas de promoción basadas en el Shogi, la palabra japonesa para "General" ("Shogun") sonaba más adecuada. Siendo el "sho" en "shogun" el mismo que en "shogi" también sirve para rendirle un tributo al mismo.

## Reglas Generales

1. La posición inicial es la misma que en Ajedrez.

2. Se definen nuevas piezas de acuerdo a la imagen arriba, y sus movimientos están descritos en detalle abajo. Nótese que los bandos promocionados tienen un color diferente. También, la Dama **comienza** como pieza promocionada en lugar de su forma no promocionada (la Duquesa). Por consistencia en la terminología, la Torre será considerada ahora una "pieza menor", mientras que la Dama, el Mortero, el Cardenal y el General (pero NO el Capitán) son consideradas "piezas mayores".

3. Las tres filas más distantes son la zona de promoción. Cada pieza inicial o soltada excepto el Rey y la Dama pueden promocionar al mover en la zona de promoción o **moviendo dentro de la zona de promoción**.

4. Sin embargo, solamente una de *cada* **pieza mayor** (Dama, Mortero, Cardenal o General) puede estar fuera en cada momento por bando. Por ejemplo, si un jugador tiene un Cardenal en juego, luego un Alfil no puede promocionar a Cardenal hasta que el que está en juego sea capturado.

5. Al igual que en Crazyhouse y Shogi, las piezas capturadas pueden ser soltadas en el tablero como piezas propias. Las piezas pueden ser soltadas en cualquier sitio en las primeras 5 filas (es decir, cualquier sitio excepto en la zona de promoción). Nótese que a diferencia de Crazyhouse, **los Peones pueden ser soltados en la primera fila**,

6. Cuando una pieza promocionada es capturada, vuelve a su versión no promocionada. Este es el único modo de obtener una Duquesa.

Reglas menores adicionales a modo de aclaración:
* Torres soltadas no pueden ser usadas para enrocar, como en Crazyhouse.
* Los Peones soltados en primera fila pueden todavía mover dos casillas cuando llegan a la segunda fila.
* Los Peones no pueden promocionar con una captura al paso.

(Nótese que las imágenes fueron diseñadas para el juego por ordenador. Las piezas usadas para el juego en tablero físico no están disponibles pero requerirían diseños al estilo del Shogi con piezas direccionales de dos caras para ser viables.

*Reloj* - El Ajedrez Shogun utiliza un reloj byo-yomi.  Una vez que el tiempo principal se acaba, el jugador entre en byo-yomi. Si está configurado a 30 segundos, el jugador solamente dispondrá de 30 segundos para realizar cada movimiento a partir de ese momento o si no, perderá la partida. La razón para usar byo-yomi en vez del incremento de Fischer es que los finales llevan más tiempo que las aperturas, por lo que el byo-yomi garantiza un tiempo para cada jugada.

## Piezas

### Cardenal (A)

![Cardenal](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ArchbishopShogun.png)

El Cardenal es una pieza híbrida que combina los movimientos del **Alfil** y el **Caballo**. En este juego, aparece cuando promocionamos un Alfil y se le añade el movimiento del Caballo. Debido a su movimiento especial, es la única pieza que puede dar jaque mate por sí sola.

### Mortero (M)

![Mortero](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Mortar.png)

El Mortero es una pieza híbrida conocida en otras variantes como Canciller o Mariscal, que combina los movimientos del **Torre** y el **Caballo**. En este juego, aparece cuando promocionamos una Torre y se le añade el movimiento del Caballo.

### General (G)

![General](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/General.png)

El General es una pieza híbrida, normalmente conocida como Centauro. En este juego, aparece cuando promocionamos un Caballo y se le añade el movimiento del Rey.

### Capitán (C)

![Capitán](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Captain.png)

El Capitán es la única promoción del Peón y mueve exactamente igual que un Rey. Capturar un Capitán no termina el juego. Además, a diferencia del resto de piezas promocionadas, puede haber múltiples Capitanes, ya que no es una pieza mayor.

### Duquesa (F)

![Duquesa](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Duchess.png)

La Duquesa es la forma degradada de la Dama, y solo entra en juego cuando una Dama es capturada y pasa a ser una Duquesa en mano. La Duquesa mueve solamente un espacio en diagonal (mismo movimiento que lo que normalmente se denomina "Ferz", y de ahí que su abreviatura sea F). Recordemos que una Duquesa no puede promocionar a Dama cuando el jugador ya tiene una Dama en juego (la poligamia no está permitida en Ajedrez Shogun).

## Estrategia

El juego es todavía reciente, así que la estrategia está en desarrollo.

Con las promociones en sexta fila, es importante proteger tu propia tercera fila. Esto es algo que un principiante puede fácilmente pasar por alto.

En términos de estrategia general, muchos jugadores estarán tentados de jugar al estilo del Crazyhouse. Sin embargo, el juego se desvía rápidamente del Crazyhouse debido a la restricción de la zona donde se pueden soltar piezas. Mientras en Crazyhouse los jugadores suelen tratar de aprovechar las debilidades en el capmo enemigo soltando piezas de forma devastadora, el juego en Shogun es más defensivo, dado que el ejército necesita maniobrar para conseguir abrir una brecha en el campo enemigo; la más pequeña brecha puede ser suficiente para una incursión que lleve a una promoción de pieza. Por tanto, la estrategia gira más en torno a táctica de Ajedrez que de Crazyhouse para este propósito, así como para el propósito de dar jaque mate.

La capacidad de soltar peones en la primera fila (a diferencia de Crazyhouse) permite a los jugadores construir un enroque más fuerte. Para romperlo, enfócate en ganar material y promocionar piezas, y después presiona el punto débil.
