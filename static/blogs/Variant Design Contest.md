<h1 align="center">Variant Design Contest</h1>
<div class="meta-headline">
    <div class= "meta">
        <span class="text">2024.11.14</span>
        <span class="text"><a href="/@/CouchTomato87">@CouchTomato87</a></span>
        <span class="text">Announcements</span>
    </div>
    <div class= "headline">Create the best chess variant!</div>
</div>
</br>

<p align="center">
  <img src="https://github.com/pychess/pychess-variants/blob/master/static/images/man-design-thinking.453x512.png">
</p>

"[man design thinking](https://iconduck.com/illustrations/173196/man-design-thinking)" by [Streamline](https://iconduck.com/designers/streamline) is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

**Introduction**
We are happy to announce Pychess’ first community contest, the Variant Design Contest! The goal of the contest is to create the *best* chess variant. *But* there will be a special theme for the contest which the designs have to make use of. The winning entry will have the honor of being added to the site. 

The contest (as well as updates and all communications) will be run exclusively via Discord. If you're not already on Discord, you can find the link on the site here below the chat box.

Submissions can either be from individual users or a team of users. However, each member can only have their name attached to one submission. Entrees must be original; you cannot use one that has already been published. "Chess variant" means anything resembling the chess family of games (Chess, Xiangqi, Shogi, etc.) Games that heavily deviate will likely not win; for example, Ataxx would not win. Additionally, the variant must be designed using Fairy Stockfish (see below). If you need help, please ask around.

**Contest format**
As “best” is a subjective determination, we will use judges – the PyChess server admins, who will rate the variants on a 100-point scale. The entry with the highest average score will win. Judges will base their score on fun, uniqueness/creativity, as well as theming.

**Timeline**
December 31, 2024 – Registration closes at midnight -- Please register in this channel.
April 31, 2025 – Submissions are due
June 30, 2025 – Judging ends

**Theme**
The theme is *regions*! Specifically having well-delineated parts of the board that function differently. In Chess and Shogi, there are promotion zones, but this is rather minimal and would be a poor submission. Instead, look more at variants like Xiangqi and Chennis, where pieces are limited to certain regions. While I did say Chess and Shogi would be poor examples, having pieces that can change movement as they promote from one zone (normal zone) to another (designated as the “promotion zone” on Fairy-Stockfish) but then demote when going back to the former zone *would* count as working in the theme.
Keep in mind that Stockfish can have parameters for exactly which squares pieces can move to, drop to, and promote/demote to. 

Tips: A good variant will almost *certainly* require unique board designs to convey movements. There's a lot of creativity that can be done with the options available in FSF. For example, you could have a linear spiral on the board where the king can't escape but moves like a rook and needs to get to the center. You can have a region of the board where there's a super piece like an amazon but is only limited to the region. You can have regions that cause a piece to change (via promotion) but then cannot go back the way it came (like the Divine King in Chak). There are a lot of options available.

**Coding the Variant**
Again, the variant must be compatible with FairyStockfish. This means the variant has to be able to defined using the code in FSF.  At the most basic level, this means no variants larger than 12 x 10. The variant definition code is basically what you'd put in the variants.ini file. All the documentation on that (which is very well explained by ubdip) is [here](https://github.com/fairy-stockfish/Fairy-Stockfish/blob/master/src/variants.ini), and you can see how PyChess implements all our variants [here](https://github.com/pychess/pychess-variants/blob/master/variants.ini). If you're not familiar with variants.ini, don't worry! We'll provide assistance for anyone who's unfamiliar with making a variant definition.

**Playtesting**
Entries should be playtested using FairyStockfish.  At the most basic level, this involves downloading the FairyStockfish engine and then running a script to have the engine play against itself for multiple games. One such script provided by ubdip (FSF’s creator) is [variantfishtest](https://github.com/ianfab/variantfishtest). If there any difficulties, there members in the community that will be be able to help.

Tomato’s standards/recommendations from playtesting are the following:
* Balance – Ideally there should be no larger than a 40/60% winrate between the two sides. Testing should be done over at least 100 games with a long time control.
* Sharpness – Ideally there should not be a forced opening. When looking at the log of AI selfplay, seeing some variation in the opening moves is important.

Don't worry about being particular perfect on these. The design is more important for the contest. The main thing is that the variant is not obviously imbalanced or sharp/limiting in choices.
The chosen winner will likely undergo more vigorous testing with NNUE and ironing out any issues before being added to the site.

**Graphics**
Graphics are *not* a consideration when judging. The entries can be playable using already available symbols if no graphics are provided, and special board graphics can be created by the contestant or Couch Tomato as needed. Naming is (including variant name, piece names, etc) is also not a part of the judging process. The community can assist with polishing the game and creating assets for the winning selection.

-Couch Tomato
