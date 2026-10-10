# ![Shogun](https://github.com/pychess/pychess-variants/blob/master/static/icons/shogun.svg) Shogun Chess

![Shogun](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ShogunPromotions3.png)

O Shogun é uma variante de Xadrez criada em 2019-2020 por Couch Tomato. Enquanto a variante em si é uma mistura de Xadrez e Shogi, a ideia principal do jogo foi a introdução de peças híbridas (normalmente denominadas de Arcebispo e Chancelor) de maneira diferente do habitual. Por exemplo, manter um tabuleiro 8x8 em vez de aumentar o seu tamanho a fim de não diminuir o valor das peças menores, ou introduzi-las num tabuleiro não muito congestionado como o Seirawan Chess. A ideia veio da introdução destas peças via promoção de peças menores e da Torre a partir da linha anterior à 8ª. Mais tarde, as colocações de peça também foram adicionadas a fim de reforçar a defesa contra as promoções. Promoções únicas de peões e cavalos e também a despromoção da Dama foram adicionadas à variante a fim de completar o tema e a simetria.

O nome original estava para ser "General's Chess" (Xadrez de Generais), baseado no nome da promoção de peões, agora sendo o da promoção dos Cavalos. No entanto pelo facto das colocações e promoções de zona serem baseados baseados em shogi, a palavra Shogun pareceu ser mais apropriada. Pelo facto do Sho de Shogun ser o mesmo do Shogi prestando assim uma homenagem a este.


## Regras Gerais

1. A posição inicial é a mesma do Xadrez.

2. As novas peças estão representadas na imagem acima, e os seus movimentos na descrição abaixo. De notar que as peças promovidas são representadas com cores diferentes. Também de notar que a Dama *começa* como sendo uma peça promovida havendo assim uma forma desta não promovida (a Duquesa). Veja mais detalhes sobre as colocações abaixo. Por uma questão de terminologia, a Torre irá ser considerada uma "peça menor", enquanto que a Dama, o Morteiro, o Arcebispo e o General(excluindo o Capitão) são consideradas "Peças Maiores".

3. As três últimas linhas são consideradas zonas de promoção. Todas as peças iniciais (ou colocadas) excepto o Rei e a Dama podem ser promovidas quando chegarem a esta zona de promoção **ou quando são movidas dentro desta zona de promoção**.

4. No entanto, só pode haver uma de *cada* peça **Maior** (Dama, Morteiro, Arcebispo ou o General) por cada jogador. Por exemplo, se um jogador tem um Arcebispo em jogo, então um Bispo não pode ser promovido para Arcebispo enquanto este não for capturado.

5. Como em Crazyhouse e em Shogi, as peças capturadas podem ser colocadas no tabuleiro como suas. As peças podem ser colocadas nas primeiras 5 linhas (por outras palavras, em qualquer casa exceto na zona de promoção). De notar que ao contrário de Crazyhouse, **Os peões podem ser colocados na primeira linha**.

6. Quando as peças promovidas são capturas, estas irão para a mão do adversário como peças despromovidas. Este é o único caso em que a Dama se transforma na Duquesa.

Regras adicionais para clarificação:
* Torres colocadas não podem efetuar Roque, como em Crazyhouse.
* Peões colocados na primeira linha podem avançar duas casas após atingirem a segunda linha.
* Os Peões não podem ser promovidos quando capturarem em en passant.

(De notar que as imagens foram feitas para jogos entre computador. Não existem peças de tabuleiro disponiveis, implicando assim o uso de peças de Shogi bi-dimensionais a fim de efetuar este jogo.)

*Relógio* - O Shogun usa um relógio byo-yomi. Quando o relógio principal do jogador chega ao fim, este entra em byo-yomi. Se tiver definido a 30 segundos então este jogador terá 30 segundos para efetuar o seu lance e a partir dai terá os mesmos 30 segundos para os próximos lances, se estes expirarem então será declarada derrota por tempo. A razão pela qual se usa byo-yomi em vez do relógio de incremento de Fischer é de que o fim-de-jogo tem uma maior duração do que a abertura, então o byo-yomi garante que haja tempo suficiente para cada lance.

## Peças

### Arcebispo

![Archbishop](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/ArchbishopShogun.png)

O Arcebispo é uma peça híbrida já muito usada noutras variantes. Nesta variante, esta é promovida a partir do Bispo e ganha os mesmos movimentos de um Cavalo. Por causa dos seus movimentos únicos, esta é a única capaz de dar Xeque-Mate por si mesma.

### Morteiro

![Mortar](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Mortar.png)

O Morteiro é uma peça híbrida já muito usadas noutras variantes, na maior parte das vezes denominada de Chanceler ou Marechal. Nesta variante, esta é promovida a partir da Torre e ganha os mesmos movimentos de um Cavalo.

### General

![General](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/General.png)

O General é uma peça híbrida, geralmente conhecida como Centauro. Neste jogo, é promovida a partir de um Cavalo e ganha os mesmos movimentos de um Rei.

### Capitão

![Captain](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Captain.png)

O Capitão é a única promoção de um Peão e movimenta-se exatamente como um Rei. Sendo uma peça não-Real, capturando o Capitão não dará o jogo como concluido. De notar que ao contrário das outras peças, podem existir vários Capitães em jogo, pelo facto de não ser uma Peça Maior.

### Duquesa

![Duchess](https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Duchess.png)

A Duquesa é a única despromoção da Dama, e só chega a jogo após a captura da Dama, por se tornar numa Duquesa às mãos do adversário. A Duquesa movimenta-se apenas uma casa na diagonal (Mesmo movimento do chamado "ferz"). Como lembrete, a Duquesa não pode ser promovida caso o jogador já tenha uma Dama em jogo (A poligamia é ilegal em Shogun).

## Estratégia

Pelo facto de ainda ser uma variante recente, a estratégia ainda está em desenvolvimento! 

Pelo facto da zona de promoção ser na 6ª linha, é necessário reforçar a defesa na sua 3ª linha. Isto é algo que qualquer iniciante pode facilmente observar.

Estrategicamente falando, qualquer jogador poderá tentar jogar esta variante como se fosse Crazyhouse. No entanto, existem grandes diferentes comparativamente ao Crazyhouse, começando com a restrição nas colocações. Enquanto um jogador de Crazyhouse tomará partido das fraquezas em território inimigo, isto se torna impossivel em Shogun. Nesta variante, o seu exército precisa de se posicionar corretamente a fim de atingir o território inimigo; Isto porque à minima abertura, isto fará com que haja promoção de peças. Daí concluir que a estratégia usada aqui está mais próxima de táticas de Xadrez do que táticas de Crazyhouse, tanto como para promoções do que como para dar Xeque-Mate.

De notar que sendo permitindo a colocação de Peões na primeira linha (ao contrário de Crazyhouse) isto permite ao jogador a construção de uma defesa ainda mais poderosa. Para quebrar esta defesa, concentre-se em ganhar material e promover peças, e após isto criar aberturas no adversário.
