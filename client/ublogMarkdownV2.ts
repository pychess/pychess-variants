/** Strict blog Markdown renderer for ublog_post2. */
import DOMPurify from 'dompurify';
import { createMarkdownRenderer } from '../markdown';

const markdown = createMarkdownRenderer({ html: false });
// Lichess MarkdownRender.WhitelistedImage (plus our versioned CDN below).
const IMAGE_HOSTS = [
    'imgur.com', 'giphy.com', 'wikimedia.org', 'creativecommons.org',
    'pexels.com', 'piqsels.com', 'freeimages.com', 'unsplash.com',
    'pixabay.com', 'githubusercontent.com', 'googleusercontent.com',
    'i.postimg.cc', 'imgs.xkcd.com', 'image.lichess1.org',
    'image.lichess.org', 'pic.lichess.org',
];

function trustedImageHost(host: string): boolean {
    return IMAGE_HOSTS.some(allowed => host === allowed || host.endsWith(`.${allowed}`));
}

const CDN_PATH = /^\/gh\/pychess\/pychess-variants@[^/]+\/static\/(?:images|docs|icons)\//;
const STATIC_PATH = /^\/static\/(?:images|docs|icons)\//;

export function approvedBlogImage(src: string, origin: string): string | null {
    try {
        const url = new URL(src, origin);
        if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) return null;
        const local = url.origin === origin;
        if (local && STATIC_PATH.test(url.pathname)) return `${url.pathname}${url.search}${url.hash}`;
        if (url.protocol !== 'https:') return null;
        if (url.hostname === 'cdn.jsdelivr.net' && CDN_PATH.test(url.pathname)) return url.href;
        if (trustedImageHost(url.hostname)) return url.href;
        return null;
    } catch {
        return null;
    }
}

function embedInfo(src: string): { src: string; youtube: boolean } | null {
    try {
        const url = new URL(src);
        if (url.protocol !== 'https:' || url.username || url.password) return null;
        const host = url.hostname.toLowerCase();
        if (host === 'youtu.be' || host === 'youtube.com' || host === 'www.youtube.com' || host === 'www.youtube-nocookie.com') {
            let id = '';
            if (host === 'youtu.be') id = url.pathname.slice(1);
            else if (url.pathname === '/watch') id = url.searchParams.get('v') || '';
            else if (url.pathname.startsWith('/embed/')) id = url.pathname.slice(7);
            if (!/^[\w-]{11}$/.test(id)) return null;
            return { src: `https://www.youtube-nocookie.com/embed/${id}`, youtube: true };
        }
        if ((host === 'lichess.org' || host === 'www.lichess.org') && /^\/study\/(?:embed\/)?[A-Za-z0-9]{8}(?:\/[A-Za-z0-9]{8})?\/?$/.test(url.pathname)) {
            return { src: `https://lichess.org/study/embed/${url.pathname.replace(/^\/study\/(?:embed\/)?/, '').replace(/\/$/, '')}`, youtube: false };
        }
        return null;
    } catch {
        return null;
    }
}

function makeEmbed(doc: Document, info: { src: string; youtube: boolean }): HTMLIFrameElement {
    const iframe = doc.createElement('iframe');
    iframe.setAttribute('src', info.src);
    iframe.setAttribute('width', '560');
    iframe.setAttribute('height', '315');
    iframe.setAttribute('loading', 'lazy');
    iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-presentation');
    iframe.setAttribute('referrerpolicy', info.youtube ? 'strict-origin-when-cross-origin' : 'no-referrer');
    iframe.setAttribute('allowfullscreen', '');
    iframe.setAttribute('title', info.youtube ? 'YouTube video' : 'Lichess study');
    return iframe;
}

export function renderStrictBlogMarkdown(source: string): DocumentFragment {
    // Raw author HTML is escaped by markdown-it; sanitize generated markup as an additional boundary.
    const fragment = DOMPurify.sanitize(markdown.render(source || ''), {
        ALLOWED_TAGS: [
            'a', 'p', 'blockquote', 'pre', 'code', 'ul', 'ol', 'li', 'hr', 'br',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'em', 'del',
            'table', 'thead', 'tbody', 'tr', 'th', 'td', 'img', 'input', 'span',
        ],
        ALLOWED_ATTR: ['href', 'title', 'src', 'alt', 'class', 'type', 'checked', 'disabled', 'width', 'height'],
        FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed', 'svg'],
        RETURN_DOM_FRAGMENT: true,
    }) as DocumentFragment;

    fragment.querySelectorAll<HTMLImageElement>('img').forEach(img => {
        // Trusted, numeric Markdown dimension extension: ![alt](url){width=336 height=336}.
        // Apply only to image-adjacent text. Never turn user content into HTML.
        const suffix = img.nextSibling;
        if (suffix?.nodeType === Node.TEXT_NODE) {
            const raw = suffix.textContent || '';
            const match = /^\{((?:width|height)=\d+(?:\s+(?:width|height)=\d+)?)\}/.exec(raw);
            if (match) {
                const values = new Map(match[1].split(/\s+/).map(pair => pair.split('=') as [string, string]));
                const valid = [...values.values()].every(value => Number(value) > 0 && Number(value) <= 2048);
                if (valid && values.size === match[1].split(/\s+/).length) {
                    values.forEach((value, key) => img.setAttribute(key, value));
                    suffix.textContent = raw.slice(match[0].length);
                }
            }
        }
        const original = img.getAttribute('src') || '';
        const approved = approvedBlogImage(original, window.location.origin);
        if (!approved) {
            const link = document.createElement('a');
            // Disallowed URLs are not made clickable if they use dangerous schemes.
            try {
                const url = new URL(original, window.location.origin);
                if (url.protocol === 'http:' || url.protocol === 'https:') {
                    link.href = url.href;
                    link.textContent = img.getAttribute('alt') || url.href;
                    link.rel = 'nofollow noopener noreferrer';
                    link.target = '_blank';
                    img.replaceWith(link);
                    return;
                }
            } catch { /* fall through to plain text */ }
            img.replaceWith(document.createTextNode(img.getAttribute('alt') || 'Image'));
            return;
        }
        img.setAttribute('src', approved);
        img.setAttribute('loading', 'lazy');
    });

    fragment.querySelectorAll<HTMLAnchorElement>('a').forEach(anchor => {
        const original = anchor.getAttribute('href') || '';
        let parsed: URL;
        try { parsed = new URL(original, window.location.origin); } catch { anchor.removeAttribute('href'); return; }
        if (!['https:', 'http:'].includes(parsed.protocol) && !original.startsWith('/')) {
            anchor.removeAttribute('href');
            return;
        }
        anchor.setAttribute('rel', 'nofollow noopener noreferrer');
        anchor.setAttribute('target', '_blank');
    });

    // Only a bare linked URL in its own paragraph becomes a trusted, generated embed.
    fragment.querySelectorAll<HTMLParagraphElement>('p').forEach(paragraph => {
        if (paragraph.children.length !== 1) return;
        const link = paragraph.firstElementChild;
        if (!link || link.tagName !== 'A' || link.textContent?.trim() !== link.getAttribute('href')) return;
        const info = embedInfo(link.getAttribute('href') || '');
        if (info) paragraph.replaceWith(makeEmbed(document, info));
    });
    return fragment;
}

export function initUblogMarkdownV2(): void {
    const source = document.getElementById('ublog-markdown-source') as HTMLTextAreaElement | null;
    const render = document.getElementById('ublog-markdown-render');
    if (source && render) render.replaceChildren(renderStrictBlogMarkdown(source.value || ''));
}
