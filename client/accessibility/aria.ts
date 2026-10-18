import { VNodeData } from 'snabbdom';

/** Hides decoration, such as an icon-font glyph, from screen readers; the control's title names it. */
export function ariaHiddenAttr(): VNodeData {
    return { attrs: { 'aria-hidden': 'true' } };
}
