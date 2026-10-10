# FAQ

## Pychess

*¿Qué es Pychess?* 

Pychess es un sitio web dedicado a permitir a las personas jugar variantes de ajedrez principales e interesantes (tanto regionales como variantes de ajedrez más modernas). Por favor lee [la pagina Acerca de](https://www.pychess.org/about).

*¿Por qué se llama Pychess?*

El código del servidor está escrito en Python.

*¿Cuál es la diferencia entre el sitio y el software?*

Ambos están diseñados para jugar a variantes de ajedrez, y ambos comparten el mismo desarrollador ([gbtami](https://www.github.com/gbtami)). Sin embargo, las similitudes terminan ahí. El nombre completo para este sitio es "Pychess Variants" por distinción, pero normalmente se le llama simplemente Pychess. El sitio para la aplicación de escritorio se encuentra [aquí](https://pychess.github.io/).

*¿Cuál es la relación con [Lichess](https://lichess.org/)?*

El diseño de Pychess está influenciado enormemente por Lichess y está pensado para ser agradable para usuarios de Lichess. Pychess no tiene relación oficial alguna con Lichess. Sin embargo, utiliza cuentas de Lichess para facilitar la gestión de los usuarios.

*¿Qué es Fairy-Stockfish?*

Stockfish es uno de los principales motores de ajedrez disponibles. [Fairy-Stockfish](https://github.com/ianfab/Fairy-Stockfish) es un fork del mismo crado por [Ianfab](https://www.github.com/ianfab) para soportar múltiples variantes.

*¿Es el nivel 8 de Stockfish el más fuerte disponible?*

Es el más fuerte disponible en este sitio, pero no representa Fairy-Stockfish a plena potencia. La máxima potencia requiere más tiempo para pensar y analizar; en Pychess, Stockfish está limitado a menos de un segundo por cada jugada.

*¡Encontré un bug! ¿Dónde lo reporto?*

[**Crea una incidencia**](https://github.com/pychess/pychess-variants/issues/new). De un modo u otro, debe terminar registrado el registro de incidencias de Github. Idealmente, intenta encontrar una forma de reproducir el bug e inclúyela en tu descripción (si es necesario, incluye el navegador y sistema operativo). Si no estás en Github, también puedes mencionarlo en Discord y alguien lo podrá registrar por ti.

## Variantes

*¿Qué variantes están disponibles?*

Lee [la página Aprender](https://www.pychess.org/variants) para ver la lista completa.

*¿Cómo se juega a XXX?*

Lee [la página Aprender](https://www.pychess.org/variants). También, durante una partida, puedes hacer click en el nombre de la variante en la esquina superior izquierda y te llevará a la correspondiente página en Aprender.

*¿Cómo escogéis qué variantes añadir?*

Las variantes regionales principales tienen mayor prioridad. Para variantes de ajedrez occidental, normalmente las más populares o conocidas han sido añadidas. Sin embargo, hay algunas que todavía no pueden ser añadidas. Pychess depende de que Fairy-Stockfish soporte la variante, ya que nuestro código también depende de Fairy-Stockfish para la validación de movimientos. Esto también significa que ninguna variante no soportada por Fairy-Stockfish puede estar en Pychess.

*¿Podéis añadir Shatranj?*

Shatranj es una variante muerta, y hay juegos similares todavía en uso (ej. Makruk), así que no. Si quieres jugar Shatranj, hay otros sitios que la ofrecen (ej. [VChess](https://vchess.club/#/))

*¿Podéis añadir XXX?*

Depende de cómo de popular o interesante sea la variante. No podemos ni siquiera considerar añadir variantes no soportadas por Fairy-Stockfish. En cualquier caso, puedes preguntarnos en Discord o Github.

## Interfaz

*¿Cómo cambio los ajustes?*

Para cambiar los ajustes, haz click en el botón con forma de ruedecilla en la esquina superior derecha de la pantalla (al lado del login o nombre de usuario) y escoge "Preferencias del tablero".

*¿Cómo cambio las piezas y el tablero? ¿Existen juegos de piezas occidentales o internacionalizados?*

Misma respuesta que a la anterior pregunta, y haz click en "Preferencias del tablero". Todas las variantes Asiáticas disponen de piezas internacionalizadas.

*¿Cómo dibujo flechas y círculos en el tablero?*

Usa el click derecho del ratón. Hacer click te da un círculo, mientras que arrastrar te da una flecha. Son verdes por defecto. Puedes hacerlos rojos presionando Shift o Ctrl, y azules presionando Alt.

*¿Qué significa "5+3" referido al tiempo?*

Es el control de tiempo para la partida. Por defecto usamos un sistema de incremento. "5+3" significa que cada jugador dispone de 5 *minutos*, y tras cada movimiento se añaden 3 *segundos* al reloj. Puedes seleccionar cualquier control de tiempo cuando creas la partida. 5+3 es simplemente el control de tiempo por defecto del bot Random-Mover.

*Vale, ¿y entonces qué es la (b) en "5+3(b)"?*

La b indica un control de tiempo byo-yomi, que es diferente del sistema de incremento, y se utiliza solamente en ciertas variantes (ej. Shogi y Janggi). Cada jugador tiene un banco de tiempo fijo (5 minutos, en este ejemplo), y después de que estos se agoten, solo disponen del periodo byo-yomi para el resto de movimientos antes de perder. En este ejemplo, esto significa solamente 3 segundos por movimiento. Normalmente se juega byo-yomi con más de 3 segundos... típicamente algo entre 10 y 30 segundos.

*¿Qué es Random-Mover?*

Random-Mover es un bot que simplemente escoge un movimiento de la lista de opciones disponibles. Es una buena forma de familiarizarse con los movimientos de las piezas y algunas de las reglas. Pero es muy recomendable entrenar contra Fairy-Stockfish (incluso a un nivel bajo) una vez que conoces las reglas.

## Social/Cuentas

*¿Cómo hago login?*

Necesitas tener una cuenta en Lichess. Si todavía no la tienes, por favor ve a [Lichess](https://lichess.org/) para crearla.

*¿Hacer login en Lichess puede comprometer mi usuario/contraseña?*

¡No! Este proceso se hace mediante OAuth y tu contraseña nunca es compartida con Pychess, del mismo modo que puedes hacer login en otras páginas con tu cuenta de Google o Facebook.

*¿Por qué no puedo enviar mensajes en el chat del vestíbulo?*

El chat del vestíbulo está destinado a jugadores activos de Pychess. Para escribir allí, tu cuenta debe tener al menos 24 horas, debes haber completado al menos 10 partidas y al menos 5 de ellas deben ser partidas clasificatorias de variantes distintas del ajedrez estándar. Todavía puedes leer el chat del vestíbulo, y esta restricción no afecta al chat de las partidas ni de los torneos.

*¿Cuál es la mejor forma de contactar a los desarrolladores?*

Puedes intentarlo en la sala de chat, aunque los desarrolladores pueden no estar para responder. Más fiable es [Discord](https://discord.gg/aPs8RKr).

*¿Cómo se financia el sitio?*

Puramente a través de donaciones. ¡Puedes [ser un Mecenas](https://www.pychess.org/patron) para ayudarnos a mejorar el sitio!

*¿Puedo contribuir?*

¡Por supuesto que puedes! Pychess es open source. Por favor comunica tus sugerencias en [Github](https://github.com/pychess/pychess-variants) o [Discord](https://discord.gg/aPs8RKr)



