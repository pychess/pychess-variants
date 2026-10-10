# ![Makruk](https://github.com/pychess/pychess-variants/blob/master/static/icons/makruk.svg) Makruk

![Makruk](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Makruk.png?raw=true)

*Makruk*, ou Xadrez Tailandês, é um jogo de tabuleiro classico proveniente da Tailandia e é um descendente chegado do Chaturanga, o mesmo antepassado do Xadrez. É jogado na Tailandia e na Cambodia, onde é conhecido como *Ouk Chatrang* (com algumas regras diferentes). O Makruk desmonstra caracteristicas semelhantes ao Xadrez antigo na sua forma original antes de serem introduzidas regras modernas que aceleraram o seu ritmo. O jogo é muito divertido no seu estilo, com o seu próprio dinamismo. O seu ritmo mais lento demonstra ser capaz de construir a paciência e o poder estratégico de pensamento.

O antigo campeão de Xadrez Vladimir Kramnik já experimentou Makruk e deu a sua opinião, "O Xadrez Makruk é mais estratégico do que o Xadrez Internacional. Tens de planear todas as tuas jogadas com extremo cuidado devido ao facto do Makruk ser comparado a um fim-de-jogo antecipado de Xadrez Internacional."
 
Da perspectiva de um jogador de Xadrez, isto corresponde à realidade. Pelo facto de, uma aproximação óbvia seria trocar as peças não familiares: o Bispo (Khon) e a Dama (Met), e entrar (possivelmente) num fim-de-jogo favorável. Mas esta aproximação é de certa maneira maçante e convida ao empate. É muito mais divertido levar avante os diferentes dinamismos em vez disto, e tentar jogar com o novo tipo de peças.

## Regras

As regras gerais são extremamente semelhantes ao Xadrez, dai que este guia se irá focar nas pequenas diferenças. O objetivo é o mesmo: dar Xeque-Mate ao Rei adversário. A maior diferença reside em algumas peças terem diferentes tipos de movimento e diferentes posições iniciais: Peões na terceira linha e o Rei está no lado esquerdo do jogador independentemente da cor. Rei afogado dará empate, como no Xadrez.

## As Peças

O nome das peças em Tailandês está entre parêntesis. 

### Rei (*Khun*)

![King](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/King.png?raw=true)

O Rei movimenta-se uma casa na ortogonal e na diagonal. Não existe roque como no Xadrez.

### Dama (*Met*)

![Queen](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Queen.png?raw=true)

Ao contrário da Dama no Xadrez, esta é relativamente fraca sendo a única que se move apenas uma casa na diagonal.

A Dama vale desde 1.5 até 2 Peões no geral. A Dama é uma excelente peça para liderar os ataques, útil para incomodar peças adversárias mais valiosas. Ocasionalmente, estas podem ser sacrificadas por Peões adversários que estejam bem posicionadas, a fim de criar caminho para invasões.

### Bispo (*Khon*)

![Bishop](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Bishop.png?raw=true)

O Bispo movimenta-se uma casa na diagonal ou uma casa para a frente, como o General Prateado em Shogi.

O Bispo é uma peça poderosa para controlar casas em frente, e para contrair forças adversárias. Também é um excelente defesa à volta do seu Rei.
 
O Bispo é mais valioso do que a Dama, mas geralmente não tanto como o Cavalo. Isto pelo facto de que Cavalos isolados não têm problemas em se escapar do Rei inimigo, enquanto que Bispos isolados têm mais facilidade em ser capturados.
 
Os Bispos podem porventura ser lentos/desastrados em questões de manobra ou retirar. Daí ser aconselhado ter sempre peças por perto deste a fim de os acolher. No fim-de-jogo, é mais seguro ter um Rei só atrás de um Bispo adversário ao invés de ficar em frente a este.

### Cavalo (*Ma*)

 ![Knight](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Knight.png?raw=true)

O cavalo move-se exatamente como no Xadrez.

Os Cavalos não são "peças menores" em Makruk. Eles são peças relevantes. Centraliza-as e utiliza-as.

### Torre (*Ruea*)

 ![Rook](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Rook.png?raw=true)

A Torre move-se exatamente como no Xadrez.

Considerando que não existem peças como a Dama do Xadrez, as Torres têm dominio no tabuleiro. Xeques laterais da Torre podem ser irritantes. Faça com que a sua Torre atinja a sétima linha ou mesmo a sexta.

### Peão (*Bia*)

![Pawn](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Pawn.png?raw=true) ![ProPawn](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/ProPawn.png?raw=true)

O Peão movimenta-se e ataca exatamente como no Xadrez. No entanto, não existem jogadas de duas casas no inicio. Os peões são promovidos e movimentam-se como a Dama quando atinjem a sexta linha.

Como é raro um dos lados ter vantagem de duas peças, o Peão promovido está constantemente presente em grande parte dos finais de jogo, e este assiste o lado com vantagem a dar Xeque-Mate.
 
