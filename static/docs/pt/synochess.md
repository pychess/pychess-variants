# ![Synochess](https://github.com/pychess/pychess-variants/blob/master/static/icons/synochess.svg) Synochess

![Synochess](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Synochess.png)

O Synochess é uma variante de Xadrez criada em 2020 por Couch Tomato. A ideia foi de criar uma variante onde o Xadrez Ocidental podia batalhar contra o Xiangqi ou o exército do Xadrez Chinês de uma forma justa. Considerando o facto do Xiangqi ser bem diferente (Tabuleiro maior e peças menos poderosas) isto foi bastante dificil de alcançar sem algumas modificações ao exército Chinês. No entanto, isto foi obtido, sem perder a alma do Xiangqi quando se joga pelo exército Chinês. Nesta variante, o exército branco representa o Xadrez Ocidental e é chamado de Reino, quando o exército Vermelho representa uma junção entre o Xiangqi e o Janggi (Xadrez Coreano) e este é denominado de Dinastia. Todas as peças da Dinastia representam o seu correspondente em relação ao Xiangqi ou ao Janggi.
O nome Synochess foi baseado no seu nome antigo de Sinochess, mas foi alterado quando a Dinastia se tornou menos "Sino" (em chinês) e se tornou numa mistura entre o Chinês e o Coreano. Daí, o prefixo syn- significa "juntos", e o jogo representa uma junção entre dois jogos de Xadrez distintos que uniram forças.  
 
## Regras Gerais
1. A posição inicial está representada em cima.
2. As únicas peças em comum entre os dois exércitos são os Reis, Cavalos e Torres (denominadas de Bigas na Dinastia)
3. O Reino (brancas) começam primeiro.
4. A Dinastia (vermelhos) não podem efetuar roque.
5. Os peões do Reino só podem ser promovidos às suas peças (Dama, Torre, Cavalo, Bispo). Os soldados da Dinastia não podem ser promovidos.

\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*

Existem cinco regras adicionais que os novos jogadores têm de conhecer! (Além de aprenderem os movimentos das novas peças)

\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*\*

1. **Reis face-a-face** - Como no Xiangqi, Ambos os reis não podem estar na mesma coluna sem peças entre estes ("Regra geral do cara-a-cara"). Pode considerar ambos aptos a atacar-se mutuamente como se fossem Torres. Isto é útil quando se efetua tácticas de pregadura (ou Pin), ou também para dar suporte às peças com o próprio Rei.
2. **Soldados Melhorados** - O lado vermelho começa com dois Soldados em mão. Em vez de efetuar um lance com uma peça no tabuleiro, o jogador da Dinastia pode optar por colocar um soldado numa casa apenas da 5ª linha do tabuleiro (ou seja a 4ª linha da Dinastia), a mesma fila de onde os soldados começam. 
3. **Mate de Linha** - O Mate de Linha acontece quando o Rei atinge a linha final sem estar em Xeque.
4. **Rei afogado** - Como no Xiangqi, o mate ao Rei Afogado é considerado derrota (Em xadrez, é empate).
5. **Xeque perpétuo** - Como no Xiangqi o xeque perpétuo (repetição da mesma posição 3 vezes e todos os lances são xeque) é considerado derrota (Empate no Xadrez).

## Dynasty Pieces
Existem quatro novas peças únicas para a Dinastia: 6 Soldados (2 em mão), 2 Canhões, 2 Elefantes, e 1 Assistente.
As Bigas(Carroças) são iguais à Torr e usam a mesma abreviatura (R) - a diferença é puramente gráfica. À sua semelhança os Reis são semelhantes, mas são representados de maneira diferente. Apesar dos Cavalos serem diferentes em Xiangqi e em Janggi, a versão da Dinastia também é denominada de Cavalo e movimentam-se da mesma forma do Cavalo do Reino.
A Dinastia não tem uma peça poderosa como a Dama; no entanto a Dinastia tem mais peças menores do que o Reino.
Abaixo estão detalhes e diagramas de cada peça.

### Soldado (S)

![Soldado](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Soldier.png)
O Soldado pode-se mover uma casa à frente e para ambos os lados. É exatamente o mesmo Soldado do Xiangqi quando atravessa o rio e exatamente igual ao soldado do Janggi inicial. O Soldado, ao contrário do peão não pode ser promovido.
Devido ao facto do soldado não se poder movimentar para trás, este só se pode mover para os lados na linha final. Evite este situação ao máximo excepto se esta resultar em xeque-mate ou mate de linha. Os soldados são mais poderosos quando emparelhados lado a lado pelo facto de poderem proteger mutuamente.

### Elefante (E)

![Elefante](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ElephantDynasty.png)
 
O Elefante é uma peça salteadora qe se move na diagonal uma ou duas casas. Pelo facto de ser salteadora, esta pode pular por cima de uma peça interveniente a fim de capturar ou de se movimentar. Esta peça é basicamente uma versão mais poderosa do Elefante do Xiangqi; E é exatamente igual ao elefante da variante Shako.

