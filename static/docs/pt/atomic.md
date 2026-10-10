# ![Atomic](https://github.com/pychess/pychess-variants/blob/master/static/icons/Atomic.svg) Atomic

Exploda o rei do seu adversário para ganhar!


## Regras

* Para além das regras de xadrez normais, todas as capturas causam uma explosão na qual a peça capturada, a peça que foi usada para capturar e todas as outras adjacentes (excluindo os peões) por uma casa são removidas do tabuleiro.
* Não é permitido a captura de uma peça que pode por ventura remover o seu próprio rei do tabuleiro, Além disso o Rei está impossibilitado de capturar. De acordo com as regras do Xadrez Atómico, a peça que captura explode e é removida do tabuleiro.
* As regras de Mate tradicionais também são aplicadas no Xadrez Atómico, **no entanto qualquer jogada que exploda o Rei adversário dará vitória imediata, ignorando assim xeques e xeque-mate.**

Este estudo feito no Lichess explica todas as regras do Xadrez Atómico em detalhe: [https://lichess.org/study/uf9GpQyI](https://lichess.org/study/uf9GpQyI)

## Esclarecimentos

No Xadrez Atómico ambos os reis podem estar próximos um do outro por casas adjacentes. **Quando os reis estão ligados, o xeque não é aplicado.** Pelo facto de não ser permitido a explosão do próprio Rei, não é possível capturar o Rei adversário diretamente. A fim de ganhar um jogo com reis conectados, será necessário forçar uma quebra na ligação entre os reis por zugzwang ou explodir uma peça adversária em que o rei adversário esteja próximo.
