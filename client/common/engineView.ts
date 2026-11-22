import { h, VNode, VNodeChildren } from 'snabbdom';

/** An engine line: activating it plays its first move. Not a <button>, which would break the ellipsis. */
export function pvLine(play: () => void, content: VNodeChildren): VNode {
    return h(
        'pv-san',
        {
            attrs: { role: 'button', tabindex: '0' },
            on: {
                click: play,
                keydown: (e: KeyboardEvent) => {
                    if (e.key !== 'Enter' && e.key !== ' ') return;
                    e.preventDefault();
                    play();
                },
            },
        },
        content,
    );
}

/** A line waiting for the engine. Same pv-san element as pvLine, so a focused line keeps focus. */
export function pvLinePending(): VNode {
    return h('pvline', pvLine(() => {}, h('pvline', '-')));
}
