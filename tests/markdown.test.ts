import { execFileSync } from 'node:child_process';
import { createMarkdownRenderer } from '../markdown';

function render(markdown: string, headingIds = false): HTMLElement {
    const root = document.createElement('div');
    root.innerHTML = createMarkdownRenderer({ headingIds }).render(markdown);
    return root;
}

test('keeps links, reference links, images, line breaks, and GitHub features', () => {
    const root = render(
        '[Inline](https://example.org/path "Title") and [Reference][ref]\n' +
            'https://example.org www.example.org @gbtami :smile: ~~gone~~\n\n' +
            '![Piece](/static/images/piece.png)\n\n' +
            '- [x] Done\n- [ ] Todo\n\n' +
            '| Header | Other |\n| --- | --- |\n| Safe | Content |\n\n' +
            '[ref]: /variants "Reference title"',
    );
    expect(Array.from(root.querySelectorAll('a'), link => link.getAttribute('href'))).toEqual([
        'https://example.org/path',
        '/variants',
        'https://example.org',
        'http://www.example.org',
        'https://github.com/gbtami',
    ]);
    expect(root.querySelector('a')?.getAttribute('title')).toBe('Title');
    expect(root.querySelector('br')).not.toBeNull();
    expect(root.textContent).toContain('😄');
    expect(root.querySelector('del')?.textContent).toBe('gone');
    expect(root.querySelector('img')?.getAttribute('src')).toBe('/static/images/piece.png');
    const tasks = root.querySelectorAll<HTMLInputElement>('input[type="checkbox"]');
    expect(tasks).toHaveLength(2);
    expect(tasks[0].checked).toBe(true);
    expect(tasks[1].checked).toBe(false);
    expect(tasks[0].disabled).toBe(true);
    expect(root.querySelectorAll('th')).toHaveLength(2);
    expect(root.querySelector('th[id]')).toBeNull();
});

test('keeps documentation heading anchors and resets duplicate counts per document', () => {
    const markdown = '# Rules & Pieces!\n\n## Rules & Pieces!\n\n## 棋子價值';
    const renderer = createMarkdownRenderer({ headingIds: true });
    for (let i = 0; i < 2; i++) {
        const root = document.createElement('div');
        root.innerHTML = renderer.render(markdown);
        expect(Array.from(root.querySelectorAll('h1, h2'), heading => heading.id)).toEqual([
            'rules--pieces',
            'rules--pieces-1',
            '棋子價值',
        ]);
    }
});

test('renders the ReDoS payload within a subprocess timeout and preserves its text', () => {
    // A child process bounds the test even if a vulnerable parser is reintroduced.
    const output = execFileSync(
        process.execPath,
        [
            '-e',
            'const { createMarkdownRenderer } = require("./markdown");' +
                'process.stdout.write(createMarkdownRenderer().render("[".repeat(90000)));',
        ],
        { timeout: 3000, encoding: 'utf8' },
    );
    const root = document.createElement('div');
    root.innerHTML = output;
    expect(root.textContent?.trim()).toBe('['.repeat(90000));
});
