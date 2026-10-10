# ![Orda chess](https://github.com/pychess/pychess-variants/blob/master/static/icons/orda.svg) Orda Chess

![Orda](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Orda.png)

![Legend](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/OrdaLegend.png)

A Orda Chess é uma variante de Xadrez criada em 2020 por Couch Tomato. A ideia desta variante foi a criação de um verdadeiro jogo de Xadrez assimétrico com dois exércitos diferentes. O Xadrez de Ralph Betza com diferentes exércitos serviu de inspiração para tal, mas o objetivo aqui foi de simplificar com o Xadrez. Nesta variante, a ideia usada foi de ter um exército baseado nos movimentos do Cavalo, onde a maior parte das peças têm a caracteristica de se moverem como tal. Dada a ideia do Cavalo, a variante foi modelada com base no exército Mongol tendo o obtido o nome de "Horde" (do inglês, multidão, horda). De notar que a Orda foi uma estrutura militar da população dos Estepes (wiki), que deu o nome à palavra inglesa "Horde"(multidão). O exército original do Xadrez tem como nome o Reino (Kingdom) ao contrário deste. Esta variante, de acordo com a inteligência artificial é muito equilibrada (ainda mais do que o Xadrez normal), com um recorde perto de 50-50 de vitória tanto para o Kingdom(Reino) como para a Horde(Multidão).
 
## Regras Gerais
1.	A posição inicial está acima. Apesar de haverem novas peças, as posições iniciais da Horde(Multidão) está simétrica ao exército do Xadrez normal.
2.	As únicas peças que são iguais em ambos os lados são os Peões e os Reis (o Rei da Horde é chamado de Khan).
3.	O Kingdom(reino, brancas) *começa sempre em primeiro lugar*.
4.	A Horde(multidão, dourados) não podem efetuar Roque.
5.	Como os Peões da Horde(multidão) começam na terceira linha, estes não têm a opção de se moverem duas casas para a frente. Os Peões do Kingdom(reino) mantém a sua habilidade de se moverem duas casas e de serem capturados por en passant.
6.	Os Peões *de ambos os lados* só podem ser promovidos a Dama ou Kheshig.
7.	Um outro método de vencer o jogo é chamado de **mate de linha**. O Mate de Linha acontece quando o Rei da Horde(multidão) atinge a linha final sem estar em Xeque.
8.	Outras regras presentes são o do Rei Afogado e a Repetição como acontece no Xadrez.

## Peças da Horde(multidão)
Existem quatro novas peças únicas* para a Horde: 2 Lanças, 2 Cavalo-Arqueiros, 2 Kheshigs e 1 Yurt (* exceção pelo facto do Kingdom(reino) poder obter um Kheshig com uma promoção). Os Kheshigs são as peças mais poderosas (movimenta-se como Cavalo+Rei) e lidera cada flanco, enquanto o Yurt é uma peça fraca comparada à Dama.
O Rei da Horde(multidão) é chamado de Khan e é representado de forma diferente, no entanto é igual ao Rei do Kingdom(reino), e também usa a mesma abreviatura (K) - a mudança é puramente a nível de desenho e representação temática.
As Lanças e os Cavalo-Arqueiros são peças únicas pelo facto de capturarem de forma diferente do seu movimento. De relembrar que a Horde(multidão) é baseada no movimento do Cavalo, portanto as Lanças e os Cavalo-Arqueiros se movem como um Cavalo. Estas peças capturam como uma Torre e um Bispo, respetivamente. O Kheshig é uma peça mais tradicional porque captura da mesma forma que se movimenta; esta peça combina o movimento do Cavalo e do Rei. Semelhante a este temos o Yurt, que captura da mesma maneira que se movimenta; este tem movimentos iguais ao do General Prateado do Shogi.

**Horde** peça	| **Kingdom** “equivalente”	| Movimento | Captura/Xeque
-- | -- | -- | --
Yurt | Dama | “Prateado” | “Prateado”
Cavalo-Arqueiro | Bispo | Cavalo | Bispo
Kheshig | Cavalo | Cavalo+Rei | Cavalo+Rei
Lança | Torre | Cavalo | Torre

