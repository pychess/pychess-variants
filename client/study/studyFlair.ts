import { h, type VNode } from 'snabbdom';
import { _ } from '../i18n';
import { enabledVariants, splitVariantKey, VARIANTS, variantKey } from '../variants';

type Choice = { value: string; name: string };
type EmojiGroups = Record<string, [emoji: string, name: string][]>;

let emojiGroups: Promise<EmojiGroups> | undefined;

function loadEmojiGroups(): Promise<EmojiGroups> {
    return (emojiGroups ??= fetch('/static/study-flair/emoji.json')
        .then(async response => {
            if (!response.ok) throw new Error('Could not load Study flair');
            return ((await response.json()) as { groups: EmojiGroups }).groups;
        })
        .catch((error: unknown) => {
            emojiGroups = undefined;
            throw error;
        }));
}

function variantChoices(): Choice[] {
    return enabledVariants
        .flatMap(name => {
            const variant = VARIANTS[name];
            return (variant.chess960 ? [false, true] : [false]).map(chess960 => ({
                value: `variant:${variantKey(name, chess960)}`,
                name: variant.displayName(chess960),
            }));
        })
        .sort((a, b) => a.name.localeCompare(b.name));
}

function flairGlyph(value: string): { variantIcon?: string; text?: string } {
    if (value.startsWith('emoji:')) return { text: value.slice('emoji:'.length) };
    if (value.startsWith('variant:')) {
        const { base, chess960 } = splitVariantKey(value.slice('variant:'.length));
        return { variantIcon: VARIANTS[base]?.icon(chess960) };
    }
    return {};
}

export function studyFlairIcon(value: string): VNode {
    const { variantIcon, text } = flairGlyph(value);
    return h('span.study-flair-icon', { attrs: { 'data-icon': variantIcon ?? false, 'aria-hidden': 'true' } }, text);
}

function paintGlyph(element: HTMLElement, value: string): void {
    const { variantIcon, text } = flairGlyph(value);
    if (variantIcon) element.dataset.icon = variantIcon;
    else delete element.dataset.icon;
    element.textContent = text ?? '';
}

function initPicker(field: HTMLElement): void {
    const input = field.querySelector<HTMLInputElement>('input[name="flair"]')!;
    const picker = field.querySelector('details')!;
    const summary = picker.querySelector('summary')!;
    const preview = summary.querySelector<HTMLElement>('.study-flair-icon')!;
    const search = picker.querySelector<HTMLInputElement>('input[type="search"]')!;
    const category = picker.querySelector('select')!;
    const results = picker.querySelector<HTMLElement>('.study-flair-picker__choices')!;
    const status = picker.querySelector<HTMLElement>('.study-flair-picker__status')!;
    const clear = picker.querySelector<HTMLButtonElement>('.study-flair-picker__clear')!;
    const choices = new Map<string, Choice[]>([['variants', variantChoices()]]);

    function select(value: string): void {
        input.value = value;
        paintGlyph(preview, value);
        clear.disabled = !value;
        picker.open = false;
        summary.focus();
    }

    function render(): void {
        const query = search.value.trim().toLowerCase();
        const matches = query
            ? [...choices.values()].flat().filter(choice => choice.name.toLowerCase().includes(query))
            : (choices.get(category.value) ?? []);
        const buttons = matches.map(({ value, name }) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.title = name;
            button.setAttribute('aria-label', name);
            button.setAttribute('aria-pressed', String(value === input.value));
            const icon = document.createElement('span');
            icon.className = 'study-flair-icon';
            icon.setAttribute('aria-hidden', 'true');
            paintGlyph(icon, value);
            button.append(icon);
            button.addEventListener('click', () => select(value));
            return button;
        });
        results.replaceChildren(...buttons);
        results.scrollTop = 0;
        status.textContent = buttons.length ? '' : _('No matching flair');
    }

    let loaded = false;
    picker.addEventListener('toggle', async () => {
        if (!picker.open) return;
        search.focus();
        if (!loaded) {
            render();
            status.textContent = _('Loading...');
            try {
                const groups = await loadEmojiGroups();
                if (!loaded) {
                    for (const [group, entries] of Object.entries(groups)) {
                        choices.set(group, entries.map(([emoji, name]) => ({ value: `emoji:${emoji}`, name })));
                    }
                    loaded = true;
                }
            } catch {
                render();
                status.textContent = _('Could not load emoji.');
                return;
            }
        }
        render();
    });
    search.addEventListener('input', render);
    search.addEventListener('keydown', event => {
        if (event.key === 'Enter') event.preventDefault();
    });
    category.addEventListener('change', () => {
        search.value = '';
        render();
    });
    clear.addEventListener('click', () => select(''));
    picker.addEventListener('keydown', event => {
        if (event.key !== 'Escape' || !picker.open) return;
        event.preventDefault();
        event.stopPropagation();
        picker.open = false;
        summary.focus();
    });
    field.closest('dialog')?.addEventListener('close', () => (picker.open = false));
}

function emojiCategories(): Record<string, string> {
    return {
        'Smileys & Emotion': _('Smileys & Emotion'),
        'People & Body': _('People & Body'),
        'Animals & Nature': _('Animals & Nature'),
        'Food & Drink': _('Food & Drink'),
        'Travel & Places': _('Travel & Places'),
        Activities: _('Activities'),
        Objects: _('Objects'),
        Symbols: _('Symbols'),
        Flags: _('Flags'),
    };
}

export function studyFlairPicker(initial = ''): VNode {
    const variantSelected = initial.startsWith('variant:');
    return h(
        'div.study-dialog__field.study-flair-field',
        { hook: { insert: vnode => initPicker(vnode.elm as HTMLElement) } },
        [
            h('span', _('Flair')),
            h('input', { attrs: { type: 'hidden', name: 'flair', value: initial } }),
            h('details.study-flair-picker', [
                h('summary', { attrs: { 'aria-label': _('Choose flair') } }, [studyFlairIcon(initial)]),
                h('div.study-flair-picker__panel', [
                    h('input', {
                        attrs: {
                            type: 'search',
                            autocomplete: 'off',
                            placeholder: _('Search flair'),
                            'aria-label': _('Search flair'),
                        },
                    }),
                    h('select', { attrs: { 'aria-label': _('Flair category') } }, [
                        h('option', { attrs: { value: 'variants', selected: variantSelected } }, _('PyChess variants')),
                        ...Object.entries(emojiCategories()).map(([value, label], index) =>
                            h('option', { attrs: { value, selected: index === 0 && !variantSelected } }, label),
                        ),
                    ]),
                    h('div.study-flair-picker__choices'),
                    h('p.study-flair-picker__status', { attrs: { role: 'status' } }),
                    h(
                        'button.button.button-empty.study-flair-picker__clear',
                        { attrs: { type: 'button', disabled: !initial } },
                        _('Remove flair'),
                    ),
                ]),
            ]),
        ],
    );
}
