<p align="center">
  <img src="https://github.com/pychess/pychess-variants/blob/master/static/images/MidAutumnFestival/20210915_134909.jpg" alt="Mooncake placed next to set-up Xiangqi board">
</p>

<h1 align="center">Mid Autumn Festival</h1>
<div class="meta-headline">
    <div class= "meta">
        <span class="text">2024.02.13</span>
        <span class="text"><a href="/@/CouchTomato87">@CouchTomato87</a></span>
        <span class="text">Blog</span>
    </div>
    <div class= "headline">Celebrating the Mid-Autumn Moon Festival with Chess</div>
</div>
</br>

Note: this blog originally was posted at 2021.09.15 on lichess.org
Even though this was from a different holiday, we wish everyone a happy Lunar New Year!

An introduction to some things Chinese - culture, food, and of course, chess.

## **Intro**

For those who aren't familiar (and most probably won't be), next week will be the Mid Autumn Festival. What exactly is that? It's the second most important holiday for Chinese culture (but also celebrated by many Asian cultures in some form), basically the halfway point until the next year. Traditionally, it's celebrated in part by hanging many, many red lanterns.

![image](https://github.com/pychess/pychess-variants/blob/master/static/images/MidAutumnFestival/mid-autumn-festival.jpg)

Being raised in the US, that's something I unfortunately don't get to see much at all. But the other big tradition is eating *moon cake*. You can even see myself getting ready to eat some delicious moon cake in the picture above! Moon cakes are amped with sugar, but delicious nonetheless! If you haven't had moon cake, it's worth a try. On top of that, at my parents' home, I always love to be treated by homecooked dumplings, which are one of my favorite foods. For those who haven't had dumplings, they are definitely worth having, as they're basically like good old delicious soul food.

![image](https://github.com/pychess/pychess-variants/blob/master/static/images/MidAutumnFestival/dumplings.jpg)

Anyways, that brings me to the next part of this brief cultural tour, which is chess! Specifically, **Chinese chess**. This is also known as Xiangqi (pronounced very similar to the Marvel superhero Shang-Chi. If you haven't already, go watch the movie!). For those who don't know, xiangqi is a sister version of chess. Both ultimately derived from Chaturanga, but with unique spins on the game. It is no historical relic either or simply just a traditional game. It's one of the most widely played board games in the world, with a large number of Chinese and Vietnamese players. Multiple xiangqi federations exist with their own grandmasters as well. So if you haven't played it before... *it's worth a try*.

### **Why play Xiangqi?**

Some reasons come to mind...

* Getting a fresh new chess experience
* Xiangqi focuses on different skills on Chess (e.g. more tactical), which could also improve your Chess game
* Unlike many other variants, it's a game that's widely played, so players and literature are definitely there (just not easily available in English)
* For those who like playing with different pieces, the cannon is a very different piece.
* Opening strategy is far less important than Chess, making it very easy to jump straight in and not be overwhelmed by having to learn multiple opening lines. Instead, it's all about the endgame.
* Games are quick, often quicker than Chess in my opinion, so each game is not much of a time commitment.
* The game is also faster paced than Chess.

Don't be discouraged by the Chinese character pieces either! For those who want to attempt to learn them, they're pretty easy as far as Chinese characters go (half of them are pictograms -- for example, the character for elephant 象 resembles the face of an elephant), far fewer pieces and much less complicated than Shogi too. And for those who don't, the websites you can play at all offer internationalized or westernized pieces.

Speaking of websites, I'll be using Pychess as an example, because I feel it's the best site equipped for Xiangqi at the moment. That is, until a Lichess fork for Xiangqi comes out (dibs on liqi.org, anyone??). I'll spend the next few sections briefly introducing the game.

Ultimately, the point is to try a new experience. Going back to food, Chess is kind of like pizza. Most people love it. But it doesn't hurt to have other go-to options for food either. My actual favorite chess variant is Shogi. Because Shogi is far more complex than other variants, it's like an expensive *omakase* course of sushi. That, of course, is amazing. But even that, I can't eat that all the time. Sometimes I'd like to go back to pizza. Or other times, I'd like to have some good old dumplings, which is Xiangqi. And there's nothing wrong that.

## Xiangqi in a Nutshell

![image](https://github.com/pychess/pychess-variants/blob/master/static/images/MidAutumnFestival/XiangqiBoard.png)

At a glance, the board looks quite different. Pieces play on intersections rather than squares, but for all intents and purposes, it's a cosmetic difference. Aside from that, you'll also notice a **river** running through the middle and two **palaces**. The river simply acts as a promotion marker for pawns and also blocks elephants from passing. The palaces prevent the king and his two advisors from leaving. The king is more restricted because it can't move diagonal... These lead to completely different kinds of mate patterns in Xiangqi than in Chess.

With a much weaker king also comes much weaker pieces. For starters, there are no queens. The chariots (=rooks) are the strongest pieces in the game.

The minor pieces are where it diverges quite a bit. Rather than the pair of the bishop and knight in Chess, you have the cannon and horse in Xiangqi. Cannons also move like rooks, but to capture they need to jump over an intervening piece. Horses move like knights, but can be blocked. If you think of a horse move as one square orthogonally and then one diagonally (like a Y shape) then it makes sense.

![image](https://github.com/pychess/pychess-variants/blob/master/static/images/MidAutumnFestival/XiangqiPieces.png)

## Tactics

One reaction might be to complain that pieces are too weak, like the horse. But keep in mind that *everything is weaker*, and the game is about how you coordinate these pieces to checkmate. Not only that, but the board is immediately open from the start, so pieces are able to develop much faster than in Chess. Finally, the fact that these pieces can be blocked opens up a new box of tactics involving *blocking*. You can jam up a cannon or horse without retaliation. Aside from pawns, this concept is impossible in Chess as a "block" really requires another piece as backup because the "blocked" piece can always retaliate. In Xiangqi, the chariot is the only piece that can't be blocked like this.

Here are some examples:

**Discovery Attacks** \- While not new in Xiangqi, these are far more prevalent\. A common example:

![image](https://github.com/pychess/pychess-variants/blob/master/static/images/MidAutumnFestival/Discovery.png)

*The red chariot can threaten to take the black chariot on the next move by opening up a check on the king via the cannon.*

**Blocking** \- Here are some examples of blocking:

![image](https://github.com/pychess/pychess-variants/blob/master/static/images/MidAutumnFestival/HorseSuffocation.png)

*Black's now in a sticky situation because his left horse (right on the image) is stuck and it's hard to develop his chariots.*

![image](https://github.com/pychess/pychess-variants/blob/master/static/images/MidAutumnFestival/Blocking.png)

*Red's horse would have mated the king if black's chariot didn't block it.*

## The Art of War

From the start, the board is nicely divided into two halves. These can be divided more as defenders line up along the middle file, which results in two "theaters at war." These can communicate with each other in different ways, for example a cannon locking down the palace's defenders in one side, letting the other side attack with aggression -- similar to how the Americans and Soviets came upon Nazi Germany at the same time from different sides in WWII.

![image](https://github.com/pychess/pychess-variants/blob/master/static/images/MidAutumnFestival/Lockdown.png)
*Here, red's cannon has black's defenders pinned (both the advisor and elephant are diagonal pieces). Red can deliver checkmate with the chariot if black does not intervene.*

With this in mind, the importance of the concept of **tempo** is also really emphasized in Xiangqi. You could be down material, but as long as you are on the right side of the board with the necessary pieces you need to win, you can pull a win out from under your opponent. If both players recognize this, they may both try to capitalize on their advantages on different sides of the board and try to achieve checkmate first. This can start all the way back to the very early moves where every wasted move could be the difference between a win and a loss.

In Chess, this situation does not come up in the same way as the board is more often one giant field with long-ranging pieces covering multiple areas of the board.

That was just the iceberg though. There are far more strategies and concepts involved, many of which I'm not even well-versed in! This was just meant to get a feel for the style of the game.

## Resources

### [THE RULES](https://www.pychess.org/variants/xiangqi)

### Online game servers (English):

[Pychess](https://www.pychess.org) \- Chess variant website modeled after Lichess\. Active tournaments, best engine for AI play and analysis\. Small but active player base\. \(*Note, there is an upcoming [Xiangqi tournament](https://www.pychess.org/tournament/yFUs7hAk) this Sunday, 9/19!).* No additional registration required -- Pychess uses Lichess' login for authentication.
[Xichess](https://www.xichess.com) \- Interface styled after Lichess\. Typically requires a challenge to play\.
[PlayOK](http://www.playok.com) \- Board game website with the largest number of players \(mostly Chinese/Vietnamese\) for an English site\. Also one of the best place to hone skills against hard players\. However, no AI, analysis, or tournaments\.
[Xiangqi.com](https://www.xiangqi.com/) \- Relatively new website, whose interface is more styled after Chess\.com\. Best source of resources\.

### Communities (English):

Discord Server: [Pychess Players](https://discord.gg/aPs8RKr)
Discord Server: [Xiangqi International (En)](https://discord.gg/2nC6M2Z6)

### YouTube:

[www.xqinenglish.com Videos (Jim Png)](https://www.youtube.com/c/wwwxqinenglishcom/featured)

### Articles:

[Xiangqi.com articles](https://www.xiangqi.com/articles)

## Conclusion

Anyways, that's all I have to offer. This is a bigger blog post than what I intended. But it's a game that's been a part of me for most of my life. I learned Xiangqi at around the same time as I learned Chess -- and unfortunately, I'm not that great in either! But either way, my hope is that it one day becomes a game that's not "exclusive" to East Asia. As with Chess, Shogi, and Go, it's another one of several strategy board games with a rich history and the depth to go along with it. And for those who celebrate the Mid-Autumn Festival, enjoy!
