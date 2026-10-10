import { h, VNode } from 'snabbdom';

// Reusable ARIA tablist/tabpanel widget for two-board pages.
//
// The widget builds mountable vnodes and nothing else: the **tablist**, and one
// **panel** per part of per tab. It deliberately does NOT build a container
// around any of them — not around the tablist and the panels, not around one
// tab's several parts, and not around the same part index across tabs. A page
// that wants any of them inside one element renders that element itself, which
// is what lets a page put the switcher somewhere other than directly above its
// content, and put one part of a tab somewhere other than beside its siblings.
//
// A tab is a list of PARTS. Each part is one dom-tree, mounted wherever the page
// wants it, and every part of every tab is an independent mount point: three tabs
// of two parts each give six. Part counts are per tab and unrelated — one tab may
// have three parts, the next one, the next two. Nothing is derived from a maximum
// and nothing is reserved for a part that was not declared.
//
// Parts are addressed positionally, by `panel(tabIndex, partIndex)`. The caller
// declared the tabs in order and each tab's parts in order, so it can name any
// part in the same terms it used to build it. A caller may equally keep the
// vnodes it passed in and mount those instead; both work. Note the accessor
// returns the panel this module wrapped around that content, not the content
// itself — the wrapper carries the ARIA attributes and the visibility that
// switching toggles, so the wrapper is the thing to mount.
//
// That freedom is real because switching never touches the DOM: `select()`
// addresses the tab and panel vnodes this object retains, through their `.elm`.
// There is no proximity requirement between any two parts, and no selector, id
// lookup or traversal anywhere in this module. Ids exist on the elements only
// because `aria-controls` and `aria-labelledby` are id references, and no
// behaviour here reads them. A tab controls several panels once it has several
// parts, which `aria-controls` expresses natively as an id-reference list.
//
// Callers never name a tab or a panel. The constructor id is a prefix:
// `<id>-tablist` for the tablist, `<id>-tab-<i>` for a tab and
// `<id>-panel-<tab>-<part>` for a panel, so two widgets on one page cannot
// collide.
//
// SIZING IS THE PAGE'S JOB. Because there is no panel container, nothing here
// claims space or passes it on; each panel is sized by wherever it is mounted.
// The round page's stylesheet does this for its panels, and any layout that
// mounts a part somewhere new has to say what that part does there.
//
// Selection is NOT a re-render. Re-patching would be the more idiomatic snabbdom
// approach, but panels hold content this module does not own — the round page's
// movelist and game-info views retain and patch their own vnodes, and its chat
// renders into its container after insertion. Diffing those subtrees can replace
// the very elements those owners hold, leaving them patching detached nodes, so
// their content would silently stop updating. Toggling element state leaves
// every panel's subtree untouched.
//
// The consequence is that the selected tab lives in the DOM rather than in a
// model: anything that re-patches a mounted part resets it to index 0. No
// two-board page does that — each owner patches inside a panel.

export interface TabPartDef {
    panelClass?: string; // extra class on this part's panel, e.g. 'chart-container'
    content: VNode[];
    /** The `display` this part takes when it is shown. Defaults to `flex`.
     *
     * Stated because the widget has to write a value: the page stylesheet hides an unselected
     * panel, so showing one again cannot simply clear the inline style. A part whose box is not a
     * flex container — a board stack is a block — says so here rather than being bent into one.
     *
     * IT IS WRITTEN INLINE, SO IT BEATS THE PAGE STYLESHEET. Whatever the sheet says about this
     * element's `display` is dead, and silently: nothing warns, the element simply lays out as
     * something else. The analysis page's partner stack said `block`, copied from the round page,
     * against a sheet that makes that stack a two-column grid — the board's definite width lived in
     * a track that therefore never existed, and board B was drawn at whatever its column happened
     * to give it. Declare the value the SHEET wants for this element, not the one a similar part on
     * another page uses. */
    display?: string;
}

export interface TabPanelDef {
    label: string;
    parts: TabPartDef[];
    /** Detached at construction: see `setDetached`. */
    detached?: boolean;
}

