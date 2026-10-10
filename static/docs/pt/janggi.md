# ![Janggi](https://github.com/pychess/pychess-variants/blob/master/static/icons/Janggi.svg) Janggi

![Boards](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Boards.png)

*Janggi* (장기, “*chahng-ghee*”), ou Xadrez Coreano, é um jogo de tabuleiro clássico proveniente da Coreira. Este jogo é derivado do Xiangqi e é extremamente semelhante a este.

## Regras: Tabuleiro e Configuração

Existem dois lados, um tem a cor vermelho (denominado Han) e o outro a cor azul (denominado Cho). O lado azul pode ser também verde. Ambos os lados correspondem aos dois lados da Contenção de Chu-Han da História da China. As peças vermelhas são escritas usando caracteres chineses (hanja), ao passo que as peças azuis são escritas em estilo-cursivo hanja. 

A configuração de todas as peças com a exceção do cavalo e do elefante são descritas na figura acima. Como no Xiangqi, o Janggi é feito num tabuleiro de 9x10, onde as peças são colocadas em interseções ao invés de casas. A casa 3x3 com um X de cada lado é chamada de *Palácio*. Ao contrário de outras variantes de Xadrez, em Janggi, os jogadores escolhem a posição inicial dos seus Cavalos e dos Elefantes. Existem quatro tipos de escolha:

1. Ambos os cavalos começam na beira (*won ang ma*)
2. Ambos os cavalos começam perto do general (*yang gwee ma*)
3. Cavalo da esquerda dentro, Cavalo da direita fora (*gwee ma*)
4. Cavalo da esquerda fora, Cavalo da esquerda dentro (*mat sang jang gi*)

O lado Vermelho (Han) escolhe a sua posição primeiro, após isto o lado Azul (Cho) faz a sua escolha. No entanto, o lado Azul é quem faz o primeiro lance.

Para repetições e outras situações no fim-de-jogo:
* É atribuida a derrota ao jogador que os efetua xeques perpétuos após três repetições. 
* Repetições de jogadas não classificadas como perpétuas são dadas como terminadas após três repetições pela contagem de material 
* Quando a regra dos 50 lances entra em vigor (100 movimentos de cada lado sem capturas), o jogo é dado como terminado e adjudicado pela contagem de material

Este guia tem como base os grafismos internacionais. Tradicionalmente as peças são representadas com caracteres chineses (hanja), e em vários sites, incluindo a Wikipedia, já são explicadas as regras.

Algumas peças têm movimentos especiais usando as diagonais dentro de qualquer Palácio, o que vai ser referido abaixo. Nos diagramas, irá ser usado um sombreado em verde claro.

### Rei

![Kings](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Kings.png)

O **Rei** (também conhecido por **general** o seu nome chinês) está restringido apenas ao palácio e pode-se mover dentro das linhas do mesmo. Isto significa que, quando o Rei está no centro, este tem 8 possíveis lances. No entanto, em qualquer outro sítio dentro do Palácio, só tem 3 lances possíveis.

*Regra especial:* Quando um Rei se encontra na mesma linha de fogo do outro Rei, isto é chamado de *bikjang*. O outro jogador terá então de mover o seu Rei para fora desta linha ou jogo se dará por terminado. Veja as regras abaixo que explicam o bikjang.

![King and advisor](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Palace.png)

### Assistente

![Advisors](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Advisors.png)

O **Assistente** (também conhecido como **guarda** o seu nome ocidental) move-se exactamente como o Rei, isto é um espaço por cada linha dentro do Palácio. Tal como o Rei, o Assistente está restringido ao Palácio.

### Cavalo

 ![Horses](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Horses.png)
 
 ![Horse movement](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/HorseDiagram.png)

O **Cavalo** move-se exatamente como o cavalo do Xadrez. No entanto em vez do pensamento normal "dois passos na ortogonal, e um para o lado", é melhor pensarmos como se fosse *um passo na ortogonal, diagonal para a frente em qualquer direção*, em forma de Y. Isto porque o Cavalo **pode ser bloqueado** se tiver uma peça adjacente a esta. Isto irá bloquear o caminho aos dois pontos finais deste Y. Caso este que pode levar a situações em que dois Cavalos se estão a atacar mutuamente, mas apenas um deles pode atacar enquanto o outro está bloqueado. Bons lances tomam partido do bloqueio do Cavalo e limitam o seu movimento. 

