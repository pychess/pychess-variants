# Frequently Asked Questions

## Pychess

<details><summary>What is Pychess?</summary>

Pychess is a website dedicated to allowing people to play major and interesting chess variants (both regional and more modern chess variants). Please see [the about page](https://www.pychess.org/about).</details>

<details><summary>Why is it called Pychess?</summary>

The server code is written in Python.</details>

<details><summary>What is the difference between this and the software?</summary>

Both are designed to play chess variants, and both share the same developer ([gbtami](https://www.github.com/gbtami)). However, the similarities end there. The full name for this site is "Pychess Variants" for distinction, but is often just called Pychess. The site for the desktop application is [here](https://pychess.github.io/).</details>

<details><summary>What is the relationship to [Lichess](https://lichess.org/)?</summary>

Pychess's design is heavily influenced by Lichess and is meant to be comfortable for Lichess users. Pychess has no official relationship to Lichess. However, it does use Lichess accounts to facilitate user management.</details>

<details><summary>What is Fairy-Stockfish?</summary>

Stockfish is one of the premier engines designed to play chess. [Fairy-Stockfish](https://github.com/ianfab/Fairy-Stockfish) is a fork of that created by [Ianfab](https://www.github.com/ianfab) to handle multiple chess variants.</details>

<details><summary>Is level 8 Stockfish the strongest available?</summary>

It is the strongest available on this site, but does not represent Fairy-Stockfish at full strength. Full strength requires more time to think and analyze; on Pychess, Stockfish is limited to less than a second for each move.</details>

<details><summary>I found a bug! Where do I report it?</summary>

[Make an issue](https://github.com/pychess/pychess-variants/issues/new). Ultimately it needs to be filed in the Github issue tracker. Ideally, try to find a way to reproduce this bug in your description (if necessary, include the browser and OS). If you're not on Github, you can also mention it on Discord, and someone else can file it.</details>

## Variants

<details><summary>What games are available?</summary>

Check out the [Variants page](https://www.pychess.org/variants).</details>

<details><summary>How do you play XXX?</summary>

Check out the [Variants page](https://www.pychess.org/variants). Also, within a game, you can click the variant name at the top left to be taken to that game's learn page.</details>

<details><summary>How do you choose which variants to add?</summary>

Major regional variants have high precedence. For western chess variants, often the most popular or well-known variants are added. However, there are still some that can't be added. Pychess relies on Fairy-Stockfish to support the variant, as our code also depends on Fairy-Stockfish for move validation. This also means no variants that aren't supported by Fairy-Stockfish can be on Pychess.</details>

<details><summary>Can you add XXX?</summary>

It depends on how popular or how interesting the variant is. We can't even consider adding variants that aren't supported by Fairy-Stockfish. Otherwise, you can ask us on Discord or Github.</details>

## Interface

<details><summary>How do I change settings?</summary>

To change the settings, click the gear button in the top right of the screen (next to login or your username).</details>

<details><summary>How do I change pieces and boards? Are there western or internationalized pieces?</summary>

Same answer as above, and then click on "Board Settings." All Asian variants have internationalized pieces.</details>

<details><summary>How do I draw arrows and circles on the board?</summary>

Use the right click. Clicking gives you a circle, and dragging gives you an arrow. These are green by default. You can make them red by holding Shift or Ctrl, and you can make them blue by holding Alt.</details>

<details><summary>What does "5+3" mean for time?</summary>

Those are the time controls for the game. By default we use an increment system. "5+3" means each player has 5 *minutes*, and after each move adds 3 *seconds* to the clock. You can set the time control to be whatever you want when creating the game. The 5+3 is just the default for random mover.</details>

<details><summary>Okay, what about the (b) in "5+3(b)"?</summary>

The b signifies byo-yomi time control, which is different from increment, and is only used in certain variants (i.e. Shogi and Janggi). Each player has a fixed time bank (5 minutes, in this example), and then after that, they only have the byo-yomi period for the rest of their moves before losing. In this example, that means only 3 seconds per move. Typically, byo-yomi is played with more than just 3 seconds... usually anywhere from 10 seconds to 30 seconds.</details>

<details><summary>What is Random-Mover?</summary>

Random-Mover is a bot that just chooses a random move from the list of available options. It serves as a great way to familiarize oneself with piece movements and some rules. It is strongly recommended to train against Fairy-Stockfish (even a lower level) once you know the rules though.</details>

## Social/Accounts

<details><summary>How do I log in?</summary>

You need to have a Lichess account. If you don't already, please go to [Lichess](https://lichess.org/signup) to make an account.</details>

<details><summary>Would logging in with my Lichess account compromise my account/password?</summary>

No! That is done via OAuth and your password isn't revealed to Pychess, just like how you can log in to third-party websites with your Google or Facebook accounts.</details>

<details><summary>What's the best way to contact the developers?</summary>

The most reliable way is our [Discord](https://discord.gg/aPs8RKr), or you can open an issue on [GitHub](https://github.com/pychess/pychess-variants/issues).</details>

<details><summary>How is the site supported?</summary>

Purely through donations. You can [become a patron](https://www.pychess.org/patron) to help us make this site better!</details>

<details><summary>Can I contribute?</summary>

You sure can! Pychess is open source. Please communicate your suggestions by [Github](https://github.com/pychess/pychess-variants) or [Discord](https://discord.gg/aPs8RKr). </details>