export class TabbedPanels {
    // retained so select() can address the elements once the page's patch has
    // populated each vnode's .elm. Indexed [tab][part].
    private readonly panelVnodes: VNode[][];
    private readonly tabVnodes: VNode[];
    private readonly tabListVnode: VNode;
    private readonly labels: string[];
    private readonly displays: string[][];
    private readonly tabId: (t: number) => string;
    // Mutable: a page detaches and attaches as its arrangement changes.
    private readonly detached: boolean[];
    private onSelect: (() => void) | null = null;

    constructor(id: string, panels: TabPanelDef[], ariaLabel: string) {
        const tabId = (t: number) => `${id}-tab-${t}`;
        const panelId = (t: number, p: number) => `${id}-panel-${t}-${p}`;
        this.tabId = tabId;
        this.labels = panels.map(panel => panel.label);
        this.displays = panels.map(panel => panel.parts.map(part => part.display ?? 'flex'));
        this.detached = panels.map(panel => panel.detached === true);

        // The tab that starts selected: the first ATTACHED one. A detached tab is not in the
        // strip, so it cannot be what the strip is showing — and if tab 0 is the detached one,
        // selecting it would leave the strip with nothing selected and every attached part hidden.
        const first = this.detached.findIndex(d => !d);

        this.panelVnodes = panels.map((panel, t) =>
            panel.parts.map((part, p) =>
                h(
                    part.panelClass ? `div.${part.panelClass}` : 'div',
                    {
                        attrs: {
                            id: panelId(t, p),
                            ...this.roleAttrs(t),
                        },
                        // A detached part is always shown. Among the attached, the first is the
                        // default and the rest rely on the page stylesheet's `display: none` for
                        // [role=tabpanel] — which is also why a detached part, no longer carrying
                        // that role, needs its display stated rather than left to the sheet.
                        style:
                            this.detached[t] || t === first
                                ? { display: this.displays[t][p] }
                                : {},
                    },
                    part.content,
                ),
            ),
        );

        this.tabVnodes = panels.map((panel, t) =>
            h(
                'button.site-tab',
                {
                    attrs: {
                        role: 'tab',
                        'aria-selected': t === first ? 'true' : 'false',
                        // an id-reference LIST: a tab controls every one of its parts
                        'aria-controls': panel.parts.map((_part, p) => panelId(t, p)).join(' '),
                        id: tabId(t),
                        type: 'button',
                    },
                    // A DETACHED TAB IS HIDDEN, NOT OMITTED. Rendering the strip as a shorter list
                    // would renumber every tab after it, and an id is generated from a tab's index
                    // — so `aria-controls`, `aria-labelledby` and every reference a page holds
                    // would move under it. `display: none` also takes the tab out of the
                    // accessibility tree, so the strip offers exactly the attached tabs.
                    style: this.detached[t] ? { display: 'none' } : {},
                    on: { click: () => this.select(t) },
                },
                panel.label,
            ),
        );

        this.tabListVnode = h(
            'div',
            { attrs: { id: `${id}-tablist`, role: 'tablist', 'aria-label': ariaLabel } },
            this.tabVnodes,
        );
    }

    /* A DETACHED PART IS NOT A TABPANEL. Its tab is not rendered, so `role="tabpanel"` and an
       `aria-labelledby` pointing at it would both be false — the reference would dangle. It is a
       region named by the same label the tab would have carried, and becomes a tabpanel again the
       moment the tab is attached. */
    private roleAttrs(t: number): Record<string, string> {
        return this.detached[t]
            ? { role: 'region', 'aria-label': this.labels[t] }
            : { role: 'tabpanel', 'aria-labelledby': this.tabId(t) };
    }

    // The mountable parts. Both accessors return vnodes built in the constructor
    // and never build new ones: select() operates on the vnodes this object holds,
    // so handing out a fresh vnode would leave switching acting on an element that
    // was never mounted — and only sometimes, depending on how often the caller
    // asked. A page that wants no switcher simply does not mount tabList().
    tabList(): VNode {
        return this.tabListVnode;
    }

    // The panel wrapping one part, addressed as the caller declared it. Every part
    // must be mounted somewhere: one that is declared and never mounted simply
    // never appears, and its tab will look half-rendered when selected.
    panel(tabIndex: number, partIndex: number): VNode {
        return this.panelVnodes[tabIndex][partIndex];
    }

