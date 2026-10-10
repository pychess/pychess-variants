
# ![Jieqi](https://github.com/pychess/pychess-variants/blob/master/static/icons/Xiangqi.svg) 揭棋 | Jieqi

揭棋是象棋的一种热门玩法，因其随机性和策略性的结合，在中国和越南地区广泛流行，有大量的玩家群体。

## 规则

开局时，每方除将帅以外，其余 15 枚棋子正面朝下打乱顺序，随机摆放在象棋棋盘的 15 个开局棋子位置。这些棋子叫做暗子。

暗子的走法与其所在位置相同。例如，开局在棋盘左下的棋子（车位）拥有车的走法。因此，暗子依其位置也被称为“暗车”“假炮”等。
暗子一旦行动，就翻开成正面朝上。正面朝上的棋子拥有其本身的走法。即翻开是什么棋子，就是什么棋子的走法。

在揭棋中，士象可以过河，在整个棋盘行动。

将帅的活动范围仍旧是九宫内。尚未过河的兵仍然只能向前走一格。

暗子也可以被吃，但被吃的棋子不会亮出。

https://www.chessprogramming.org/Jeiqi [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/deed.en)

## 补充说明

根据维基百科（https://zh.wikipedia.org/wiki/揭棋），双方无法确认被吃的棋子。本站尚未实现。