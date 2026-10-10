# ![ShoShogi](https://github.com/pychess/pychess-variants/blob/master/static/icons/ShoShogi.svg) Sho Shogi

![ShoShogi](https://github.com/pychess/pychess-variants/blob/master/static/images/ShoShogi.png)

Shō Shogi (小将棋 'small chess') is a 16th-century form of Shogi (Japanese chess), and the immediate predecessor of the modern game. It is played on a 9×9 board with the same setup as in modern shogi, except that an extra piece is placed in front of the king: a 'drunk elephant' that promoted into a prince, which acts like a second king. According to the Sho Shōgi Zushiki, the drunk elephant was eliminated by the Emperor Go-Nara (reigned 1526–1557), and it is assumed that the drop rule was introduced at about the same time, giving rise to shogi as it is known today.

## Rules

- No drops and no pockets. Captured pieces are not returned to play.
- Each side has one extra piece: the **Drunken Elephant**.
- The drunken elephant promotes to the **Crown Prince**.
- After promotion, a side can effectively have two king-like royal pieces (king + prince).

![image](https://github.com/pychess/pychess-variants/blob/master/static/images/DrunkenElephant.png)

The **Drunken Elephant** can step one square in any direction, orthogonal or diagonal, except directly backward.

![image](https://github.com/pychess/pychess-variants/blob/master/static/images/CrownPrince.png)

The **Crown Prince** can step one square in any direction, orthogonal or diagonal. The Crown Prince effectively doubles as a second king, and must also be captured to win if present.

## Clarification

At the moment, PyChess does **not** support the so-called **bare king** rule in Sho Shogi.
This is due to current Fairy-Stockfish technical limitations.
Support may be added in the future.