    /** Updates the visible and accessible labels without rebuilding the tab or changing selection. */
    setLabel(tabIndex: number, label: string): void {
        if (this.labels[tabIndex] === label) return;
        this.labels[tabIndex] = label;

        const tab = this.tabVnodes[tabIndex].elm as HTMLElement | undefined;
        if (tab !== undefined) tab.textContent = label;

        if (!this.detached[tabIndex]) return;
        this.panelVnodes[tabIndex].forEach(panel => {
            const el = panel.elm as HTMLElement | undefined;
            el?.setAttribute('aria-label', label);
        });
    }

    /** Detaches or attaches one tab, at any time after construction.
     *
     * DETACHED means: absent from the strip, always displayed, and not governed by which tab is
     * selected. It is how a page says "I have somewhere permanent to put this" — and attaching
     * again is how it says the room has gone. Where a part is MOUNTED never changes; this module
     * contributes no container and moves nothing. Detachment governs only the strip.
     *
     * Returns early when nothing changes, and that is semantics rather than an optimisation:
     * attaching SELECTS, and a page that recomputes its arrangement on every resize would
     * otherwise re-select this tab on every frame and take the choice away from the reader. Only a
     * transition may move the selection. */
    setDetached(tabIndex: number, detached: boolean): void {
        if (this.detached[tabIndex] === detached) return;
        this.detached[tabIndex] = detached;

        const tab = this.tabVnodes[tabIndex].elm as HTMLElement | undefined;
        if (tab !== undefined) tab.style.display = detached ? 'none' : '';

        const attrs = this.roleAttrs(tabIndex);
        this.panelVnodes[tabIndex].forEach(panel => {
            const el = panel.elm as HTMLElement | undefined;
            if (el === undefined) return;
            el.removeAttribute(detached ? 'aria-labelledby' : 'aria-label');
            for (const [name, value] of Object.entries(attrs)) el.setAttribute(name, value);
        });

        if (!detached) {
            // ATTACHING SELECTS IT, so the part already on screen stays on screen: the arrangement
            // flips and the reader sees nothing move.
            this.select(tabIndex);
            return;
        }

        // Its parts go on being shown; what has to move is the SELECTION, if this tab held it —
        // otherwise the strip is left with every attached part hidden and no tab marked.
        this.showParts(tabIndex);
        if (this.selectedIndex() !== tabIndex) return;
        const next = this.detached.findIndex(d => !d);
        if (next >= 0) this.select(next);
    }

    /** Runs after any selection change.
     *
     * Showing a panel MOVES whatever is in it without resizing it, and a page that caches an
     * element's position — chessground's bounds memo does — has to be told. A tab click is the one
     * way a part can move that no layout pass sees: nothing resizes, so no observer fires. */
    setOnSelect(fn: () => void): void {
        this.onSelect = fn;
    }

    private selectedIndex(): number {
        return this.tabVnodes.findIndex(
            tab => (tab.elm as HTMLElement | undefined)?.getAttribute('aria-selected') === 'true',
        );
    }

    private showParts(tabIndex: number): void {
        this.panelVnodes[tabIndex].forEach((panel, p) => {
            const el = panel.elm as HTMLElement | undefined;
            if (el !== undefined) el.style.display = this.displays[tabIndex][p];
        });
    }

    // Runs only after the page's patch, so every .elm exists.
    private select(index: number): void {
        this.tabVnodes.forEach((tab, t) =>
            (tab.elm as HTMLElement).setAttribute('aria-selected', t === index ? 'true' : 'false'),
        );
        // every part of every tab, wherever each one happens to be mounted — EXCEPT a detached
        // tab's, which selection does not govern. Hiding "everything but the selected one" is the
        // one line that has to know about detachment.
        this.panelVnodes.forEach((parts, t) => {
            if (this.detached[t]) return;
            parts.forEach(
                (panel, p) =>
                    ((panel.elm as HTMLElement).style.display = t === index ? this.displays[t][p] : 'none'),
            );
        });
        this.onSelect?.();
    }
}
