/* THE HEADER'S SECTION MENUS, AS DISCLOSURES.
   ------------------------------------------------------------------------------------
   Each `.topnav section` holds a `.nav-section` button and the `.drp` it names through
   `aria-controls`. The button's `aria-expanded` is the ONLY state: `site.css` reveals a menu with
   `.nav-section[aria-expanded='true'] + .drp`, so there is no class to keep in step and no way for
   what a screen reader is told to differ from what is on screen.

   WHY A BUTTON RATHER THAN THE LINK THAT USED TO BE HERE. A pointer has two gestures -- hover opens
   the menu, click follows the link -- so the menu never needed a control of its own. A screen reader
   has ONE: activation. So activation has to either navigate or toggle, and `aria-expanded` on
   something that navigates is a lie. The destination is not lost: every section's URL is also its
   submenu's first item. And a tap-only device has no hover at all, so these menus were previously
   unreachable there by anybody, sighted or not.

   `:hover` still opens the menu for pointers and does NOT touch `aria-expanded` -- see the comment
   on the rule in `site.css`. `mouseleave` closes a latched menu so a click followed by a mouse-out
   behaves the way hovering always did. */

import { registerHeaderDropdown } from './headerPanel';

const SECTION = '.topnav section';
const BUTTON = '.nav-section';

function buttons(root: ParentNode): HTMLElement[] {
    return Array.from(root.querySelectorAll<HTMLElement>(`${SECTION} > ${BUTTON}`));
}

function setOpen(button: HTMLElement, open: boolean): void {
    button.setAttribute('aria-expanded', String(open));
}

/** Wires the six section menus. Returns a teardown, as `searchBar.ts` does. */
export function initTopNavDisclosures(root: ParentNode = document): () => void {
    const all = buttons(root);
    if (all.length === 0) return () => {};

    // Click outside and Escape are the shared header dismissal's.
    all.forEach(button =>
        registerHeaderDropdown({
            root: button.parentElement!,
            button,
            isOpen: () => button.getAttribute('aria-expanded') === 'true',
            close: () => setOpen(button, false),
        }),
    );

    // ONE DELEGATED LISTENER, not one per section: opening one menu closes the others.
    const onClick = (e: Event) => {
        const target = e.target as HTMLElement | null;
        const button = target?.closest<HTMLElement>(`${SECTION} > ${BUTTON}`) ?? null;
        if (button === null) return;
        const wasOpen = button.getAttribute('aria-expanded') === 'true';
        all.forEach(b => setOpen(b, false));
        setOpen(button, !wasOpen);
    };

    const leaveHandlers = all.map(button => {
        const section = button.parentElement;
        const onLeave = () => setOpen(button, false);
        section?.addEventListener('mouseleave', onLeave);
        return () => section?.removeEventListener('mouseleave', onLeave);
    });

    document.addEventListener('click', onClick);

    return () => {
        document.removeEventListener('click', onClick);
        leaveHandlers.forEach(off => off());
    };
}
