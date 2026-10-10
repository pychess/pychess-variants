# Terminologia

Ao longo deste site e dos guias presentes, são usados diversos termos. A maioria destes termos são globais e aplicam-se a todas as formas das variantes de Xadrez, alguns dos termos são usados nalgumas variantes (byo-yomi), e outros têm implicações diferentes dependendo da variante (ex: rei afogado). Qualquer termo usado numa única variante será explicado aqui (ex: muitos termos de Shogi). Esta página serve como referência a fim de esclarecer algumas confusões! 

# "Variantes de Xadrez"

O termo mais importante a ser esclarecido é a definição de "**Variante de Xadrez**". Não existem dúvidas de que o Bughouse e o Crazyhouse são variantes de Xadrez, pelo facto de serem derivadas deste. No entanto existem jogos locais como o Xiangqi, Shogi, Janggi e o Makruk que também podem ser considerados "Variantes de Xadrez" e isto pode causar alguma confusão.

A maior enciclopédia para Variantes de Xadrez, chessvariants.com tem um artigo complete dedicado à definição de Variantes de Xadrez em inglês ["O que é uma variante de Xadrez?"](https://www.chessvariants.com/what.html). Aqui no Pychess temos a mesma opinião feita. A fim de simplifcar, "Variante de Xadrez" significa um jogo de estratégia feito por turnos, derivado do Chaturanga, onde as peças têm movimentos distintos e que o objetivo é de capturar ou de dar "Xeque-Mate" ao Rei adversário. Mesmo pelo facto de que as Variantes do Este não são derivadas do xadrez, ambas têm o mesmo antepassado, e ambos os seus nomes têm o mesmo significado de "Xadrez". Desta forma, o "Xadrez" nas variantes de Xadrez dará assim um conceito geral de um jogo parecido ao Xadrez, em vez de ser o Xadrez internacional com regras de FIDE. Isto também é representado na maioria dos desportos, onde "futebol" tem um significado diferente em vários locais.

Pelo facto das variantes de Xadrez serem baseados no Xadrez internacional, tal como todas as formas de "Xadrez", existe uma ambiguidade aqui. Na maioria das vezes, podemos chegar à conclusão do que se trata cada tipo de variante pelo nome. No entanto é pode ser considerada uma falha haver este termo ambiguo, e talvez quando se debate sobre todas as formas de Xadrez, então um termo geral denominado de "Variantes como o Xadrez" podia ser usado.

# Peças

**Peças Heterodoxas** - Uma peça não muito comum no Xadrez, como o nome "Heterodoxa" (ingles "Fairy") descreve como "invenção". Não é muito claro se as peças nativas de variantes locais são consideradas "Peças Heterodoxas", mas optamos por não usar este termo para tais jogos. No entanto o Canhão de Xiangqi existe numa variante de Xadrez (como Shako), ou o Bispo que podia porventura aparecer numa variante de Xiangqi podia ser denominado de "Peça Heterodoxa", por não existir no jogo original.

De notar que existem peças que são do mesmo tipo, mas têm nomes distintos. Por exemplo a "Torre" e "Biga" que se referem à mesma peça. O nome é referência para cada jogo que é usado.

## Classificação

Pelo facto das Peças Heterodoxas introduzirem várias peças possíveis, existe um sistema de classificação para tal. Também existem notações usadas para descrever os seus movimentos, mas isto está fora do âmbito desta página. Existem três tipos de peças simples:

**Cavaleiros** (também conhecidos como peças de longo alcance) são peças que se continuam a mover numa direção não definida até serem bloqueados por outra. A Torre e o Bispo são exemplos clássicos do Xadrez.

**Saltadores** são peças que têm movimentos fixos e podem saltar outros a fim de chegarem ao seu destino. O Cavalo do Xadrez é um Exemplo clássico. O Cavalo em Xiangqi e Janggi é um Saltador modificado por poder ser bloqueado. Peças semelhantes também podem ser denominadas de "Saltadores Fracos" ("lame leapers").

**Puladores** são peças que precisam de ter outra à sua frente antes de se movimentarem ou capturarem. Não existem puladores em Xadrez, mas o Canhão de Xiangqi (captura na ortogonal saltando outra peça à sua frente) e também o Canhão de Janggi (captura e movimenta-se na ortogonal se tiver outra peça à sua frente) são puladores clássicos.

E por fim, **peças compostas** são peças que combinam o movimento de duas peças base. A Dama do Xadrez, combina a Torre e o Bispo, é um destes exemplos. Existem várias peças heterodoxas que são compostas.

# Relógio

O Relógio determina restrições no tempo da partida a fim de punir aquele que possa levar demasiado tempo a efetuar um lance. Um tipo de jogo, chamado **correspondência**, é conhecido por usar um relógio longo de no mínimo algumas horas, tipicamente contado em dias. Os jogadores típicamente fazem os seus lances após espairecerem de um dia dificil. Neste momento os jogos por correspondência não estão disponíveis no Pychess.

As partidas feitas de uma só vez usam um relógio principal definido de 1 minuto a 60 minutos, onde cada jogador tem o seu próprio cronómetro. Um jogador pode ou não obter tempo extra durante o jogo. Existem três tipos de relógio que irão indicar como o tempo extra irá ser obtido:

1. **(Fischer) Incremento** - A cada lance, um jogador ganha um certo número de tempo no seu relógio. Um jogo no Pychess denominado de "10+15" significa que o jogador tem 10 *minutos* de tempo inicial e 15 segundos de incremento. Isto é o modo de defeito usado na maioria das variantes.

2. **Byo-yomi** - (Japonês para contagem) Significa que quando o relógio principal de um dos jogadores expira, este tem um tempo fixo para efetuar cada um do seu lance a partir deste ponto. Este sistema é usado em Shogi e Janggi. Existem vários períodos de byo-yomi que podem ser usados, tipicamente em Janggi. Por exemplo, se existem 3 períodos, então o jogador pode deixar o seu relógio expirar 3 vezes antes de perder. Isto pode ser muito útil em jogadas criticas, onde um único período de byo-yomi não basta para uma situação delicada. Um jogo em Pychess denominado de "10+3x30(b)" significa 10 *minutes* no tempo inicial e 3 períodos de 30 segundos de byo-yomi. 

3. **Morte súbita** - Sem tempo extre. Um jogo que usa incremento ou byo-yomi pode ser configurado para morte súbita ajustando as configurações para 0 segundos.

# Conceitos Gerais

**Xeque** - Ameaçando o Rei com uma peça que o possa capturar no lance seguinte.

**Xeque-Mate** - O objetivo principal em Xadrez, onde o Rei não pode escapar do Xeque. O jogador que leva Xeque-Mate perde.

**Rei Afogado** - Quando o Rei não está em Xeque, mas não tem movimentos legais. No Xadrez, isto é considerado empate, mas nalgumas variantes (como o Xiangqi), isto é considerado derrota para quem está afogado.

**Repetição** - Quando existe repetição da mesma posição no tabuleiro pelo menos três vezes. Isto acontece geralmente quando algumas peças se seguem mutuamente. Existem determinadas variantes que tratam da repetição de maneira diferente. Mesmo dentro do mesmo jogo, existem determinadas Federações que tratam desta regra de maneira diferente.

**Xeque Perpétuo** - Semelhante à repetição, mas o jogador dá xeques contínuos ao Rei e eventualmente repete a posição. As regras de xeque-perpétuo também variam de variante a variante e de federações a federações.

**Linha** - Linha do Tabuleiro

**Coluna** - Coluna do Tabuleiro

**Notação** - Sistema usado em cada um dos jogos para referir a posição no tabuleiro, usa-se abreviaturas de peças e o tipo de lance a cada turno.

**Standard Algebraic Notation (SAN)** - ou Notação Algébrica Standard - Notação usada em Xadrez. Cada lance é descrito com o nome da peça (à exceção do Peão), seguidamente da sua casa final. Letras adicionais são usadas como esclarecimento.

**Lance** - Um lance em xadrez é o movimento da peça por cada um dos jogadores. No entanto em Shogi, um lance é descrito como um movimento único de cada jogador. No Xadrez, pode acontecer haver "Xeque-Mate em 1", 2, 3, etc.. mas em Shogi, só pode haver Xeque-Mate em 1,3,5,7, etc...

**Colocação** - Um lance feito pela colocação de uma peça capturada como sua. Isto é estipulado em Shogi ou Crazyhouse e não pode ser feito no Xadrez. As variantes que permitem a colocação são denominadas de "Variantes de Colocação", e existem várias destas aqui no Pychess (na maioria das vezes têm o sufixo "House")

**Zona de Promoção** - Área do tabuleiro onde as peças podem ser promovidas. No Xadrez, os Peões só podem ser promovidos na última linha. No entanto em Shogi, a zona de promoção são as três últimas linhas, e grande parte das peças podem ser promovidas. Outras variantes podem ser diferentes na sua zona de promoção.

# Táticas

**Garfo** - Atacar duas peças ao mesmo tempo. Os Cavalos são quem efetuam mais esta tática em todas as variantes. Nas variantes de colocação, as Torres e os Bispos também são capazes de tal tática.

![Fork example](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Fork.png)

**Espeto** - Atacar uma peça que não se pode mover, caso contrário irá expor um ataque a uma mais valiosa (na maioria das vezes o Rei)

![Pin example](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Pin.png)

**Raio-X** - Semelhante ao espeto, mas ataca duas peças na mesma linha de fogo estando a mais valiosa na frente. A peça mais valiosa é obrigada assim a se mover, permitindo ao atacante capturar a segunda peça exposta.

![Skewer example](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Skewer.png)

**Ataque por Descoberta** - Uma das peças poderia porventura atacar a peça adversária, mas está bloqueado por uma peça que é sua. Movendo a peça que está a bloquear (e ao mesmo tempo ameaçando a peça adversária), irá abrir esta peça e começar um ataque, isto é geralmente chamado de ataques por descoberta. Ataques por descoberta existem em grande quantidade no Xiangqi.

![Discovered attack example](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Discovery.png)

Nesta situação, movendo o Cavalo para ameaçar a Dama também faz com abra Xeque ao Rei pela Torre. Pelo facto das Pretas terem de responder ao Xeque, as Brancas podem capturar a Dama. Se ao trocarmos a posição da Dama Preta e o Rei, o resultado final seria o mesmo (as Pretas iriam perder a Dama)

**Sacrifício** - Oferecer material a fim de obter uma posição melhor.

![Sacrifice example](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Sacrifice.png)

Neste exemplo, se a Dama capturar o Cavalo Preto, esta pode ser recapturada facilmente por um Peão. No entanto isto abrirá caminho para o Cavalo dar Xeque-Mato (Seta vermelha). A Dama foi sacrificada para um objetivo maior.
