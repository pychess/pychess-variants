# ![Ajedrez Orda](https://github.com/pychess/pychess-variants/blob/master/static/icons/orda.svg) Ajedrez Orda

![Orda](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Orda.png)

![Leyenda](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/OrdaLegend.png)

El Ajedrez Orda es una variante diseñada en 2020 por Couch Tomato. La idea del juego era create una variante puramente asimétrica de Ajedrez con dos ejércitos diferentes. El Ajedrez de Ralph Betza con Ejércitos Diferentes fue una inspiración, pero el objetivo era estar un poco más alineado con la temática de aquí. En este caso, el tema del nuevo ejército se basa en el movimiento del Caballo, dado que la mayoría de piezas se mueven coo el Caballo. Dada dicha temática relacionada con el Caballo, el juego fue modelado en base al ejército Mongol y nombrado Orda. De hecho, una Orda era una estructura militar para la gente de la estepa. El ejército original del Ajedrez es nombrado el Reino por contraposición. El juego es increíblemente equilibrado de acuerdo a la valoración del ordenador (incluso más que el Ajedrez estándar), con aproximadamente un ratio de victorias de 50%/50% para Reino y Orda.
 
## Reglas Generales
1.	La posición inicial es según se muestra arriba. A pesar de las nuevas piezas, la ubicación de las piezas de la Orda refleja a sus contrapartidas de Ajedrez.
2.	Las únicas piezas que los bandos tienen en común son los Peones y los Reyes (el Rey de la Orda se llama Khan).
3.	El Reino (Blancas) *siempre mueve primero*.
4.	La Orda (Doradas) no se puede enrocar.
5.	Como los Peones de la Orda comienzan en la tercera fila, no tienen la opción de mover dos casillas o ser capturados al paso. Los peones del Reino mantienen la capacidad de mover dos casillas inicialmente y de ser capturados al paso.
6.	Los Peones *de ambos bandos* pueden promocionar únicamente a una Dama o Kheshig.
7.	Existe un método adicional de conseguir la victoria: **camp mate**. El camp mate se consigue llegando con nuestro propio Rey a la última fila sin ponerlo en jaque.
8.	El resto de reglas, incluyendo ahogados y repeticiones, son como en el Ajedrez.

## Piezas de la Orda
Hay cuatro nuevas unidades *en la Orda: 2 Lanzas, 2 Arqueros, 2 Kheshigs y 1 Yurta* (con la excepción de que el Reino todavía puede obtener un Kheshig mediante promoción). Los Kheshigs son la pieza más poderosa (movimientos de Caballo + Rey) y lideran cada flanco, mientras que la Yurta es una pieza bastante débil en comparación con la Dama.
El Rey de la Orda se denomina Khan y se representa con un símbolo diferente, pero es esencialmente la misma pieza que el Rey del Reino, y utiliza la misma abreviatura (K) - el cambio es puramente estético y temático.
La Lanza y el Arquero de la Orda son únicas en que capturan diferente a como mueven. Recuerda que la Orda se basa en el movimiento del Caballo, así que la Lanza y el Arquero mueven ambos como Caballos. Capturan/dan jaque como Torres y Alfiles, respectivamente. El Kheshig es más tradicional en el sentido de que captura de la misma forma que mueve; combina los movimientos del Caballo y el Rey. De forma parecida, la Yurta también captura de la forma en que mueve; mueve como el General de Plata del Shogi.

Pieza de la **Orda**	| "Contrapartida" del **Reino** “counterpart”	| Movimiento | Captura/Jaque
-- | -- | -- | --
Yurta | Dama | “General de Plata” | “General de Plata”
Arquero | Alfil | Caballo | Alfil
Kheshig | Caballo | Caballo+Rey | Caballo+Rey
Lanza | Torre | Caballlo | Torre

A continuación se muestran detalles y diagramas de cada pieza. Los puntos verdes representan movimiento, los puntos rojos representan captura, y los amarillos representan ambos.
 
### Yurta (Y)

![Yurta](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Yurt.png)
 
La Yurta mueve y captura un espcio en diagonal y un espacio hacia adelante. Es similar al General de Plata del Shogi o el Alfil/Khon del Makruk. Solo hay una Yurta, que comienza la partida en la casilla de la Dama, pero a diferencia de la Dama, es una pieza mucho menor, la más débil del juego al margen de los Peones. No debe ser subestimada, sin embargo, ya que es una de las pocas piezas de Orda que puede mover y capturar del mismo modo. Las otras dos son el Khan y el Kheshig, que son las piezas más valiosas. Por lo tanto, la Yurta desempeña la especial labor de proteger a Peones y otras piezas sin miedo a represalias.
Una Yurta es una casa móvil de los pueblos Mongol y Túrquico en las estepas de Asia. Su limitada movilidad pero importancia para proteger al ejército son reflejadas en esta pieza.

### Kheshig (H)

![Kheshig](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Kheshig.png)
 
El Kheshig es una pieza híbrida que mueve y captura como un Caballo y un Rey combinados. Este tipo de pieza es generalmente denominada centauro. El Kheshig comienza en el lugar del Caballo, pero a diferencia del Caballo, es la pieza más poderosa de la Orda. Podemos pensar en ella como un General que lidera su propia tropa en cada flanco. Generalmente  es preferible mantener a los Kheshigs a salvo en posiciones retrasadas durante las primeras fases de la partida, debido a su extremada importancia para la Orda en los finales.
Los Kheshigs eran la guardia imperial de la realeza Mongol. Adecuadamente, es increíblemente difícil para el Reino dar jaque mate al Khan sin al menos eliminar uno de sus Kheshigs primero.

