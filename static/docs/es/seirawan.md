# ![Seirawan](https://github.com/pychess/pychess-variants/blob/master/static/icons/schess.svg) S-chess (Ajedrez Seirawan, Ajedrez SHARPER)

S-chess fue creado por Yasser Seirawan y Bruce Harper en 2007. El juego se desarrolla en un tablero de 8x8 pero añade un giro con dos nuevas piezas a través del proceso de embarque (introducir las piezas en el tablero reemplazando vacantes en la primera fila).

## Reglas

Se juega en un tablero de 8x8. El **elefante** es el híbrido Torre/Caballo, mientras que el **Halcón** es el híbrido Alfil/Caballo. Ambas piezas comienzan fuera del tablero, aunque no pueden ser soltadas como en Crazyhouse.

En lugar de ello, cuando una pieza en la primera fila del jugador se mueve por primera vez, estas piezas pueden opcionalmente ser colocadas en la casilla evacuada por aquella pieza. Si todas las piezas de la primera fila han sido movidas o capturadas, cualquier Elefante o Halcón restante ya no puede ser introducido al juego. Con el enroque, las piezas extra pueden o bien entrar en la casilla original del Rey o de la Torre. El Rey no puede estar en jaque durante este proceso, similar al enroque normal.

Los Peones solamente pueden promocionar a Elefantes o Halcones.

## Piezas Nuevas

### Halcón

![Halcón](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Hawk.png)

El Halcón (H) es una pieza compuesta que combina los movimientos del **Alfil** y del **Caballo**. En el ámbito de las piezas de fantasía, esta pieza se conoce con el nombre genérico de Princesa, pero tiene también otras denominaciones en diferentes variantes.

El Halcón es la única pieza que puede dar jaque mate por sí sola, lo cual se puede apreciar fijándonos en su patrón de movimiento/ataque.

El valor de un Halcón es considerado ligeramente mejor que una Torre, pero menos que un Elefante o una Dama.

### Elefante

![Elefante](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ElephantSeirawan.png)

El Elefante (E) es una pieza compuesta que combina los movimientos del **Torre** y del **Caballo**. En el ámbito de las piezas de fantasía, esta pieza se conoce con el nombre genérico de Emperatriz, pero tiene también otras denominaciones en diferentes variantes.

El valor de un Elefante es considerado mejor que un Halcón, pero equivalente o ligeramente inferior a una Dama.

## Estrategia

Según Yasser Seirawan, proteger al Rey es incluso más importante en este juego porque un ataque por una pieza de largo alcance como una Dama, Alfil o Torre, puede inmediatamente ser apoyado con la incorporación de un Halcón o Elefante, llevando en algunos casos al jaque mate.
Recomendamos [https://www.chess.com/blog/catask/s-chess-ramblings-1](https://www.chess.com/blog/catask/s-chess-ramblings-1) por catask a todo el mundo.

También puedes ver este stream de Yasser Seirawan jugando contra JannLee:

<iframe width="560" height="315" src="https://www.youtube.com/embed/ujWzsxm18aQ" frameborder="0" allowfullscreen></iframe>
