# ![Makpong](https://github.com/pychess/pychess-variants/blob/master/static/icons/makpong.svg) Makpong

![Makpong Board](https://github.com/pychess/pychess-variants/blob/master/static/images/MakrukGuide/Makruk.png?raw=true)

Makpong is a variant of Makruk (Thai chess) designed to reduce draws. It is played in Makruk single elimination tournaments in Thailand to decide a winner after a certain number of Makruk games have been drawn.

If you are not familiar with the rules of Makruk, please see that first.

## Rules

Pieces, win conditions, and other rules are the same as Makruk.

However, there is one additional rule regarding how the king moves:
* The king may not move away from check

To clarify, there are generally three ways to answer a check:
* Move the king away
* Block the check with another piece
* Capture the attacker

This means the first option, moving the king away, is *not* allowed. You can only block the check or capture the attacker.
* The king is still allowed to capture an unprotected attacker. In this case, the king isn't moving *away* from the check, so it doesn't break the rule.
* Checking the king with multiple pieces is an immediate checkmate. Moving the king to capture either of them is illegal since it involves moving *away* from the other attacker.
<iframe width="560" height="315" src="https://www.youtube.com/embed/WmMw97hp8C0" frameborder="0" allowfullscreen></iframe>