Para o lado em desvantagem, o peão promovido é um bom isco porque deve ser rodeado e capturado antes de que se possa dar Xeque-Mate ao Rei. Este pode ficar junto ao Rei, para proteção adicional, ou falhando isto, afugenta peças adversárias. Espalhando assim as peças adversárias pode custar tempo valioso na reorganização, dando maior manobra defensiva ao lado em desvantagem e uma maior chance de empatar o jogo sob regras de contagem (Ver abaixo).

## Regras de Contagem

When neither side has any unpromoted pawns, the game must be completed within a certain number of moves or it is declared a draw. In real games, the disadvantaged player verbally counts his moves according to these rules.

### Contagem de Honra do Tabuleiro

Quando não existem Peões não promovidos no tablureiro, o jogador em desvantagem pode começar a contagem de honra no tabuleiro. A contagem começa em 1, e o Xeque-Mate tem de ser dado em 64 lances (isto é, antes da contagem chegar a 65) ou o jogo terminará em empate. O jogador pode escolher parar de contar a qualquer altura, mas se qualquer jogador pretender contar outra vez, A contagem irá reeniciar para 1. Se o jogador em desvantagem dar Xeque-Mate ao jogador em vantagem e não parou a contagem, o resultado terminará em empate.

### Contagem de Honra das Peças

Quando não existirem peões não promovidos no tabuleiro e a última peça (que não seja o Rei) do jogador em desvantagem for captura, a contagem de honra de peças irá ser iniciada. Isto sobrepõe-se à contagem de honra do tabuleiro. A contagem começa com o número de peças que ainda existim no tabuleiro, incluindo ambos os Reis mais um. O limite de contagem é baseado no número de peças do jogador em vantagem, determinado pelos números abaixo indicados:
* Se houverem duas torres: 8
* Se houver uma torre: 16
* Se houverem dois bispos: 22
* Se houverem dois cavalos: 32
* Se houver um bispo: 44
* Se houver um cavalo: 64
* Se houverem apenas (qualquer número) damas e peões promovidos: 64

O jogador em vantagem tem de dar Xeque-Mate ao Rei adversário antes que a contagem exceda o limite. Caso contrário, o jogo terminará em empate. Quando a contagem de honra das peças começa, o limite é atribuido numa pedra, e este não irá ser alterado, mesmo que as peças sejam capturadas no tabuleiro.
Por exemplo, se as Brancas tiverem duas Torres contra um Rei sozinho, a contagem de honra de peças irá de 5 a 8. Se as pretas capturarem uma das torres brancas, a contagem não irá ser reeniciada, nem limite irá ser recalculado. O jogo terminará em empate após as pretas contarem até 9.

## Makruk vs Sittuyin
 
O Sittuyin é um jogo muito semelhante ao Makruk, mas é jogado em Myanmar. De uma certa forma, o Sittuyin pode ser considerado um tipo de Makruk acelerado, que pode porventura saltar imensos lances na abertura. Metade dos Peões de Sittuyin começam na terceira linha, ao contrário de Makruk onde começam todos na terceira linha.

Os jogadores de Makruk têm de negociar desde cedo uma boa configuração de abertura, uma abilidade fulcral no Makruk. Os jogadores de Sittuyin apenas têm de posicionar as peças do seu agrado. Alguma experiência em qualquer uma das variantes beneficia o jogo na outra.  

Em Makruk é permitida a promoção de peões para várias Damas, o que se pode tornar perigoso rapidamente. Isto torna os Peões de Makruk mais valiosos do que os peões em Sittuyin.

## Estratégia
 
O ritmo de jogo é lento, pelo facto da maioria das peças se moverem apenas uma casa de cada vez. É uma boa ideia organizar um grupo de peças em conjunto. Movê-las em grupo a fim de dar suporte mútuo. Não tente abrir o jogo em vários sítios. A chave do Makruk é a coordenação.

## Tácticas
 
**As Torres são as únicas peças que podem pregar ou espetar outras peças. O resto das tácticas consistem em garfos.**

A maioria dos jogos de Sittuyin e de Makruk chega ao fim com um sabor amargo.
Quando um dos lados chega ao fim com apenas um Rei, existem certas regras de contagem (ver acima) que aparecem e induzem imensa pressão no jogador com vantagem. Tais regras, incentivam o lado em desvantagem a jogar até ao fim. Daí ser crucial masterizar todas os xeque-mates básicos contra um Rei sozinho. Não há grande interesse em jogar estes jogos se um dos lados não consegue terminar um Rei sozinho no fim. 
 
Como não existem promoções a peças de grande relevo, torna-se extremamente dificil dar xeque-mate após as peças terem sido capturados do tabuleiro. Planeia com cuidado e tenta ficar com algumas armas letais.
 
Por favor dê a si próprio tempo suficiente no relógio, pelo facto da maior parte dos Xeque-mates necessitarem de precisão.