### Elefante

 ![Elephants](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Elephants.png)
 
 ![Elephant movement](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/ElephantDiagram.png)

O **Elefante** é muito diferente do descrito em Xiangqi. O seu movimento é semelhante ao do Cavalo pelo facto de se mover em forma de Y. Enquanto o cavalo se move um passo na ortogonal e um passo na diagonal, o elefante move-se um passo na ortogonal e após isto *dois* passos na diagonal. O Elefante, tal como o Cavalo pode ser bloqueado por qualquer peça no seu caminho.

### Biga

 ![Chariots](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Chariots.png)
 
 ![Chariot movement](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/ChariotDiagram.png)

A **Biga** (também conhecida como **Torre** o seu nome ocidental) move-se exatamente como a torre do Xadrez: qualquer número de linhas na ortogonal. Esta é a peça mais valiosa do jogo, excluindo o Rei.

*Movimento no Palácio*: Dentro do palácio, a biga também se move na diagonal.

### Canhão

![Cannons](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Cannons.png)

![Cannon movement](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/CannonDiagram.png)

O **Canhão** é um bocado diferente do Xiangqi. Move-se na ortogonal como a Biga, no entanto este precisa de um interveniente (chamada a "mira") a fim de pular esta peça. Após isto, o canhão pode capturar qualquer peça que esteja nesta linha de fogo. Ao contrário do Xiangqi, o Canhão não se pode movimentar sem mira.

*EXCEÇÃO*: O Canhão não pode usar qualquer outro Canhão como mira. Além disso, também não pode capturar o Canhão adversário.

*Movimento no Palácio*: Quando está dentro do Palácio, o Canhão pode-se mover na diagonal. Basicamente, o Canhão tem de estar no canto do Palácio, onde se pode mover ou atacar o canto contrário se nenhuma peça que não seja canhão esteja no centro (como se vê no diagrama).

### Peão

![Pawns](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/Pawns.png)

![Pawn movement](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/PawnDiagram.png)

O **Peão** (também denominado de **soldado** o seu nome chinês) movimenta-se e captura uma casa em frente ou numa casa em cada lado. Este é diferente do Peão em Xiangqi, que necessita atravessar o Rio primeiro antes de se mover para os lados.

*Movimento no Palácio*: Quando está dentro do palácio, o Peão também se pode mover na diagonal.

## Notação

A Notação em Janggi funciona de forma diferente das outras variantes. Primeiramente, os números das coordenadas. No ponto de vista do lado Azul, as linhas são numeradas de 1 a 10 decrescendo do cimo para o fundo. No entanto, a 10ª linha é denominada por 0. As colunas são numeradas de 1 a 9 da esquerda para a direita. Descrevendo o local da peça é o posto do Xadrez. A localização é descrita por *coluna* logo de seguida *linha* (em todas as outras variantes dá-se primeiramente a linha e após esta a coluna). Por exemplo, a Biga Azul no canto inferior esquerdo está em **01**. A interseção acima está em **91**. O Rei azul está localizado em **95**.

A descrição dos lances não tem uma versão internacionalizada. Nós usamos uma versão modificada do estilo Coreano. Em Coreano, a síntaxe é (localização inicial)(nome da peça em coreano)(posição final). Aqui no Pychess, nós usamos (Nome das peças em Inglês abreviadas) (localização inicial)-(localização final). Como no Xadrez, as capturas são denotadas com x em vez de -, um Xeque tem um + no fim e o Xeque-mate tem #.

Por Exemplo, a Biga da esquerda move-se três espaços acima é denotado por R01-71, "R" refere-se à Biga. Para abreviaturas das peças, veja abaixo.

### Abreviações

K = **K**ing (Rei)

A = **A**dvisor (Assistente)

E = **E**lephant (Elefante)

H = **H**orse (Cavalo)

C = **C**annon (Canhão)

R = Cha**R**iot (Biga/Torre)

P = **P**awn (Peão)



## Regras: Jogo

Tal como o Xadrez, o objetivo principal é dar Xeque-mate ao outro Rei.

Ao contrário da maior parte das variantes de Xadrez, podes passar numa jogada em Janggi. Implicando que, afogar o Rei é impossível. **Para passar no Pychess, use o control+clique em cima do seu Rei**

