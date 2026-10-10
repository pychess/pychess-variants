# ![Atomic](https://github.com/pychess/pychess-variants/blob/master/static/icons/Atomic.svg) Atomic

Fai esplodere il re avversario per vincere!

## Regole

* In aggiunta alle regole standard, tutte le catture causano un'esplosione con la quale il pezzo catturato, il pezzo usato per la cattura e tutti i pezzi circostanti, tranne i pedoni, che si trovano nel raggio di una casella vengono rimossi dalla scacchiera.
* È illegale catturare un pezzo che farebbe saltare in aria il tuo re, né un re può catturare qualsiasi pezzo perché, secondo le regole Atomic, il pezzo catturato esplode e viene rimosso dal gioco.
* Lo scacco matto tradizionale si applica anche all'Atomic, **ma qualsiasi mossa che risulti nel far esplodere il re nemico risulterà in una vittoria immediata, scavalcando in priorità tutti gli scacchi e gli scacco matto.**

Questo studio Lichess spiega le regole Atomic nel dettaglio: [https://lichess.org/study/uf9GpQyI](https://lichess.org/study/uf9GpQyI)

## Chiarimenti

In Atomic i re possono "toccarsi" muovendone uno nelle caselle adiacenti al re dell'altro lato. **Quando i re sono adiacenti, gli scacchi non hanno valore.** La logica che sta dietro alla regola è semplice: poiché è illegale con una cattura far esplodere il proprio re, non è possibile catturare direttamente l'altro re, visto che si trova accanto al proprio. Per vincere un tale finale, è necessario provocare il distacco dei re per zugzwang o far esplodere un pezzo del colore opposto mentre il re è accanto ad esso.
