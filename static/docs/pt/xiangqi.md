# ![Xiangqi](https://github.com/pychess/pychess-variants/blob/master/static/icons/xiangqi.svg) Xiangqi

![Boards](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Boards.png)

*Xiangqi* (象棋, soletrado como “*shyang-chee*”), ou Xadrez Chinês é um jogo clássico de tabuleiro proviente da China e julga-se ser descendente do Chatturanga, o mesmo antepassado do Xadrez, no entanto o mesmo se pode afirmar do oposto. Este jogo é muito popular na China e no Vietname, e já se afirmou que este é o jogo de tabuleiro mais popular no Mundo. O jogo em si é muito semelhante ao Xadrez, no entanto a sua jogabilidade é diferente.

## Porquê aprender Xiangqi?

Se és grande fã de Xadrez, vale mesmo apena experimentar Xiangqi. Enquanto o seu ritmo é mais lento e longo do que o Xadrez, o jogo inicia-se com uma configuração mais aberta onde é mais rápido obter um fim-de-jogo. Em comparação ao Xadrez, o Xiangqi é um jogo mais tático (ao contrário de estratégico). Tal como outras variantes de Xadrez, ao melhorar a sua habilidade em Xiangqi esta pode implicar também melhoramentos nas habilidades em Xadrez (Principalmente a nível tático) e também de abrir novas portas 
a uma nova maneira de pensar. [Veja aqui mais informações(Inglês)](https://en.chessbase.com/post/why-you-need-to-learn-xiangqi-for-playing-better-chess)

## Regras

As regras são muito semelhantes ao Xadrez, daí iremos focar-nos apenas nas suas diferenças. A diferença mais significativa é de que as Peças estão posicionadas em interseções em vez de casas, isto é meramente uma diferença estética. Cada jogador faz o seu lance por turnos, movimentando as peças no tabuleiro a fim de dar Xeque-Mate ao Rei adversário. O jogador com as Vermelhas normalmente começa primeiro, sendo de seguida o das Pretas, no entanto a ordem de começar não é relevante pelo facto do tabuleiro ser simétrico. A única outra diferença com o Xadrez é de que o Rei Afogado é considerado uma derrota para quem ficou Afogado (i.e. não consegue movimentar peça alguma).
Em relação aos xeques perpétuos, é atribuida a derrota ao jogador que os efetua após três repetições. 

## Tabuleiro

O tabuleiro de Xiangqi é um bocado diferente da maioria dos jogos de Xadrez. Para além de ser jogado nas interseções, existem várias seções importantes do tabuleiro. Em primeiro lugar temos o rio, que divide o tabuleiro a metade. O rio afeta o movimento do Elefante e dos Peões. De seguida temos os Palácios, que são um conjunto de casas 3x3 localizadas no fim do tabuleiro e tem linhas diagonais representadas neste. O Rei e os seus Assistentes estão restringidos ao Palácio.

## Peças

Aqui iremos focar-nos na representação das peças internacionais. Tradicionalmente são usadas peças com caracteres Chineses, e na maioria dos sites, incluindo a wikipedia, já se explicam as regras com tal. De certa forma, é necessário conhecimento dos caracteres chineses se pretende usar todos os recursos ou jogar num tabuleiro ao vivo. Em comparação ao Shogi que é outro jogo que usa caracteres chineses, o Xiangqi tem menos caracteres a aprender e alguns destes são claros no seu movimento, isto faz com que seja mais fácil aprender.

As peças Xiangqi tradicionalmente já tiveram nomes diferentes: a sua tradução Chinesa e o seu equivalente Ocidental. Neste guia, usaremos os seus nomes e abreviaturas escolhidas pela Federação Asiática de Xiangqi (Asian Xiangqi Federation - AXF), que mistura um pouco dos dois. Pelo facto de ambos os nomes serem comuns, poderá já estar familiarizado com estes. 

### Rei

![Kings](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Kings.png)

O Rei (também conhecido pelo seu nome chinês, **general**) só se pode movimentar uma interseção na ortogonal (vertical e horizontal nunca na diagonal). Além disto, está restringido a estar dentro do Palácio.

*Regra especial:* Ambos os reis não podem estar na mesma coluna sem peças entre estes ("Regra geral do cara-a-cara"). Pode considerar ambos aptos a atacar-se mutuamente como se fossem Torres (também chamado de "Generais Voadores"). Isto é útil a fim de preparar Xeque-Mate no fim-de-jogo.

![King and advisor movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/KingAdvisorDiagram.png)

### Assistente

![Advisors](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Advisors.png)

O Assistente (também conhecido como **guarda** o seu nome Ocidental, e **ministro**) só se pode movimentar uma interseção dentro das diagonais do Palácio. Só existem cinco posições onde os Assistnetes podem estar.

### Elefante

 ![Elephants](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Elephants.png)
 
 ![Elephant movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/ElephantDiagram.png)

O Elefante (raramente chamado de **bispo** o seu nome Ocidental) pode-se mover duas interseções na diagonal. Existem mais duas restrições: 1) O Elefante pode ser bloqueado se tiver uma peça entre este e o destino. 2) Não pode ir para além do Rio.

