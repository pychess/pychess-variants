# ![Shogi](https://github.com/pychess/pychess-variants/blob/master/static/icons/shogi.svg) Shogi

![Boards](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Boards.png)

*Shogi* (将棋), ou Xadrez japonês é um jogo de tabuleiro classico proveniente do Japão e descendente do Chaturanga, o mesmo antepassado do Xadrez. A sua forma moderna já existe desde o século XVI. O jogo é muito popular no Japão, país este onde o Shogi é mais jogado do que o Xadrez e onde existe um lado profissional. O jogo em si é ao mesmo tempo semelhante e muito distinto do Xadrez, com a adição da colocação de peças que são capturadas de volta ao tabuleiro.

## Porquê aprender Shogi?

Se és grande fã de Xadrez, vale mesmo apena experimentar Shogi. Enquanto o seu ritmo é mais lento e longo do que o Xadrez, este também é mais dinâmico e complexo, oferecendo uma experiência completamente diferente. O Shogi está entre o Xadrez e o GO em termos de complexidade, mas por causa disto não tenha receio de experimentá-lo. Tal como outras variantes do Xadrez, ao melhorar a sua habilidade no Shogi isto pode também levar ao melhoramento no Xadrez, abrindo novas portas a novas maneiras de pensar! [Veja aqui com mais detalhe(Inglês)](https://chessbase.in/news/peter-heine-nielsen-on-shogi)

## Regras

As regras são muito semelhantes ao Xadrez, daí iremos focar-nos apenas nas suas diferenças. O Shogi é jogado num tabuleiro de 9x9 onde cada Jogador faz o seu lance a partir de turnos e o seu objetivo é dar Xeque-Mate ao Rei adversário. O jogador das Pretas, ou *sente* (先手 primeiro jogador), começa primeiro, de seguida o jogador das Brancas ou *gote* (後手 segundo jogador), o oposto do Xadrez. Estas cores são meramente arbitrárias e não refletem a cor original das peças. 

Uma diferença significativa com o Xadrez mas semelhante à variante Crazyhouse é de que as peças capturadas podem ser colocadas no tabuleiro como lance. Existem algumas restrições quanto à colocação de peões, que irão ser mostradas mais à frente, excluindo isto, todas as peças podem ser colocadas em qualquer casa. Além disso, quase todas as peças podem ser promovidas. As peças são promovidas quando entram na zona de promoção / território inimigo (últimas três linhas) ou movendo uma peça que já esteja em território inimigo. A peça irá ser então virada. Os peões promovidos que são capturados obtém a sua forma inicial quando ficam na mão do adversário.

## Peças

Neste guia iremos usar a representação internacional das peças. Tradicionalmente são usados caracteres chineses, *kanji*, e as peças geralmente são representadas na forma de 2-kanji, e em 1-kanji (forma abreviada). Desta forma, algum conhecimento de kanji é necessário se pretende usar todos os recursos.

Regra geral, as peças de Shogi estão muito mais restritas do que as peças de Xadrez. As peças menores (i.e. tudo menos a Torre e o Bispo) movimentam-se na maior parte das vezes para a frente e muito pouco para trás.

Acerca das peças promovidas, na maioria das representações, incluindo as que são usadas neste site, são representadas com a cor vermelha. Existem duas regras que irão facilitar na aprendizagem de todas as peças. Todas as peças *menores* movimentam-se como um General Dourado quando são promovidas. O General Dourado, por sua vez não pode ser promovido. De seguida, as duas peças *maiores* (Torre e Bispo), ambas se podem movimentar como um Rei para além dos seus movimentos originals quando promovidas. O Rei não pode ser promovido.


### Rei

![BlackKings](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/BlackKings.png)

![WhiteKings](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/WhiteKings.png)

![KingDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/King.png)

O rei movimenta-se exatamente como no Xadrez: uma casa em qualquer direção. Na representação em kanji, o rei com um ponto, 玉將 gyokushō é o rei das pretas, enquanto que o Rei sem ponto, 王將 ōshō é o rei das brancas.

Esta é a única peça cuja representação internacional é mantida na sua forma original em kanji, 王. Nesta representação, ambas as cores pretas e brancas são representadas na peça em si. A representação em madeira tem uma barra abaixo do caracter 王. 

### Torre

![Rooks](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Rooks.png)

![RookDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Rook.png)


A Torre movimenta-se exatamente como no xadrez: quaisquer número de casas na ortogonal. A representação internacional é um Carrinho, a que se refere ao nome japonês "Carrinho Voador". Em inglês o nome da Torre (Rook) é baseado na palavra persa para Carrinho. Esta é a peça não promovida mais valiosa, excluindo o Rei.

### Bispo

O Bispo movimenta-se exatamente como no Xadrez: quaisquer número de casas na diagonal. A sua representação internacional tem um chapéu tradicional de um oficial Japonês. Esta é a segunda peça não promovida mais valiosa do jogo, excluindo o Rei.

![Bishops](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Bishops.png)

![BishopDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Bishop.png)

### Dragão Rei (Dragão, Torre Promovida)

![Dragons](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Dragons.png)

![DragonDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Dragon.png)

O Dragão-Rei é uma Torre promovida, que obtém os mesmos movimentos do Rei adicionando-os aos movimentos da Torre. Esta é a peça mais valiosa do jogo, excluindo o Rei.

### Dragão-Cavalo (Cavalo, Bispo Promovido)

![Horses](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Horses.png)

![HorseDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Horse.png)

O Dragão-Cavalo é um bispo promovido, que tem os mesmos movimentos do Rei para além do Bispo. Esta é a segunda peça mais valiosa no jogo, excluindo o Rei.

Nota: Não confundir esta peça com o cavalo do Xadrez.

### General Dourado (Ouro)

![Golds](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Golds.png)

![GoldDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Gold.png)

O movimento do General-Dourado pode parecer confuso à primeira, mas a maneira mais fácil de lembrar é pensando que este se **move uma casa na ortogonal em qualquer direção** ou para as três casas da frente. Na sua representação internacional, as saliências no seu capacete (incluindo o símbolo dourado circular) também apontam para todas as possíveis direções.

**Todas as peças menores promovidas movimentam-se exatamente como o General Dourado.**

### General Prateado (Prata)

![Silvers](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Silvers.png)

![SilverDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Silver.png)

O movimento do General-Prateado pode parecer confuso à primeira, mas a maneira mais fácil de lembrar é pensando que este se **move uma casa na diagonal em qualquer direção** ou para as três casas da frente. Na sua representação internacional, as saliências no seu capacete também apontam para todas as possíveis direções.

### Cavalo

![Knights](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Knights.png)

![KnightDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Knight.png)

Semelhante ao cavalo do Xadrez, mas este só se movimenta para as duas casas em frente, i.e. movimenta-se para a frente duas casas e uma para o lado. Tal como o Cavalo do Xadrez, esta pode saltar outras peças.

### Lança

![Lances](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Lances.png)

![LanceeDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Lance.png)

A Lança só se movimenta para a frente, mas em qualquer número de casas (semelhante à Torre).

### Peão

![Pawns](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawns.png)

![PawnDiagram](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Pawn.png)

O peão movimenta-se e captura uma casa em frente. Este é diferente do Peão do Xadrez. O seu chapéu potiagudo na representação internacional é um lembrete do seu movimento.

### Peças menores promovidas

![PSilvers](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PSilvers.png)

![PKnights](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PKnights.png)

![PLances](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/PLances.png)

![Tokins](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Tokins.png)

Ao contrário do Dragão-Rei e do Dragão-Cavalo, estas não têm designações diferentes. À exceção do Peão, que por vezes é denominado de *tokin* o seu nome japonês. Como já foi explicado acima todas estas peças se movem como um General-Dourado. De notar que as versões em kanji têm representações diferentes para os caracteres do General-Dourado.

## Outras Regras

*Colocações* - As únicas exceções sáo relativas aos peões.
1) Os peões não podem ser colocados na mesma coluna dos seus Peões não promovidos (Podem ser colocados com peões promovidos).
2) Os Peões colocados não podem dar Xeque-Mate, mas podem dar Xeque.
3) A última exceção é relativa às peças menores. Não podem ser colocadas peças que não se podem movimentar posteriormente, geralmente na última linha... ou nas últimas duas linhas no caso do Cavalo.

