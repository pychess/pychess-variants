import { approvedBlogImage, renderStrictBlogMarkdown } from '../client/ublogMarkdownV2';

function render(md: string): HTMLDivElement {
    const root = document.createElement('div');
    root.append(renderStrictBlogMarkdown(md));
    return root;
}

test('escapes all author iframe HTML, including same-origin proxy', () => {
    const root = render('<iframe src="/blogs/image?url=https://attacker.test/a.svg"></iframe>');
    expect(root.querySelector('iframe')).toBeNull();
    expect(root.textContent).toContain('<iframe');
});

test('generates sandboxed YouTube and Lichess study embeds from bare links', () => {
    const root = render('https://www.youtube.com/watch?v=dQw4w9WgXcQ\n\nhttps://lichess.org/study/abcdefgh');
    const frames = root.querySelectorAll('iframe');
    expect(frames).toHaveLength(2);
    expect(frames[0].getAttribute('src')).toBe('https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ');
    expect(frames[0].getAttribute('sandbox')).toContain('allow-scripts');
    expect(frames[1].getAttribute('src')).toBe('https://lichess.org/study/embed/abcdefgh');
});

test('unapproved sources become links, approved SVG sources stay direct', () => {
    const root = render('![unsafe](https://unapproved.test/foo.svg)\n\n![approved](https://i.imgur.com/x.svg)');
    expect(root.querySelectorAll('img')).toHaveLength(1);
    expect(root.querySelector('img')?.getAttribute('src')).toBe('https://i.imgur.com/x.svg');
    expect(root.querySelector('a')?.getAttribute('href')).toBe('https://unapproved.test/foo.svg');
});

test('accepts exact pychess CDN path but not other jsdelivr repos', () => {
    const good = 'https://cdn.jsdelivr.net/gh/pychess/pychess-variants@1.11.78/static/images/test.svg';
    expect(approvedBlogImage(good, window.location.origin)).toBe(good);
    expect(approvedBlogImage('https://cdn.jsdelivr.net/gh/evil/repo@1/static/images/x.svg', window.location.origin)).toBeNull();
});

test('does not render executable HTML or data URLs', () => {
    const root = render('<img src=x onerror="alert(1)">\n\n![image](data:image/svg+xml;base64,WA==)');
    expect(root.querySelector('img, script, svg, iframe, [onerror]')).toBeNull();
});

test('supports bounded numeric dimensions without author HTML', () => {
    const root = render('![diagram](/static/images/diagram.png){width=336 height=200}');
    const img = root.querySelector('img');
    expect(img?.getAttribute('width')).toBe('336');
    expect(img?.getAttribute('height')).toBe('200');
    expect(root.textContent).not.toContain('{width=');
});

test('rejects invalid dimensions and leaves markup as text', () => {
    const root = render('![diagram](/static/images/diagram.png){width=999999}');
    expect(root.querySelector('img')?.hasAttribute('width')).toBe(false);
    expect(root.textContent).toContain('{width=999999}');
});