Alguns detalhes e diagramas de cada peça estão representados abaixo. Os pontos a verde representam o movimento, os pontos a vermelho a captura, e os pontos a amarelo representam ambos.
 
### Yurt (Y)

![Yurt](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Yurt.png)
 
O Yurt move-se e captura uma casa na diagonal ou uma casa em frente. Este é o mesmo que um General Prateado em Shogi ou o Bispo/Khon em Makruk. Só existe um Yurt, que começa na casa da Dama, mas ao contrário da Dama, esta é uma peça bem menor, a mais fraca em termos de valor excluindo o Peão. No entanto não se deve desprezá-la, pois esta é uma das poucas peças da Horde que capturam e se movimentam da mesma maneira. As outras duas peças assim são o Khan(Rei) e o Kheshig, sendo ambas as peças mais valiosas. Dai, o Yurt tem um objetivo unico de dar suporte aos Peões ou outras peças sem medo de ser ameaçada. Um Yurt é uma casa ambulante dos Mongóis e dos Turcos provenientes dos Estepes da Ásia. O seu movimento limitado mas importante para o suporte ao exército é refletido nesta peça.


### Kheshig (H)

![Kheshig](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Kheshig.png)

O Kheshig é uma peça híbrida que se move e captura como um Rei e um Cavalo. Este tipo de peça é geralmente denominada de Centauro. Os Kheshigs começam nas casas dos Cavalos, mas ao contrário do Cavalo, esta é a peça mais poderosa da Horde. Pode ser considerada um general que lidera o seu próprio exército nos flancos. É aconselhado a manter os Kheshigs seguros atrás do exército antes do meio-jogo por causa da sua elevada importância no exército da Horde no fim-de-jogo.
Os Kheshigs forma guardas imperiais do exército real da Mongólia. É extremamente dificil para o Kingdom(reino) dar Xeque-Mate ao Khan(Rei) sem eliminar um dos Kheshigs em primeiro lugar, o que é apropriado ao seu papel.  

### Cavalo-Arqueiro (A)

![Horse Archer](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Archer.png)
 
O Cavalo-Arqueiro, ou simplesmente chamado de Arqueiro, é uma peça única "semi-híbrida" que se movimenta e ataca de maneira diferente. O Arqueiro movimenta-se como um Cavalo mas captura como um Bispo. Pelo facto do Arqueiro não estar preso à cor da sua casa, este é mais valioso do que o Bispo.
Os Arqueiros são uma das duas componentes principais da cavalaria Mongol, e funcionam como uma cavalaria rápida. A sua velocidade e proeza como arqueiros a cavalo fizeram destes uma ameaça única. A sua capacidade de se posicionarem rapidamente para um ataque de raio-X ou de tácticas de Garfo faz com que eles sejam uma grande ameaça para o Kingdom(reino).
 
### Lança (L)

![Lancer](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Lancer.png)
 
A Lança é uma peça única "semi-híbrida" que se movimenta e ataca de maneira diferente. A Lança movimenta-se como um Cavalo mas captura como uma Torre. Pelo facto da Lança não ser tão móvil como a Torre, esta é considerada inferior à Torre. E isto se torna mais visível no fim-de-jogo, pelo facto de não se poder mover ao longo do tabuleiro rapidamente como a Torre. O seu valor é comparável ao do Cavalo-Arqueiro.
As Lanças são uma das duas componentes principais da cavalria Mongol, sendo estas parte da cavalaria pesada. Mesmo sendo mais fracas do que a Torre, a sua habilidade de entrar em jogo mais rapidamente cria uma vantagem ao lado da Horde(multidão) que o jogador deve usufruir.
 
## Avaliação das Peças

São desconhecidos valores certos para as peças. No entanto, estes são os valores usados pelo Fairy-Stockfish, de notar que são valores genéricos, não especificos para a Orda Chess.

