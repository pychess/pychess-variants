<h1 align="center">Alternate Variants</h1>
<div class="meta-headline">
    <div class= "meta">
        <span class="text">2024.06.25</span>
        <span class="text"><a href="/@/autocorr">@autocorr</a></span>
        <span class="text">Announcements</span>
    </div>
    <div class= "headline">An additional PyChess server for alternate variants</div>
</div>
</br>

![ALT server](https://github.com/pychess/pychess-variants/blob/master/static/images/alt-server-boards.png)

The developers of PyChess have a strong commitment to stability and quality. It is this happy circumstance that allows players to enjoy the rich features available on the site for a multitude of variants, and be confident that those features will work tomorrow, and the day after that. These features include tournaments, play against Fairy-Stockfish, an analysis board, post-game move-by-move analysis, a board editor, correspondence games, tactical puzzles, and more. Like other prominent open source software projects, these features require on-going maintenance effort simply to keep the site working, and often the more features, the more maintenance work required. For these reasons, the PyChess maintainers apply an understandably conservative approach to adding new features and variants.

To help provide a playground for testing both new variants and variants of more niche interest, I ([@autocorr](https://www.pychess.org/@/autocorr)) have deployed a fork of the PyChess code that includes a variety of alternate variants. This "Alt site" is available here at [https://pychess-alternates.onrender.com/](https://pychess-alternates.onrender.com/). At the time of this writing the site contains approximately 45 unique variants and close to 60 when including 960 versions of the same. Notable variants include [Kinglet](https://www.chessvariants.com/winning.dir/kinglet.html), [Knightmate](https://www.chessvariants.org/diffobjective.dir/knightmate.html), [Nightrider Chess](https://greenchess.net/rules.php?v=nightrider-2), several [Makruk](https://en.wikipedia.org/wiki/Makruk) variants, [Shatranj](https://en.wikipedia.org/wiki/Shatranj), [Reformed Courier-Spiel](https://www.chessvariants.com/rules/reformedcourier-spiel), mirror variants of Shinobi and Spartan, [Yari Shogi](https://www.chessvariants.com/ms.dir/yarishogi.html), [Wildebeest](https://www.chessvariants.com/play/wildebeest-chess), and [Tencubed](https://www.chessvariants.com/play/tencubed_chess.html).

Not all features of the main-site are supported (notably, tournaments are missing), and priority is placed on implementing real-time games and the analysis board. The Alt site will also be less stable, have poorer up-time, and generally a higher degree of bugs than the main site. Keeping these limitations in mind, I hope players will enjoy the variants currently available to play!

I'm happy to take suggestions on the PyChess Discord server (see the invite link at the bottom of the page). Similar to the main site, the principle limitation to adding variants is that they are supported by Fairy-Stockfish. Further, please show the PyChess maintainers respect and do not pester them to add variants on the Alt site to the main site. Happy playing! :)

-autocorr