### Canhão (C)

![Cannon](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/CannonDynasty.png)
 
O Canhão é uma peça de pulo. É basicamente como uma Torre que precisa de uma peça interveniente (também chamada de "mira") a fim de pulsar por cima desta a fim de se mover ou capturar. *****Um canhão não pode usar outro canhão como mira.***** Esta versão do canhão é exatamente igual ao do Janggi. Pelo facto de precisar de outra peça interveniente a fim de capturar ou de se mover, O canhão é muito mais fraco no final de jogo.
 
### Assistente

![Assistente](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Advisor.png)

O Assistente, movimenta-se e captura exatamente como um Rei. Ao contrário do Rei, este pode ser capturado. Enquanto não existe uma peça equivalente no Janggi ou no Xiangqi, não existe o Palácio no Synochess. Por isto, o Assistente precisou de se tornar mais forte a fim de proteger o Rei, pode-se considerar os seus movimentos como uma junção entre os dois assistentes do Xiangqi que podem ir para quaisquer das 8 casas.

 
## Valores das Peças

Não existem valores concretos de cada peça para esta variante. No entanto estes são os valores utilizados pelo Fairy-Stockfish, de notar que são valores genéricos, não especificos para o Synochess.

Reino	| Valor (Inicio / Fim) | Dinastia | Valor (Inicio / Fim)
-- | -- | -- | --
Peão | 120 / 213	| Soldado | 200 / 270
Dama | 2538 / 2682	| Assistente | 700 / 900
Bispo | 825 / 915	| Elefante | 700 / 650
Cavalo | 781 / 854	| Canhão | 700 / 650
Torre | 1276 / 1380	| Cavalo | 781 / 854
 | | | Biga | 1276 / 1380

Para aqueles que pretendem uma avaliação simplificada, esta é a tabela.

Reino	| Valor | Dinastia	| Valor
-- | -- | -- | --
Peão | 1 | Soldado | 2
Dama	| 9 | Elefante | 2.75
Bispo | 3 | Assistente | 2.75
Cavalo | 3 | Canhão | 3
Torre | 5 | Cavalo | 3
 | |  | Biga | 5

## Estratégia
Esta variante é nova, daí a sua estratégia estar ainda a ser desenvolvida! A maior parte dos dados existentes consiste em jogos entre computador. Como a maior parte das variantes, pode-se jogar contra o computador e aprender estratégias com este.

### Aberturas

Como no Xiangqi, os primeiros lances da abertura são muito limitados até que o jogo se desenvolve. Na maior parte dos jogos (~90%) o Fairy-Stockfish começa com 1. e3. Se as brancas não começarem com 1.e3, 1.b3 é a segunda abertura mais comum. Outros lances são: 1.g3, 1.f3 e 1.c3, mas são raros. Todas as outras aberturas não são optimais. 1.b3 é a segunda mais comum para as brancas. 1.c3 também jogada ocasionalmente. Para o segundo lance, existem mais opções, no entanto 2.Bb2 é o mais comum.
Para a Dinastia, o lance mais comum é 1...Nc6 (70%) e 1...Nf6(30%). Não existem outras tentativas feitas pelo Fairy-Stockfish. O segundo lance consiste em desenvolver ou outro Cavalo ou centralizar o Canhão (Ce6+ > Cd6). Após isto, os lances variam imenso.

Daí, Conclui-se que a "Abertura de Cavalo Nc6" é a seguinte:
1.	e3 Nc6
2.	b3 …Nf6/Ce6+/Cd6

Abertura mais comum:

1.	e3 Nc6
2.	b3 Nf6
3.	Bb2 Ee7

Para jogadores que preferem Nf6, esta é a mais comum:

1.	e3 Nf6
2.	b3 Ce6+
3.	Be2 Nc6

Como em Xiangqi, os ataques de descoberta são bastante frequentes. Esteja bastante atento a estes!

Como no Xiangqi, usar os Reis por questões ofensivas é importante. É muito fácil pregar uma peça entre os Reis. Por exemplo, um peão entre estes não pode atacar por estar no meio dos Reis.

O jogador da Dinastia tem de jogar de forma agressiva. Este começa com uma posição mais avançada, mas peças mais fracas. Este precisa procurar trocas a seu favor. Os Soldados são mais poderosos do que os peões, por isto a Dinastia tem de fazer com que o Reino tenha dificuldades em remover os Soldados.

O jogador da Dinastia tem de evitar movimentar os Soldados em demasia. A sua posição inicial já é considerada uma "estrutura de Soldado" optimizada (2 pares de Soldados lado-a-lado). Movimente os Soldados para criar ataques para os Canhões e as Bigas. Use os seus Soldados em mão para substituir Soldados que foram capturados. Se os colocar cedo demais, pode prejudicar o seu jogo.

### Conselhos para o Reino (brancas)