*Xeque Perpétuo* - Repetições de Xeque que resultem na mesma posição quatro vezes seguidas dará derrota ao jogador que fez com que o Xeque perpétuo fosse possível. No Xadrez, isto é considerado empate. 

*Repetição* - À semelhança da regra acima descrita, a repetição da mesma posição (incluindo as peças em mão) dará empate.

*Relógio* - Em Shogi é usado um relógio de byo-yomi. Quando o relógio principal do jogador chega ao fim, este entra em byo-yomi. Se tiver definido a 30 segundos então este jogador terá 30 segundos para efetuar o seu lance e a partir dai terá os mesmos 30 segundos para os próximos lances, se estes expirarem então será declarada derrota por tempo.


## Notação

Existem várias notações para Shogi, incluindo uma japonesa. Neste site usamos a notação ocidental (Notação de Hodge) semelhante ao Xadrez.

### Coordenadas

Uma diferença notável dá-se ao facto das coordenadas do tabuleiro serem o oposto do Xadrez. As colunas são numeradas enquanto que as linhas têm alfabeto. A coordenada de origem do tabuleiro existe no canto inferior esquerdo do jogador das brancas. No entanto, como a maioria dos diagramas estão orientados para o jogador das Pretas (o primeiro a começar), estes irão parecer ter origem no canto superior direito. Por exemplo, o Rei Branco está na casa 5a. 