Ao contrário do Xiangqi, os Reis podem ficar na mesma linha de fogo um do outro. Isto cria uma situação denominada de **bikjang** (tradução literal "Generais se rindo"). Se o jogador que irá jogar a seguir não quebrar o bikjang (por exemplo, movendo o Rei ou movendo uma peça entre estes), então o jogo termina em empate. Nos torneios não é permitido empate, o valor das peças é contado, e o jogador com o maior valor ganha.

Peça | Valor 
------------ | ------------- 
Biga | 13
Canhão | 7
Cavalo | 5
Elefante | 3
Assistente | 3
Peão | 2

Pelo facto dos azuis (Cho) começarem o jogo, estes começam com vantagem e por isto os vermelhos (Han) recebem 1.5 pontos (*deom*) como compensação. O Valor 0.5 é adicionado de modo a evitar empates.

Presentemente o Pychess usa as regras de torneio e não permite empates. Daí os jogos serem decididos por pontos quando o bikjang acontece.

Adicionalmente, é possível provocar bikjang e xeque ao mesmo tempo. Neste caso, o bikjang tem prioridade.

A repetição é ilegal; no entanto, a forma disto ser tratado varia de sitio para sitio. A repetição não é tratada aqui no Pychess, portanto aquando acontece repetição, os jogadores terão de adjudicar o resultado entre estes.

## Diferenças com o Xiangqi

Além das regras acima descritas...

* Não existe rio em Janggi. Consequentemente os Peões e os Elefantes movem-se de maneira diferente. Os Peões podem-se mover para o lado desde o inicio. Os Elefantes movem-se de maneira completamente diferente.
* Visualmente, as peças são representadas em octógonos em vez de circulos. Os tamanhos das peças também são variáveis e são baseadas no seu valor. Os Reis(Generais) são denominados referentemente a cada um dos lados ao invés de serem chamados "Generais". Os tabuleiros usam X em vez de cruzes para as peças iniciais.
* Ambos os Reis começam no meio do Palácio em vez de começarem atrás.
* Os Canhões são diferentes da forma como se movem e capturam (pulando por cima de uma peça primeiro). Também apresentam mais restrições.
* O Palácio afeta todos os movimentos de todas as peças com exceção do Cavalo e do Elefante. Os Reis e os Assistentes movem-se através das linhas em vez de apenas na ortogonal ou diagonal. Bigas, Canhões e Peões também se podem mover na diagonal.


## Estratégia

[Estes vídeos de Amphibian Hoplite](https://www.youtube.com/playlist?list=PL9corMEVRvP-HUJcF7I670pEqV3XNbkKM) são um excelente começo em Inglês. Todos os contéudos disponibilizados em Inglês são poucos.

[Aqui](https://www.youtube.com/watch?v=pX_ZDjeqlJs) está outro vídeo de Kolo (Galdian) que também explica principios na abertura.

### Conceitos Gerais

* A estrutura dos Peões é muito importante. Porque os peões conseguem se mover para os lados, estes são os melhores a proteger outros em pares. A linha de três peões é uma formação fraca (porque estes ficam restringidos). Por cause disto não é aconselhável avançar peões se possível.

![Bad Pawn Formations](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/BadPawns.png)

* Relativamente à escolha da posição dos Cavalos e Elefantes, uma forma de pensar será como os seus Elefantes estão posicionados, e isto tem grande impacto na abertura. Um elefante próximo da beira é capaz de se mover para o centro entre dois Peões. No entanto, um elefanto próximo do centro é bloqueado por peões (no entanto é capaz de os proteger).
* Após isto, a posição do teu elefante determina qual a **beira a ser aberta**. Por exemplo, quando se joga uma posição onde o elefante da esquerda pode avançar (e o elefante do adversário também está na beira), irás querer avançar o teu peão da esquerda para o lado, abrindo assim a coluna da Biga/Torre, porque se o Peão adversário defender, este irá perder a sua Biga/Torre. De notar que se o adversário tivesse dois elefantes próximos do centro, então irás querer abrir a beira do outro lado. 

![Activating the elephant and chariot](https://github.com/pychess/pychess-variants/blob/master/static/images/JanggiGuide/ActiveElephant.png)