Um pequeno detalhe, o caracter chinês do Elefante Vermelho significa “ministro”, mas mesmo assim tem o nome de Elefante.

### Cavalo

 ![Horses](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Horses.png)
 
 ![Horse movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/HorseDiagram.png)

O **Cavalo** move-se exatamente como o cavalo do Xadrez. No entanto em vez do pensamento normal "dois passos na ortogonal, e um para o lado", é melhor pensarmos como se fosse *um passo na ortogonal, diagonal para a frente em qualquer direção*, em forma de Y. Isto porque o Cavalo **pode ser bloqueado** se tiver uma peça adjacente a esta. Isto irá bloquear o caminho aos dois pontos finais deste Y. Caso este que pode levar a situações em que dois Cavalos se estão a atacar mutuamente, mas apenas um deles pode atacar enquanto o outro está bloqueado. Bons lances tomam partido do bloqueio do Cavalo e limitam o seu movimento. 


### Biga

 ![Chariots](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Chariots.png)
 
 ![Chariot movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/ChariotDiagram.png)

A **Biga** (também conhecida como **Torre** o seu nome ocidental) move-se exatamente como a torre do Xadrez: qualquer número de linhas na ortogonal. Esta é a peça mais valiosa do jogo, excluindo o Rei.

### Canhão

![Cannons](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Cannons.png)

![Cannon movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/CannonDiagram.png)

O Canhão é uma peça única do Xiangqi. Pode-se movimentar exatamente como uma Biga. No entanto para capturar outra, é necessário ter uma peça(adversária ou do mesmo lado) entre esta e o destino, geralmente chamada de "Mira".

### Peão

![Pawns](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Pawns.png)

![Pawn movement](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/PawnDiagram.png)

O Peão (também conhecido por **soldado** o seu nome chinês) movimenta-se e captura uma iterseção em frente. Este é diferente do Peão do Xadrez. O chapéu pontiagudo na sua peça internacional torna-se um lembrete do seu movimento.

*Regra especial:* Após atravessar o rio, o Peão pode-se mover e capturar uma interseção para o lado também. A aparência da peça não muda para dar a informação de tal.

## Regras adicionais - Xeque Perpétuo e perseguições

* Um jogador que esteja a dar Xeque perpétuo com uma ou mais peças pode ser considerado como derrotado se não parar com tal acto.
* Um jogador que insista na perseguição de uma peça desprotegida com uma ou mais peças, excluindo o Rei e os Peões, pode ser considerado como derrotado se não parar com tal acto.
* Se um dos jogadores estiver a dar Xeque perpétuo e o outro estiver a perseguir constantemente peças desprotegidas, o jogador que está a efetuar o Xeque perpétuo terá de parar com tal ou irá ser considerado como derrotado.
* Quando nenhum dos lados quebrarem as regras e ambos persistirem em não efetuar lances alternados, o jogo irá ser adjudicado como empate.
* Quando ambos os lados quebrarem as regras ao mesmo tempo e ambos persistirem em não efetuar lances alternados, o jogo irá ser adjudicado como empate.

## Notação

O Pychess usa a mesma notação algebraica do Xadrez. A notação mais comum para o Xiangqi não está presentemente implementada. 

### Símbolos

K = **K**ing (Rei)

A = **A**dvisor (Assistente)

E = **E**lephant (Elefante)

H = **H**orse (Cavalo)

C = **C**annon (Canhão)

R = Cha**R**iot (Biga)

P = **P**awn (Peão)


## Onde será que posso aprender Xiangqi?