Na notação de Hoskings, são usados apenas números. Em vez de 5e, este é denominado de 55 (5ª linha, 5ª coluna). Este é semelhante ao estilo japonês que também usa números.

### Peças

K = king (Rei)

G = gold general (General Dourado)

S = silver general (General Prateado)

N = knight (Cavalo)

L = lance (Lança)

R = rook (Torre)

B = bishop (Bispo)

P = pawn (Peão)

+R ou D = dragon king (Dragão-Rei)

+B ou H = dragon horse (Dragão-Cavalo)

+S, +N, +L, +P para todas as outras peças promovidas, respetivamente.

### Símbolos

* As colocações são indicadas com um \* (Hodges) ou ‘ (Hosking). Aqui usamos o \*, portanto um Peão colocado em 5e será P*5e.
* Lances que resultem em promoção irão acabar com um +. Um Peão promovida em 1c será P1c+.
* Caso optar por não promver uma peça, um = irá ser adicionado no fim.
* Xeques e Xeque-Mates não têm notação.

## Recursos para aprendizagem de Shogi

[Hidetchi’s YouTube channel](https://www.youtube.com/playlist?list=PL587865CAE59EB84A) é um sitio excelente para um iniciante e um jogador intermédio. Este canal está em Inglês e demonstra vários aspetos do jogo. De notar que como todos os outros recursos, irás necessitar de conhecer as peças em kanji para perceber os vídeos (Ele também introduz as peças nos videos para iniciantes).

[81dojo.com](http://www.81dojo.com) é um site internacional onde podes desafiar grandes jogadores. No entanto este não suporta jogos por correspondência até ao momento.

## Estratégia

### Valores das Peças

Não existem valores por defeito dos valores das peças em Shogi ao contrário do Xadrez. No entanto é importante notar que os valores variam imenso, pelo facto da perca de peças não ser permanente e da posição ser muito mais importante. Dito isto, existe um sistema de valor básico para as peças, mas alguns jogadores profissionais também deram o seu valor para cada peça; Tanigawa e Satoh são mostrados em baixo.

Peça | Base | Tanigawa | Satoh 
------------ | ------------- | ------------- | -------------
P | 1 | 1 | 1
L | 3 | 5 | 6
N | 3 | 6 | 6
S | 5 | 8 | 10
G | 5 | 9 | 11
B | 7 | 13 | 17
R | 8 | 15 | 19
*H* |  | 15 | 20
*D* |  | 17 | 22
*+P* |  | 12 | 
*+L* |  | 10 | 
*+N* |  | 10 | 
*+S* |  | 9 | 

### Aberturas

De forma geral, existem dois tipos de aberturas: *Torre Estática* e *Torre Enfurecida*. Na *Torre Estática*, a Torre não se movimenta. Os ataques são direcionados para o lado direito do tabuleiro. Na *Torre Enfurecida*, a Torre movimenta-se para o lado esquerdo (tipicamente da 2ª à 5ª coluna), mudando o ataque para aquele lado do tabuleiro.

Esta diferença é importante pelo facto dos lances na abertura (chamados *joseki*) serem classificados como um destes dois e podem mudar o tipo de jogo que está a ser feito. Algumas aberturas de Torres Estáticas são feitas contra Torres Estáticas adversárias, enquanto outras são direcionadas para jogadores que prefiram Torres Enfurecidas.

### Roques

Os roques em Shogi são formações defensivas que levam algum tempo a se formar. Conhecer certos tipos de roque é essencial pelo facto de um Rei com uma defesa fragilizada poder ser facilmente explorado com peças colocadas no seu território. De notar que também é importante conhecer os prós e contras dos vários tipos de Roque.

Como já foi dito, os roques dependem das Torres Estáticas e Enfurecidas. Nas aberturas com Torres Estáticas, os Reis protegem-se para a esquerda. Nas aberturas com Torres Enfurecias, os reis protegem-se no lado direito. Existem várias formas de efetuar o roque, que são explicads nos videos de Hidetchi em Inglês (Veja abaixo).
Aqui estão três tipos de roque mais importantes de se saber:

**Yagura (AKA Fortress) / Fortaleza**

![Yagura](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Yagura.png)

O Roque Yagura é um dos mais poderosos Roques de *Torre Estática*, usado contra Torre Estática adversária. Um lembrete que pode ser útil para se lembrar destas posições é lembrar-se das posições dos generais "S G | G B," ou talvez de se lembrar que o Rei é protegido por um General-Dourado, uma peça extremamente forte. O Yagura é forte na frente, mas fraco nos lados.

A fim de efetuar o Yagura, lembre-se que os generals que se movimentam na diagonal são mais eficientes. Existem vários tipos de josekis para diferentes roques, mas lembre-se que até um certo ponto, as brancas poderão atacar e irás ter de reagir entre os teus lances de Yagura. Os 24 lances típicos de joseki são:

1. ☗P-7f
2. ☖P-8d
3. ☗S-6h
4. ☖P-d3
5. ☗P-6f
6. ☖S-6b
7. ☗P-5f
8. ☖P-5d
9. ☗S-4h
10. ☖S-4b
11. ☗G-5h
12. ☖G-3b
13. ☗G-7h
14. ☖K-4a
15. ☗K-6i
16. ☖P-7d
17. ☗G-6g
18. ☖G-5b 
19. ☗S-7g
20. ☖S-3c
21. ☗B-7i
22. ☖B-3a
23. ☗P-3f
24. ☖P-4d

**Roque Mino**

![Mino Castle](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Mino.png)

O Roque Mino é um roque clássico de *Torre Enfurecida*, usado contra Torre Estática adversária. O Rei é posto na posição inicial da torre, o General Dourado da esquerda movimenta-se uma casa para a frente e uma para a direita, e após isto o General-Prateado é posto na forma de "G G S" formação V. Este Roque é forte na esquerda, mas fraco em frente e na beira. 

Exemplo de abertura para as pretas usando a 4ª coluna da torre:

* P76
* B77 (protects the 86/8f square) 
* P66 (reject bishop exchange if white opens bishop up)
* R68 (fourth file rook)
* S78 
* K48 -> K38 -> K28
* S38 (silver up)
* G58 (gold up-right)
* P16 (creates escape route for the king)
* P46

Após estes lances, estará livre de trocar de Bispos e outras peças que desejar, incluindo Torres para começar um ataque.

**Anaguma**

![Anaguma](https://github.com/pychess/pychess-variants/blob/master/static/images/ShogiGuide/Anaguma.png)

Anaguma (“Urso no buraco”) é um outro tipo de Roque com *Torre Enraivecida*, e um dos mais sólidos do jogo, no entanto este leva imenso tempo a ser formado.

**Ataque duplo de Flancos**

Não é um Roque, mas é uma abertura de *Torre Estática*. Ambos os lados avançam os seus Peões da Torre, causando uma troca. Grande parte do joseki é de que os Generais-Prateados devem defender os Peões dos Bispos antes que os Peões inimigos atingem o seu objetivo. De notar que isto é uma abertura favorita do AlphaZero, com mais de metade das suas aberturas usadas nas Pretas.

## Desvantagens

Ao contrário do Xadrez e com grande semelhança ao GO, os jogos com desvantagem têm um grande impacto no ensino e não devem ser considerados como um jogador a ter dó do outro. Estas desvantagens são uma grande maneira de aprender o jogo, e até existem estratégias para estes diferentes tipos. Em Shogi, jogos com desvantagem são comuns, e as configurações mais populares estão descritas abaixo.

Enquanto que numa partida normal as pretas (*gote*) começam primeiro, **As brancas começam primeiro num jogo com desvantagem**. As brancas têm o nome de *uwate* enquanto as pretas se denominam de *shitate*. Esta desvantagem pode ser recuperada pelo facto de se poder colocar peças capturadas. E pelo facto de não existirem muitas peças poderosas, As pretas/*shitate* são derrotadas muitas vezes quando as peças são capturadas.

Nome | peças omitidas
-- | --
Lança | Lança da Esquerda
Bispo | bispo
Torre | Torre
Torre–Lança | Torre, Lança da Esquerda 
2-Peças | Torre, Bispo
4-Peças | Torre, Bispo, Ambas as Lanças
6-Peças | Torre, Bispo, Ambas as Lanças, Ambos os Cavalos
8-Peças | Torre, Bispo, Ambas as Lanças, Ambos os Cavalos, Ambos Generais Prateados
9-Peças | Torre, Bispo, Ambas as Lanças, Ambos os Cavalos, Ambos Generais Prateados, General-Dourado da Esquerda
10-Peças | Torre, Bispo, Ambas as Lanças, Ambos os Cavalos, Ambos Generais Prateados, Ambos Generais Dourados
