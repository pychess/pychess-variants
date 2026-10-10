<h1 align="center">Shinobi Arrives in Time For the Sakura Blossoms</h1>

<div class="meta-headline">
    <div class= "meta">
        <span class="text">2021.04.21</span>
        <span class="text"><a href="/@/CouchTomato87">@CouchTomato87</a></span>
        <span class="text">Announcements</span>
    </div>
    <div class= "headline">Shinobi Chess has arrived!</div>
</div>
</br>

<p align="center">
  <img src="https://github.com/pychess/pychess-variants/blob/master/static/icons/shinobi.svg" width="150" height="150">
</p>
<br>

<p align="center">
  <img src="https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Shinobi.png" width="492" height="589">
</p>
<br>

Hey everyone, Couch Tomato here! I'm pleased to announce that my latest variant, Shinobi Chess is now available to play on Pychess! Much like most of my other variants, this is another asymmetric game pitting the classic chess army (the Kingdom) against the Sakura Clan. As with all other new armies I've made, the Clan also has its own theme and quirk. The theme is quite obvious, and the quirk is that they have the ability to drop a lot of pieces (five pieces start in hand!) as well as promote, basically almost straight out of Shogi for those are familiar with it. I could go on, but I would be repeating myself from what's written in the [guide](https://www.pychess.org/variants/shinobi), so hop on over and check it out!

Instead, I figure I can give a brief history of the game's creation, something that I typically do not put into the guides. Empire Chess -- which is currently available on Vchess, and wasn't playable on Pychess because of Fairy Stockfish restrictions at the time -- was intended to be my last variant. I had one more idea in mind for a unique army, one that would use extensive use of drops. However, I realized that this would require weak units and eventually the ability to promote to compensate. While this could be defined in Fairy Stockfish, this would lead to problems in Winboard, which is the software I use to test my variants. Winboard unfortunately has a lot of issues with promotions, and I had to shelve the idea indefinitely.

Later, the idea kept swirling in my head despite not being able to playtest it, and I mentally drafted an idea of the game. Originally the theme for the new army was tentatively going to be a "rebel army," which would thematically tie into the ability to drop a bunch of weak pieces all over the place. As the game shaped more, the weak pieces that I used were adopted from Shogi, as they were the most obvious. Similarly, the mechanism for promotion sounded more like Shogi. At this point, I couldn't ignore the homage to Shogi, and I went with a ninja theme, which still makes for sneaky drop-happy army. The titular ninja became the name of the Clan's strongest piece, the archbishop. Actually, I think the name ninja is much better than an archbishop! You can imagine a ninja hopping around (like its horse movement) or charging at an angle with a swift sword strike (bishop movement).

<p align="center">
  <img src="https://github.com/pychess/pychess-variants/blob/master/static/images/CVariantsGuide/Ninja.png" width="492" height="492">
</p>
<br>

The idea, finally named Shinobi Chess ("Ninja Chess" already exists) was then ported to VChess without my usual playtesting. The Clan started with its entire army in hand except for the pawns and its king (called the kage). It was fun, yet obviously skewed in favor of the Clan. At the time, the Clan also had a chancellor, redubbed as the Samurai. At the same time, Fables began to add support for my other variants to Cutechess. Cutechess is more flexible than Winboard, and so it was able to handle promotions. He ran some tests for the original version of Shinobi, which showed the game was indeed skewed towards the Clan (at least 60% win rate, if I recall), and many games reused around the same opening line, which was essentially an abuse of the Clan's powers to immediately pick off an enemy rook.

From there, Fables tested many different combinations and then also provided me with the tools to help out. We went through at least 20 combinations, changing things like the combination of pieces in hand, what rank pieces can be dropped at, and what rank pieces can promote at. Each run was always kind of close, but still significantly skewed towards one side or the other with even the smallest addition. Finally, we tinkered with adding pieces to the board... first lances, then wooden horses, and finally we achieved a 51.7% win rate for the Clan at high time controls, which for all intents and purposes is extremely balanced. So super thanks to Fables! Without you, this game wouldn't be here. And of course, thanks to gbtami and ubdip as always for their role in making the means to make this happen!

On another note, as I was alluding to earlier, I think this may be my last variant. I've exhausted all the ideas I had from the start. If I do add any variants, maybe they'll be  variants of something other than international chess, as there are zillions of variants for that, but not nearly as many for games like Xiangqi and Shogi! Only time will tell.

Anyways, I hope everyone enjoys Shinobi! Tomato out.

![Shinobi](https://github.com/pychess/pychess-variants/blob/master/static/icons/shinobi.svg)  *whoosh*