* **Aberturas com peões - Um passo de cada vez!** - Isto é baseado no jogo e nos padrões estabelecidos pelo Fairy-Stockfish, mas os seus primeiros lances com peões devem ser feitos por uma casa apenas. Isto se deve ao facto de se formar uma estrutura mais sólida a fim de derrubar os Soldados da Dinastia.
* **EVITE iniciar uma troca pelo canhão** - O Canhão, por muito mortifero que seja no inicio, perde o seu valor no decorrer do jogo. De facto quanto menos peças houver no tabuleiro, menos vale o canhão (Se não houver miras, o Canhão é inútil), eventualmente isto leva a que o canhão seja capturado facilmente por outra peça.
* **Proteja a Dama!** - A Dama é valoriza mais aqui do que no Xadrez tradicional. Isto pelo facto de ser o trunfo do Reino. Se tiver que trocar a Dama faça com que seja uma das Bigas/Torres adversárias.
* **Trocas, trocas, trocas** - Isto segue os conselhos anteriores, se estiver a trocar as peças continuamente e com a sua Dama intacta, e também não houver trocas com Canhões adversários, as brancas irão sair com vantagem. A Dinastia tem uma coordenação complexa entre as peças, isto pode ser vencido com menos peças no tabuleiro. O Reino quer um jogo simples, aberto ao passo que a Dinastia procura tomar vantagem a partir dos seus Canhões e miras iniciais.


### Conselhos para a Dinastia (vermelho)

* **Aprenda o movimento das peças!** - Pode parecer óbvio, mas a maior parte dos jogadores novos esquece-se de que os soldados se podem movimentar para os lados.
* **Estrutura dos Soldados - EVITE MOVIMENTÁ-LOS** - Isto pode parecer estranho em comparação ao Xadrez tradicional, mas os Soldados não se precisam movimentar no desenvolvimento das suas peças ou na maior parte dos ataques. A posição inicial dos seus quatro soldados iniciais já está optimizada. Estes defendem-se mutuamente e evitam as brancas de colocarem peças na 5ª linha. Como tal cada par tem um valor maior do que uma peça menor. Mantenha-os na sua posição inicial e use-os como Mira para os seus Canhões a fim de cortar o jogo às brancas e o seu desenvolvimento de peças. Mesmo lendo "EVITE MOVIMENTÁ-LOS" se for forçado a fazê-lo irá obviamente ter de movimentar os Soldados.
* **Soldados na mão - Use como trunfo** - Como já descrito acima, a estrutura dos Soldados já é a ideal. A colocação destes sem uso aparente danifica a sua estrutura e estraga a sua iniciativa. Use os seus reforços quando as brancas estão a planear atacar um dos soldados com um peão mais outra peça. Se houver uma troca com o soldado, pode usar os seus reforços para voltar a ter a estrutura inicial.
* **Troque os seus Canhões o mais cedo possível** - Como já referido acima nos Conselhos do Reino, os Canhões perdem o seu valor ao decorrer do jogo. Estes podem ser usados para algumas tácticas mortiferas, mas o jogador da Dinastia tem de ter em consideração que a existem uma pequena margem para isto. É recomendado trocar um dos seus canhões no inicio de jogo. Permitindo ao segundo Canhão maior facilidade de movimento.
* **Active as suas Bigas/Torres** - Este é um conselho vindo das bases do Xiangqi. A Dinastia começa com colunas abertas para as Bigas/Torres - Faça com que estas entrem em jogo cedo. Quando as Torres inimigas entram em jogo, esta vantagem desaparece facilmente.


### Tácticas

**Mate do Louco**

Se jogas de brancas, evita esta situação. Atenção aos canhões

![Mate do Louco](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/FoolsMate.png)

Esta é a razão pela qual 1.e3 é a abertura mais popular. Se não for 1.e3 então 2.e3, é jogada. Após isto, se o Canhão atacar, este pode ser bloqueado por um Bispo ou um Cavalo, que irá continuar pregado por um bocado. 1.e4 não é comendado por não ser ameaça nenhuma (o Peão está pregado à sua coluna por estar no meio entre Reis).

**Assassino de Dama**

Esta é uma táctica bastante mortifera que pode resultar na derrota das brancas se não tiverem cuidado. A situação é de que a Biga/Torre tem uma coluna aberta (pela qual já começa com esta) e de que o Canhão tem o caminho aberta para as casas b1 ou g1. Esta casa pode ou não ter um Cavalo lá, mas se estiver vazia, o Cavalo não pode protegê-la a fim de isto resultar.

![Assassino de Dama](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Queenslayer.png)

Quanto esta posição acontecer, a Biga/Torre pode capturar o peão, fazendo com que a Torre seja forçada a capturar a Biga/Torre. Isto expõe a casa b1/g1 a ataques do Canhão, que irão ameaçar a Dama e pregá-la ao atacar o lado desta (b1), ou efetuar a tática do espeto no lado do Rei(g1). De uma forma ou outra a Dama irá ser capturada.