### Arquero (A)

![Arquero](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Archer.png)
 
El Arquero, o Caballo Arquero, es una pieza semihíbrida única que mueve y ataca de formas diferentes. El Arquero se mueve como el Caballo pero captura como el Alfil. Dado que el Arquero no va por un único color, su valor es mayor que el de su contrapartida el Alfil.
Los Arqueros eran uno de los dos componentes principales de la caballería Mongol, y funcionaban como caballería ligera. Su velocidad y gran habilidad como Arqueros montados les convertía en una amenaza única. Su habilidad para posicionarse rápidamente para una enfilada o double ataque les convierte en una amenaza muy peligrosa para el Reino.
 
### Lanza (L)

![Lanza](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Lancer.png)
 
La Lanza es una pieza única semihíbrida que mueve y ataca de formas diferentes. La lanza mueve como un Caballo pero captura como una Torre.  Dado que la Lanza no es tan móvil como la Torre, su valor es generalmente inferior al de la Torre, y esto se pronuncia más en el final, ya que no se puede mover por el tablero tan rápido como una Torre. Su valor es comparable al de un Arquero.
Las lanzas eran uno de los componentes fundamentales de la caballería Mongol, funcionando como caballería pesada. A pesar de ser más débiles que la Torre, su habilidad para entrar en juego mucho antes en la partida es una ventaja que el jugador de Orda debería utilizar.

 
## Valores de las Piezas

Los valores precisos de las piezas son desconocidos. Sin embargo, estos son los valores utilizados por Fairy Stockfish, precisando que son valores genéricos, no necesariamente específicos al Ajedrez Orda:

Pieza del Reino	| Valor (Temprano / Tarde) | Pieza de Orda | Valor (Temprano / Tarde)
-- | -- | -- | --
Peón | 120 / 213	| Peón | 120 / 213
Dama | 2538 / 2682	| Yurta | 630 / 630
Alfil | 825 / 915	| Arquero	| 1100 / 1200
Caballo | 781 / 854	| Kheshig | 1800 / 1900
Torre| 1276 / 1380	| Lanza | 1050 / 1250

Para aquellos que quieran un enfoque más simiplificado, la siguiente tabla puede ser una aproximación.

Pieza del Reino	| Valor | Pieza de Orda	| Valor
-- | -- | -- | --
Peón | 1	| Peón | 1
Dama	| 9	| Yurta | 2
Alfil | 3 | Arquero | 4
Caballo | 3 | Kheshig | 7
Torre | 5 | Lanza | 4

## Estrategia
El juego todavía es joven, por lo que la estrategia todavía está desarrollo. La mayoría de la información está basada en el juego de ordenador.

La Orda no puede enrocar. Sin embargo, un componente fundamental de la mayoría de aperturas en Orda es mover el Khan a g7. Llegar a esta casilla en las primeras cuatro jugadas es ideal - de hecho, Fairy Stockfish abre con Kf7 en un 56% de sus partidas. El resto es variable.
Para el Reino, d4, g3 y b3 son las aperturas más comunes en ese orden.

Una debilidad importante de la Orda es que las Lanzas y los Arqueros no pueden mantener una amenaza en una pieza. Si atacas a una Lanza/Arquero, si deben retroceder, perderán su ataque. Es importante para el Reino sacar partido de esta circunstancia.

### Aperturas

Lo siguiente se basa en un análisis de las primeros movimientos jugados por Fairy Stockfish contra sí mismo

Primera jugada Blancas	| Porcentaje de partidas (número) | Blancas Ganan % | Doradas Ganan  % | Respuesta Doradas
-- | -- | -- | -- | --
d4 | 38%	(47) | 45% | 38% | Kf7 ~= c5 >> Hb7
g3	| 24% (30)	| 33% | 43% | Kf7 >> d5
b3 | 14% (18) | 33% | 44% | Kf7 >> Lc7
e3 | 11% (14) | 50% | 50% | Kf7 ~50% del tiempo
d3 | 6% (8) | 25% | 25% | e5 ~=Kf7
Nf3 | 3% (4) | 25% | 50% | e5 always
e4 | 2% (3) | 33% | 67% | d5
c4 | 1% (1) | 100% | 0% | Kf7

Algunas líneas particulares han sido también jugadas en múltiples partidas. Aquí tenemos las cuatro más comunes. Usaremos el nombre "enroque" para cualquier variación en la que la Orda resguarda su Khan en f7 tan pronto como sea posible. Las últimas jugadas entre paréntesis indican donde las variaciones empiezan a ocurrir significativamente.

**Enroque de Benko - Apertura de Doble Esquina** - Apertura más común
1. g3 Kf7
2. e4 Kg7
3. (Bd3 or Nf3) ...

![Enroque de Benko](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/BenkoCastle.png)

*Enroque de Benko después de 2... Kg7*

**Defensa Stockfish - Variante Cerrada**
1. d4 c5
2. dxc5 *bxc5*
3. c4 Kf7
4. (Nc3) ...

**Defensa Stockfish - Variante Abierta**
1. d4 c5
2. dxc5 *dxc5*

**Defensa Stockfish - Avance de Flanco de Dama**
1. d4 c5
2. *e3* cxd4
3. exd4 b5
4. b3 Kf7
5. c4

![Defensa Stockfish Avance de Flanco de Dama](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/QueensidePush.png)

*Defensa Stockfish- Avance de Flanco de Dama después de 5. c4*