[Xiangqi in English] (http://www.xqinenglish.com/) é um site excelente em Inglês para iniciantes. O autor do website, Jim Png Hau Cheng, também é autor de vários livros, tais como a coleção "Xiangqi Primer", que pode valer apena o investimento para quem realmente pretenda aprender.

[Club Xiangqi](https://www.clubxiangqi.com/) é um site onde pode ter partidas com jogadores fortes, a maior parte destes são do Vietname.

## Estratégia

### Valores das Peças

Abaixo estão indicados os valores das Peças

Peça | Valor 
------------ | ------------- 
K | Infinito
R | 9
H | 4
C | 4.5
P | 1 antes de atravessar o rio, 2 após atravessar o rio
A | 2
E | 2.5

### Principios Gerais

* Semelhante ao Cavalo e o Bispo do Xadrez, o Cavalo e o Canhão têm valores diferentes com base na posição.
  * O Cavalo é uma peça mais defensiva e menos poderosa no inicio de jogo pelo facto do seu movimento ser restringido por imensas peças. Esta torna-se mais poderosa no fim-de-jogo onde existem menos peças a bloquear o seu caminho (Isto é o oposto do Xadrez)
  * O Canhão é uma peça mais ofensiva e mais potente no inicio de jogo pelo facto de usar outras peças como mira. No fim-de-jogo o seu valor é reduzido por haver menos peças no tabuleiro.
* Como descrito acima, use as suas peças para bloquear os Cavalos e os Elefantes!
* Não pense no Elefante como se fosse um Bispo, pelo facto destes não terem propósitos iguais, mesmo tendo movimentos e posições iniciais semelhantes. Esta peça é meramente defensiva. Pode ser usada ofensivamente como mira para os Canhões.
* *Ataques de Descoberta* existem em maior quantidade no Xiangqi do que no Xadrez e no Shogi pelo facto de existirem peças que possam bloquear o caminho. Esteja pronto a usar esta tática ou de defender contra.
* *Cheques duplos* também são muito comuns, especialmente com a combinação da Biga e do Canhão.

### Aberturas

Estas informações foram obtidas [neste site](http://www.shakki.info/english/openings.html)

O movimento mais comum na abertura é o de centralizar o Canhão, que é dos movimentos mais óbvios por abrir uma linha de ataque central. Aproximadamente 70% das partidas são iniciadas desta maneira, o que é considerada a melhor maneira de aprender o jogo.

![Cannon opening](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/CannonOpening.png)

Existem quatro defesas populares na abertura, e uma quinta que também irá ser mencionada.

**1. Cavalos-Mira / Defesa dos dois Cavalos**

![Screen horses](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Screen_Horses.png)

Esta é a defesa mais comum. O objetivo é de ter ambos os cavalos a protegerem os Peões do centro. Existem várias variantes.

**2. Fan Gong Ma / "Cavalos-Sanduíches"**

Um dos Cavalos é desenvolvido normalmente, e antes que o outro entre em ação, o Canhão movimenta-se para uma posição de "Canhão de Canto" (Canhão no Canto do Palácio), e por fim movimenta-se o segundo cavalo para o seu sítio. As pretas mais tarde irão ligar os seus Elefantes para completar a defesa. Esta é uma abertura relativamente nova. 

![Fan Gong Ma](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Fan_Gong_Ma.png)

**3. Canhão na mesma linha de fogo**

As Pretas movimentam o canhão para a mesma coluna onde o Canhão das Vermelhas foi. A captura de peões de centro é um lance feito por amadores porque este faz com que haja perca de tempo e as Pretas ganhem iniciativa.

**4. Canhões em Linhas de fogo opostas**

Semelhante ao descrito acima, mas usando o canhão oposto. A ideia moderna é de movimentar o Canhão preto mais tarde através da tática de "Atraso no Canhão em Direção Oposta"

**5. Tigre em três passos**

![Three Step Tiger](https://github.com/pychess/pychess-variants/blob/master/static/images/XiangqiGuide/Three_Step_Tiger.png)

As Pretas desenvolvem a sua Biga rapidamente movimentando o seu Canhão para o canto do tabuleiro. Uma jogada típica é de avançar os Cavalos primeiro e após isto os Canhões para o canto, e finalmente as Bigas para as colunas do Canhão.

Outras defesas para além destas raramente são usadas.

Para além da abertura do Canhão, as Vermelhas têm outras opções. Estas são denominadas de "aberturas suaves" por não construirem uma ameaça imediata.

**Abertura de Peão** - Avanço do 2º ou 4º Peão. Esta é uma abertura flexivel que permite às Vermelhas se ajustarem aos lances das Pretas. As pretas geralmente não respondem com os Canhões para o centro porque as Vermelhas poderiam então jogar quaisquer um dos Canhões para o Centro com as cores invertidas e o avanço do Peão daria assim uma grande vantagem.

**Abertura do Elefante** - Avanço do Elefante para o Palácio em vez do Canhão. Esta é uma abertura defensiva e sólida, onde o Rei é protegido.

**Abertura do Cavalo** - Avanço de um Cavalo para o centro. A partir daqui, as Vermelhas podem jogar a Abertura dos dois Cavalos, Fan Gong Ma ou Tigre em Três passos com as cores invertidas.

As Vermelhas também podem jogar o seu Canhão para a frente do Palácio ("Canhão de Canto") ou para o canto oposto ("Canhão de Palácio"). Estes movimentos também são úteis no desenvolvimento das peças.

Outras aberturas para as Vermelhas são muito raras.