Peça do Reino	| Valor (Inicio / Fim) | Peça da Horde | Valor (Inicio / Fim)
-- | -- | -- | --
Peão | 120 / 213	| Peão | 120 / 213
Dama | 2538 / 2682	| Yurt | 630 / 630
Bispo | 825 / 915	| Cavalo-Arqueiro	| 1100 / 1200
Cavalo | 781 / 854	| Kheshig | 1800 / 1900
Torre | 1276 / 1380	| Lança | 1050 / 1250

Para aqueles que pretendem uma tabela simplificada, damos aqui uma aproximação.

Peça do Reino	| Valor | Peça da Horde	| Valor
-- | -- | -- | --
Peão | 1	| Peão | 1
Dama	| 9	| Yurt | 2
Bispo | 3 | Cavalo-Arqueiro | 4
Cavalo | 3 | Kheshig | 7
Torre | 5 | Lança | 4

## Estratégia
Pelo facto de ainda ser uma variante recente, a estratégia ainda está em desenvolvimente! A maior parte das ideias são baseadas na inteligência artificial.

A Horde não pode efetuar o Roque. No entanto, um conceito fundamental na maioria das aberturas da Horde é mover o seu Khan(Rei) para a casa g7. Chegando a esta casa nos primeiros quatro lances seria o ideal - de notar, que o Fairy-Stockfish começa com Kf7 em 56% das suas partidas. O resto varia.
Para o Reino, d4, g3 e b3 são as aberturas mais comuns (por esta ordem).

Uma grande fraqueza da Horde é o facto das Lanças e dos Cavalos-Arqueiros não aguentarem muito bem com uma ameaça. Se uma Lança ou um Arqueiro for atacado, ambos têm de recuar, perdendo assim o seu ataque. É importante que o Reino obtenha vantagem com isto.

### Aberturas

A tabela seguinte é baseada na análise feita pelos primeiros lances jogados pelo Fairy-Stockfish contra si próprio

Brancas Primeiro Lance	| Percentagem de jogos (número) | Brancas Vencem % | Dourados Vencem % | Resposta Dourados
-- | -- | -- | -- | --
d4 | 38%	(47) | 45% | 38% | Kf7 ~= c5 >> Hb7
g3	| 24% (30)	| 33% | 43% | Kf7 >> d5
b3 | 14% (18) | 33% | 44% | Kf7 >> Lc7
e3 | 11% (14) | 50% | 50% | Kf7 ~50% of the time
d3 | 6% (8) | 25% | 25% | e5 ~=Kf7
Nf3 | 3% (4) | 25% | 50% | e5 always
e4 | 2% (3) | 33% | 67% | d5
c4 | 1% (1) | 100% | 0% | Kf7

Algumas aberturas em particular são usadas em várias partidas. Aqui estão quatro aberturas mais comuns. Aqui daremos o nome de "Fortaleza" para qualquer variante em que a Horde põe o seu Khan(Rei) na casa f7 o mais cedo possível. Os últimos lances entre parêntesis são onde estas jogadas começam a acontecer.

**Fortaleza de Benko - Abertura de Canto Dupla** - Abertura mais comum
1. g3 Kf7
2. e4 Kg7
3. (Bd3 ou Nf3) ...

![Benko's Castle](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/BenkoCastle.png)

*Fortaleza de Benko após 2... Kg7*

**Defesa Stockfish - Variante Fechada**
1. d4 c5
2. dxc5 *bxc5*
3. c4 Kf7
4. (Nc3) ...

**Defesa Stockfish - Variante Aberta**
1. d4 c5
2. dxc5 *dxc5*

**Defesa Stockfish - Pressão no lado da Dama**
1. d4 c5
2. *e3* cxd4
3. exd4 b5
4. b3 Kf7
5. c4

![Stockfish Defense Queenside Push](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/QueensidePush.png)

*Defesa Stockfish- Pressão no lado da Dama após 5. c4*
