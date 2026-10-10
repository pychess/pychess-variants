# ![Atomic](https://github.com/pychess/pychess-variants/blob/master/static/icons/Atomic.svg) Atomic

¡Explota al rey contrario para ganar!

## Reglas

* A mayores de las reglas habituales, todas las capturas causan una explosión por la cual la pieza capturada, la pieza usada para capturar y todas las piezas circundantes, excepto los peones, que se encuentran a una casilla de distancia son eliminadas del tablero.
* Es ilegal capturar una pieza que haga explotar a tu propio rey, y tampoco es posible capturar ninguna pieza con el rey, ya que según las reglas de Atomic la pieza usada para capturar explota y es eliminada del tablero.
* El jaque mate tradicional se aplica también en Atomic, **pero cualquier jugada que haga explotar al rey adversario te otorga la victoria inmediatamente, anulando cualquier jaque o jaque mate de tu rival.**

Este estudio en Lichess explica las reglas de Atomic en detalle: [https://lichess.org/study/uf9GpQyI](https://lichess.org/study/uf9GpQyI)

## Aclaración

En Atomic los reyes pueden "tocarse" moviéndose uno de ellos a una casilla adyacente al otro. **Cuando los reyes están conectados los jaques no se aplican.** La lógica detrás de esta regla es simple: no es posible explotar tu propio rey, por lo que con los reyes conectados es imposible capturar al rey adversario directamente. Para ganar un final de este tipo, es necesario forzar la desconexión de los reyes mediante zugzwang o explotar una pieza que toque al rey rival pero no al tuyo.
