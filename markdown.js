const MarkdownIt = require('markdown-it');
const { full: emoji } = require('markdown-it-emoji');
const taskLists = require('markdown-it-task-lists');

function createMarkdownRenderer({ headingIds = false, html = true } = {}) {
    // Raw HTML supports existing embeds and documentation diagrams. Sanitize
    // untrusted output before inserting it into the DOM (see ublogMarkdown.ts).
    const md = new MarkdownIt({ html, breaks: true, linkify: true }).use(emoji, { shortcuts: {} }).use(taskLists);
    md.linkify.set({ fuzzyLink: true, fuzzyEmail: true });
    md.renderer.rules.s_open = () => '<del>';
    md.renderer.rules.s_close = () => '</del>';

    md.inline.ruler.before('link', 'github_mentions', (state, silent) => {
        if (state.src[state.pos] !== '@' || state.linkLevel > 0) return false;
        if (state.pos > 0 && !/\s/.test(state.src[state.pos - 1])) return false;
        // GitHub usernames are at most 39 characters. Bound the match length.
        const match = /^@([a-z\d](?:[a-z\d._-]{0,37}[a-z\d])?)/i.exec(state.src.slice(state.pos));
        if (!match) return false;
        if (!silent) {
            const link = state.push('link_open', 'a', 1);
            link.attrSet('href', `https://github.com/${match[1]}`);
            state.push('text', '', 0).content = match[0];
            state.push('link_close', 'a', -1);
        }
        state.pos += match[0].length;
        return true;
    });

    if (headingIds) {
        md.core.ruler.push('heading_ids', state => {
            const counts = new Map();
            state.tokens.forEach((token, index) => {
                if (token.type !== 'heading_open') return;
                // Keep existing documentation anchors, including duplicate suffixes.
                const slug = state.tokens[index + 1].content
                    .replace(/ /g, '-')
                    .replace(/&amp;/g, '')
                    .replace(/[&+$,/:;=?@"#{}|^~[\]`\\*)(%.!'<>]/g, '')
                    .toLowerCase();
                const count = counts.get(slug) || 0;
                counts.set(slug, count + 1);
                token.attrSet('id', count ? `${slug}-${count}` : slug);
            });
        });
    }

    return md;
}

module.exports = { createMarkdownRenderer };
