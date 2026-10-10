import { h, VNode } from 'snabbdom';
import { Api } from 'chessgroundx/api';
import { Chessground } from 'chessgroundx';
import * as cg from 'chessgroundx/types';

import { _ } from './i18n';
import { patch } from './document';
import { alertDialog } from './alertDialog';
import { timeago } from './datetime';
import { PyChessModel } from './types';
import { expandGameEmbeds, makeExternalLinkPopups, renderRichText } from './richTextEnhance';
import { boardSettings } from './boardSettings';
import { VARIANTS } from './variants';
import { isSameDocumentForumRedirect } from './forumNavigation';

/** Supported forum UI modes mapped from URL paths. */
type ForumMode = 'index' | 'categ' | 'topic' | 'newTopic' | 'search' | 'modFeed';

/** Category row payload used by forum index and topic-category headers. */
interface ForumCategory {
    _id: string;
    name: string;
    desc: string;
    teamId?: string;
    nbTopics: number;
    nbPosts: number;
    lastPostAt?: string | null;
    lastPostUser?: string;
    lastTopicSlug?: string;
    lastTopicName?: string;
    lastTopicPage?: number;
    lastPostId?: string;
}

/** Topic summary payload used by category listings and topic header state. */
interface ForumTopicSummary {
    _id: string;
    categId: string;
    slug: string;
    name: string;
    user: string;
    userTitle?: string;
    createdAt: string;
    updatedAt: string;
    nbPosts: number;
    nbReplies: number;
    lastPostAt: string;
    lastPostUser: string;
    lastPostUserTitle?: string;
    lastPostId: string;
    sticky?: boolean;
    closed?: boolean;
    lastPage?: number;
    blogPostId?: string;
    blogPostUrl?: string;
}

/** Post payload used by topic, search, and moderation feed views. */
interface ForumPost {
    _id: string;
    topicId: string;
    categId: string;
    user: string;
    userTitle?: string;
    text: string;
    createdAt: string;
    updatedAt?: string | null;
    erasedAt?: string | null;
    erased?: boolean;
    canEdit?: boolean;
    canDelete?: boolean;
    canReact?: boolean;
    reactionCounts?: Record<string, number>;
    myReactions?: string[];
}

/** Search result row combining post data with owning topic and category labels. */
interface ForumSearchResult {
    post: ForumPost;
    postUserTitle?: string;
    topic: {
        _id: string;
        slug: string;
        name: string;
        blogPostId?: string;
        blogPostUrl?: string;
    };
    categ: {
        _id: string;
        name: string;
    };
}

/** Moderation feed row containing one post and its topic info. */
interface ForumModFeedItem {
    post: ForumPost;
    topic: {
        _id: string;
        slug: string;
        name: string;
        blogPostId?: string;
        blogPostUrl?: string;
    };
}

/** Client-side reaction descriptor mapped to emoji assets and API keys. */
interface ForumReaction {
    key: string;
    emoji: string;
    icon?: string;
}

/** Captcha payload returned by forum captcha API endpoints. */
interface ForumCaptcha {
    gameId: string;
    variant?: string;
    fen: string;
    color: 'white' | 'black';
    moves: Record<string, string>;
    helpUrl?: string;
}

/** Captcha validation state mirrored in form UX feedback. */
type ForumCaptchaState = 'idle' | 'checking' | 'success' | 'failure';

/** Maximum accepted post length enforced by both UI and backend API. */
const FORUM_MAX_POST_LEN = 5000;
/** Maximum accepted topic-title length enforced by both UI and backend API. */
const FORUM_MAX_TOPIC_NAME_LEN = 100;
const ERASED_POST_USER = '<erased>';
const ERASED_POST_TEXT = '<Comment deleted by user>';

const DEFAULT_FORUM_CATEGORY_TRANSLATIONS: Record<string, { name: string; desc: string }> = {
    'general-chess-discussion': {
        name: _('General Variant Discussion'),
        desc: _('Discuss variants, and strategy.'),
    },
    'pychess-feedback': {
        name: _('Pychess Feedback'),
        desc: _('Feedback and feature requests about the site.'),
    },
    'game-analysis': {
        name: _('Game Analysis'),
        desc: _('Share and discuss your games.'),
    },
    'off-topic-discussion': {
        name: _('Off-Topic Discussion'),
        desc: _("Everything that isn't related to Pychess."),
    },
    'community-blog-discussions': {
        name: _('Community Blog Discussions'),
        desc: _('Discuss community blog posts.'),
    },
};

function translateForumCategory(category: ForumCategory | null): ForumCategory | null {
    if (!category || category.teamId) return category;
    const translated = DEFAULT_FORUM_CATEGORY_TRANSLATIONS[category._id];
    return translated ? { ...category, ...translated } : category;
}

function forumCategoryName(categoryId: string, fallback: string): string {
    return DEFAULT_FORUM_CATEGORY_TRANSLATIONS[categoryId]?.name || fallback;
}

function forumTopicName(topic: { name: string; blogPostId?: string }): string {
    if (topic.blogPostId && topic.name.startsWith('Comments on ')) {
        return _('Comments on %1', topic.name.slice('Comments on '.length));
    }
    return topic.name;
}

interface ForumApiError {
    type?: string;
    code?: string;
    message?: string;
}

function forumApiErrorMessage(data: ForumApiError, status: number): string {
    switch (data.code) {
        case 'forum_unavailable': return _('Forum unavailable');
        case 'invalid_category': return _('Invalid category');
        case 'category_not_found': return _('Category not found');
        case 'not_allowed': return _('Not allowed');
        case 'invalid_topic': return _('Invalid topic');
        case 'invalid_topic_id': return _('Invalid topic id');
        case 'topic_not_found': return _('Topic not found');
        case 'search_text_too_long': return _('Search text too long');
        case 'login_required': return _('Login required');
        case 'cannot_post': return _('You cannot post in this forum');
        case 'invalid_request': return _('Invalid request');
        case 'topic_title_too_short': return _('Topic title is too short');
        case 'topic_title_too_long': return _('Topic title is too long');
        case 'message_too_short': return _('Message is too short');
        case 'message_too_long': return _('Message too long (max %1)', FORUM_MAX_POST_LEN);
        case 'captcha_required': return _('Please solve the captcha.');
        case 'too_many_similar_messages': return _('Too many similar messages. Please wait and retry.');
        case 'topic_closed': return _('This topic is closed');
        case 'post_not_found': return _('Post not found');
        case 'post_edit_expired': return _('Post can no longer be edited');
        case 'invalid_reaction': return _('Invalid reaction');
        case 'cannot_react_deleted_post': return _('Cannot react to deleted posts');
        case 'cannot_react_own_post': return _('Cannot react to your own post');
        case 'team_topic_relocation_forbidden': return _('Team forum topics cannot be relocated');
        case 'first_post_required': return _('Only the first post can relocate a thread');
        case 'invalid_target_category': return _('Invalid target category');
        case 'already_in_category': return _('Already in that category');
        case 'target_category_not_found': return _('Target category not found');
        default: return data.message || data.type || `HTTP ${status}`;
    }
}
/** Supported forum reactions mirrored from the server and lila conventions. */
const REACTIONS: ForumReaction[] = [
    { key: '+1', emoji: '+1' },
    { key: '-1', emoji: '-1' },
    { key: 'laugh', emoji: 'laugh' },
    { key: 'thinking', emoji: 'thinking' },
    { key: 'heart', emoji: 'heart' },
    { key: 'elephant', emoji: 'elephant', icon: '/icons/Shatranj.svg' },
];

/** Parse current path into the forum mode/categ/slug route state. */
function parsePath(pathname: string): { mode: ForumMode; categ?: string; slug?: string } {
    const clean = pathname.replace(/\/+$/g, '');
    const parts = clean.split('/').filter(Boolean);
    if (parts.length === 1 && parts[0] === 'forum') return { mode: 'index' };
    if (parts.length >= 2 && parts[0] === 'forum' && parts[1] === 'search') return { mode: 'search' };
    if (parts.length >= 3 && parts[0] === 'forum' && parts[2] === 'mod-feed') {
        return { mode: 'modFeed', categ: parts[1] };
    }
    if (parts.length >= 3 && parts[0] === 'forum' && parts[2] === 'form') {
        return { mode: 'newTopic', categ: parts[1] };
    }
    if (parts.length >= 3 && parts[0] === 'forum') return { mode: 'topic', categ: parts[1], slug: parts[2] };
    if (parts.length >= 2 && parts[0] === 'forum') return { mode: 'categ', categ: parts[1] };
    return { mode: 'index' };
}

/** Decode JSON responses and surface useful errors for malformed payloads. */
async function parseJsonResponse(res: Response) {
    const text = await res.text();
    if (text.length === 0) return { status: res.status, data: {} as any };
    try {
        return { status: res.status, data: JSON.parse(text) };
    } catch {
        throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
    }
}

/** Compose a human-readable name with optional title prefix (e.g. GM user). */
function titleAndName(title: string | undefined, name: string): string {
    return title ? `${title} ${name}` : name;
}

function isErasedPost(post: ForumPost): boolean {
    return Boolean(post.erased) || Boolean(post.erasedAt) || post.user === ERASED_POST_USER;
}

/** Apply rich-content enhancers reused from inbox message rendering flow. */
function renderForumQuoteLinks(html: string): string {
    return html.replace(
        /\[\^\]\((\/forum\/redirect\/post\/[A-Za-z0-9_%.-]+)\)/g,
        (_match, href: string) => `<a class="text" href="${href}">^</a>`,
    );
}

function renderForumBlockquotes(html: string): string {
    if (!html.match(/(^|<br>)&gt;/)) return html;

    const hiddenQuotes = '<span class="hidden-quotes">&gt;</span>';
    let result = '';
    let quote: string[] = [];
    for (const line of html.split('<br>')) {
        if (line.startsWith('&gt;')) quote.push(hiddenQuotes + line.substring(4).trim());
        else {
            if (quote.length > 0) {
                result += `<blockquote>${quote.join('<br>')}</blockquote>`;
                quote = [];
            }
            result += line + '<br>';
        }
    }
    if (quote.length > 0) result += `<blockquote>${quote.join('<br>')}</blockquote>`;
    return result;
}

function enhanceForumPostMessage(el: HTMLElement) {
    el.innerHTML = renderForumBlockquotes(renderForumQuoteLinks(el.innerHTML));
    expandGameEmbeds(el, {
        linkSelector: 'a:not(.text)',
        expandLinkClass: 'forum-post-game-expand',
        embedContainerClass: 'forum-post-game-embed',
    });
    makeExternalLinkPopups(el, { selector: "a[href^='http']" });
    window.requestAnimationFrame(() => expandGameEmbeds(el));
}

/** Read a query-string parameter from the current location. */
function searchParam(name: string): string {
    const value = new URLSearchParams(window.location.search).get(name);
    return value ? value : '';
}

/** Parse and validate the current `page` query parameter. */
function pageParam(): number {
    const page = parseInt(searchParam('page'), 10);
    return Number.isFinite(page) && page > 0 ? page : 1;
}

/** Shorten long text snippets for tabular preview rows. */
function shorten(text: string, len: number): string {
    if (text.length <= len) return text;
    return `${text.slice(0, len - 1)}…`;
}

/** Build canonical post redirect URLs that preserve page and anchor resolution. */
function postRedirectHref(postId: string): string {
    return `/forum/redirect/post/${encodeURIComponent(postId)}`;
}

/** Build report-form URL prefilled for a specific forum post and author. */
function reportPostHref(post: ForumPost): string {
    const postUrl = `${window.location.origin}${postRedirectHref(post._id)}`;
    const params = new URLSearchParams({
        source: 'profile',
        username: post.user,
        reason: 'harass',
        url: postUrl,
        details: `${_('Forum post')}: ${postUrl}`,
    });
    return `/report?${params.toString()}`;
}

/** Forum SPA entry point for index/category/topic/search/mod-feed rendering and actions. */
export function forumView(model: PyChessModel) {
    boardSettings.assetURL = model.assetURL;
    const route = parsePath(window.location.pathname);
    const mode = route.mode;
    const categ = route.categ || '';
    const slug = route.slug || '';
    let appEl: HTMLElement | VNode;
    let loading = true;
    let error = '';

    let categories: ForumCategory[] = [];
    let topics: ForumTopicSummary[] = [];
    let topicPosts: ForumPost[] = [];
    let searchPosts: ForumSearchResult[] = [];
    let modFeedItems: ForumModFeedItem[] = [];

    let page = pageParam();
    let nbPages = 1;
    let total = 0;

    let categData: ForumCategory | null = null;
    let topicData: ForumTopicSummary | null = null;
    let canWrite = false;
    let canModerate = false;
    let canReply = false;
    let canClose = false;
    let canSticky = false;
    let timelineUnsubscribed: boolean | null = null;
    let updatingTimelineSubscription = false;

    let relocateTargets: ForumCategory[] = [];

    let composeReply = '';
    let sendingReply = false;
    let creatingTopic = false;
    let topicTitleDraft = '';
    let topicTextDraft = '';
    let searchTextDraft = searchParam('text');
    let showRelocateModal = false;
    let relocateTargetDraft = '';
    let showDeleteModal = false;
    let deletePostDraftId = '';
    let formCaptcha: ForumCaptcha | null = null;
    let loadingCaptcha = false;
    let captchaMoveDraft = '';
    let captchaState: ForumCaptchaState = 'idle';
    let captchaError = '';
    let formSubmitError = '';

    const reactingPostIds = new Set<string>();
    const expandedReactionPostIds = new Set<string>();
    const editDraftByPostId = new Map<string, string>();
    const savingEditPostIds = new Set<string>();
    const quotedReplies = new Set<string>();

    /** Re-render the forum vnode tree after state changes. */
    function redraw() {
        appEl = patch(appEl, render());
    }

    /** Convert API errors into thrown exceptions for shared catch handling. */
    function handleApiError(data: ForumApiError, status: number) {
        throw new Error(forumApiErrorMessage(data, status));
    }

    /** Parse compact captcha destination encoding into chessground destination map. */
    function parseCaptchaDests(moves: Record<string, string>): cg.Dests {
        const squarePattern = /[a-z][0-9]+/g;
        const dests: cg.Dests = new Map();
        Object.entries(moves || {}).forEach(([orig, raw]) => {
            if (!orig || !raw) return;
            const cleaned = raw.replace(/\s+/g, '');
            if (!/^[a-z][0-9]+$/i.test(orig)) return;
            const squares = cleaned.match(squarePattern) || [];
            const validSquares = squares as cg.Key[];
            if (validSquares.length > 0) dests.set(orig as cg.Key, validSquares);
        });
        return dests;
    }

    function captchaVariantKey(captcha: ForumCaptcha): string {
        const key = (captcha.variant || '').toLowerCase();
        return key && VARIANTS[key] ? key : 'chess';
    }

    function captchaVariantLabel(variantKey: string): string {
        const variant = VARIANTS[variantKey];
        const rawName = (variant?._displayName || variant?.name || 'chess').trim();
        return rawName ? rawName.charAt(0).toUpperCase() + rawName.slice(1) : _('Chess');
    }

    /** Reset captcha interaction state while preserving loaded challenge payload. */
    function resetCaptchaState() {
        captchaMoveDraft = '';
        captchaState = 'idle';
        captchaError = '';
    }

    /** Replace active form captcha challenge and reset move/result state. */
    function setFormCaptcha(captcha: ForumCaptcha | null) {
        formCaptcha = captcha;
        resetCaptchaState();
        formSubmitError = '';
    }

    /** Fetch a new forum captcha challenge payload for post forms. */
    function loadCaptcha() {
        if (loadingCaptcha) return;
        loadingCaptcha = true;
        captchaError = '';
        redraw();
        fetch('/api/forum/captcha')
            .then(parseJsonResponse)
            .then(({ status, data }) => {
                loadingCaptcha = false;
                if (status >= 400 || data.type === 'error') handleApiError(data, status);
                setFormCaptcha((data.captcha || null) as ForumCaptcha | null);
                redraw();
            })
            .catch(err => {
                loadingCaptcha = false;
                setFormCaptcha(null);
                captchaError = err instanceof Error ? err.message : _('Could not load captcha.');
                redraw();
            });
    }

    /** Verify the selected captcha move with server API and update status classes. */
    function checkCaptchaMove(solution: string, board: Api, fen: string, color: cg.Color, dests: cg.Dests) {
        if (!formCaptcha) return;
        captchaState = 'checking';
        captchaMoveDraft = solution;
        redraw();
        fetch(
            `/api/forum/captcha/${encodeURIComponent(formCaptcha.gameId)}/check?solution=${encodeURIComponent(solution)}`,
        )
            .then(res => res.text())
            .then(text => {
                if (text.trim() === '1') {
                    captchaState = 'success';
                    formSubmitError = '';
                    board.stop();
                } else {
                    captchaState = 'failure';
                    captchaMoveDraft = '';
                    window.setTimeout(() => {
                        board.set({
                            fen,
                            turnColor: color,
                            movable: {
                                color,
                                free: false,
                                dests,
                            },
                        });
                    }, 280);
                }
                redraw();
            })
            .catch(() => {
                captchaState = 'failure';
                captchaMoveDraft = '';
                redraw();
            });
    }

    /** Render captcha widget used by topic creation and reply forms. */
    function renderCaptcha() {
        if (loadingCaptcha) return h('div.forum-captcha-loading', _('Loading captcha...'));
        if (captchaError) {
            return h('div.forum-captcha-error', [
                h('span', captchaError),
                h(
                    'button.button.button-empty.text',
                    {
                        props: { type: 'button' },
                        on: {
                            click: () => loadCaptcha(),
                        },
                    },
                    _('Retry'),
                ),
            ]);
        }
        if (!formCaptcha) {
            return h('div.forum-captcha-error', _('Captcha unavailable. Please retry.'));
        }

        const variantKey = captchaVariantKey(formCaptcha);
        const captchaVariant = VARIANTS[variantKey];
        const variantLabel = captchaVariantLabel(variantKey);
        const color = formCaptcha.color === 'black' ? 'black' : 'white';
        const sideLabel = _(color === 'white' ? captchaVariant.colors.first : captchaVariant.colors.second);
        const dests = parseCaptchaDests(formCaptcha.moves);
        return h(
            'div.forum-captcha',
            {
                key: `captcha-${formCaptcha.gameId}`,
                class: {
                    success: captchaState === 'success',
                    failure: captchaState === 'failure',
                },
            },
            [
                h('div.forum-captcha__challenge', [
                    h(
                        `selection.forum-captcha-board.${captchaVariant.boardFamily}.${captchaVariant.pieceFamily}.${captchaVariant.ui.boardMark}`,
                        [
                            h(`div.cg-wrap.${captchaVariant.board.cg}.mini`, {
                                hook: {
                                    insert(vnode) {
                                        boardSettings.updateScopedBoardStyle(captchaVariant, vnode.elm as Element);
                                        boardSettings.updateScopedPieceStyle(captchaVariant, vnode.elm as Element);
                                        const board = Chessground(vnode.elm as HTMLElement, {
                                            fen: formCaptcha!.fen as cg.FEN,
                                            dimensions: captchaVariant.board.dimensions,
                                            notation: captchaVariant.notation,
                                            pocketRoles: captchaVariant.pocket?.roles,
                                            orientation: color,
                                            turnColor: color,
                                            coordinates: false,
                                            viewOnly: false,
                                            movable: {
                                                free: false,
                                                color,
                                                dests,
                                                events: {
                                                    after(orig: cg.Key, dest: cg.Key) {
                                                        checkCaptchaMove(
                                                            `${orig} ${dest}`,
                                                            board,
                                                            formCaptcha!.fen,
                                                            color,
                                                            dests,
                                                        );
                                                    },
                                                },
                                            },
                                        });
                                    },
                                    update(_oldVnode, vnode) {
                                        boardSettings.updateScopedBoardStyle(captchaVariant, vnode.elm as Element);
                                        boardSettings.updateScopedPieceStyle(captchaVariant, vnode.elm as Element);
                                    },
                                },
                            }),
                        ],
                    ),
                ]),
                h('div.forum-captcha__explanation', [
                    h('label.form-label', _('%1 to checkmate in one move', sideLabel)),
                    h('p', _('This is a %1 CAPTCHA.', variantLabel)),
                    h('p', _('Click on the board to make your move, and prove you are human.')),
                    formCaptcha.helpUrl
                        ? h('p.forum-captcha__help', [
                              `${_('Help')}: `,
                              h(
                                  'a',
                                  {
                                      attrs: {
                                          href: formCaptcha.helpUrl,
                                          target: '_blank',
                                          rel: 'noopener',
                                      },
                                  },
                                  formCaptcha.helpUrl,
                              ),
                          ])
                        : null,
                    h(
                        'div.forum-captcha__result.success',
                        {
                            class: { visible: captchaState === 'success' },
                        },
                        _('Checkmate.'),
                    ),
                    h(
                        'div.forum-captcha__result.failure',
                        {
                            class: { visible: captchaState === 'failure' },
                        },
                        _('Not a checkmate. Try again.'),
                    ),
                ]),
            ],
        );
    }

    /** Render simple previous/next pager links for list and topic pages. */
    function renderPagination(baseUrl: string) {
        if (nbPages <= 1) return null;
        const prevPage = page > 1 ? page - 1 : 1;
        const nextPage = page < nbPages ? page + 1 : nbPages;
        const sep = baseUrl.includes('?') ? '&' : '?';
        return h('nav.pagination.forum-pagination', [
            h(
                `a.button.button-empty${page <= 1 ? '.disabled' : ''}`,
                {
                    attrs: { href: page <= 1 ? '#' : `${baseUrl}${sep}page=${prevPage}` },
                },
                _('Previous'),
            ),
            h('span.forum-pagination-current', `${page} / ${nbPages}`),
            h(
                `a.button.button-empty${page >= nbPages ? '.disabled' : ''}`,
                {
                    attrs: { href: page >= nbPages ? '#' : `${baseUrl}${sep}page=${nextPage}` },
                },
                _('Next'),
            ),
        ]);
    }

    /** Load forum home categories and counters. */
    function loadIndex() {
        fetch('/api/forum/categs')
            .then(parseJsonResponse)
            .then(({ status, data }) => {
                if (status >= 400 || data.type === 'error') handleApiError(data, status);
                categories = (data.categs || []).map((category: ForumCategory) => translateForumCategory(category) as ForumCategory);
                loading = false;
                redraw();
            })
            .catch(err => {
                console.warn('Failed to load forum categories.', err);
                error = _('Could not load forum categories.');
                loading = false;
                redraw();
            });
    }

    /** Load one category with topic listing and permission flags. */
    function loadCateg() {
        fetch(`/api/forum/${encodeURIComponent(categ)}/topics?page=${page}`)
            .then(parseJsonResponse)
            .then(({ status, data }) => {
                if (status >= 400 || data.type === 'error') handleApiError(data, status);
                categData = translateForumCategory(data.categ || null);
                topics = data.topics || [];
                page = data.page || 1;
                nbPages = data.nbPages || 1;
                total = data.total || 0;
                canWrite = Boolean(data.canWrite);
                canModerate = Boolean(data.canModerate);
                setFormCaptcha((data.captcha || null) as ForumCaptcha | null);
                loading = false;
                redraw();
            })
            .catch(err => {
                console.warn('Failed to load forum category.', err);
                error = _('Could not load forum category.');
                loading = false;
                redraw();
            });
    }

    /** Load one topic page including posts, reactions, and moderation metadata. */
    function loadTopic(afterLoad?: () => void) {
        fetch(`/api/forum/${encodeURIComponent(categ)}/${encodeURIComponent(slug)}?page=${page}`)
            .then(parseJsonResponse)
            .then(({ status, data }) => {
                if (status >= 400 || data.type === 'error') handleApiError(data, status);
                categData = translateForumCategory(data.categ || null);
                topicData = data.topic || null;
                topicPosts = data.posts || [];
                page = data.page || 1;
                nbPages = data.nbPages || 1;
                total = data.total || 0;
                canWrite = Boolean(data.canWrite);
                canModerate = Boolean(data.canModerate);
                canReply = Boolean(data.canReply);
                canClose = Boolean(data.canClose);
                canSticky = Boolean(data.canSticky);
                timelineUnsubscribed =
                    typeof data.timelineUnsubscribed === 'boolean' ? data.timelineUnsubscribed : null;
                relocateTargets = (data.relocateTargets || []).map((category: ForumCategory) => translateForumCategory(category) as ForumCategory);
                setFormCaptcha((data.captcha || null) as ForumCaptcha | null);
                if (canReply && !formCaptcha) loadCaptcha();
                if (relocateTargetDraft === '' && relocateTargets.length > 0) {
                    relocateTargetDraft = relocateTargets[0]._id;
                }
                loading = false;
                redraw();
                afterLoad?.();
            })
            .catch(err => {
                console.warn('Failed to load forum topic.', err);
                error = _('Could not load forum topic.');
                loading = false;
                redraw();
            });
    }

    /** Load forum search results for the current `text` query. */
    function loadSearch() {
        const text = searchParam('text').trim();
        searchTextDraft = text;
        if (!text) {
            searchPosts = [];
            page = 1;
            nbPages = 1;
            total = 0;
            loading = false;
            redraw();
            return;
        }
        fetch(`/api/forum/search?text=${encodeURIComponent(text)}&page=${page}`)
            .then(parseJsonResponse)
            .then(({ status, data }) => {
                if (status >= 400 || data.type === 'error') handleApiError(data, status);
                searchPosts = data.posts || [];
                page = data.page || 1;
                nbPages = data.nbPages || 1;
                total = data.total || 0;
                loading = false;
                redraw();
            })
            .catch(err => {
                console.warn('Failed to load forum search results.', err);
                error = _('Could not search forum posts.');
                loading = false;
                redraw();
            });
    }

    /** Load moderator-only category feed ordered by latest posts first. */
    function loadModFeed() {
        fetch(`/api/forum/${encodeURIComponent(categ)}/mod-feed?page=${page}`)
            .then(parseJsonResponse)
            .then(({ status, data }) => {
                if (status >= 400 || data.type === 'error') handleApiError(data, status);
                categData = translateForumCategory(data.categ || null);
                modFeedItems = data.items || [];
                page = data.page || 1;
                nbPages = data.nbPages || 1;
                total = data.total || 0;
                loading = false;
                redraw();
            })
            .catch(err => {
                console.warn('Failed to load forum moderation feed.', err);
                error = _('Could not load moderation feed.');
                loading = false;
                redraw();
            });
    }

    /** Submit creation of a new topic in the current category. */
    function submitNewTopic(event: Event) {
        event.preventDefault();
        const name = topicTitleDraft.trim();
        const text = topicTextDraft.trim();
        if (!name || !text || creatingTopic) return;
        if (!formCaptcha || captchaState !== 'success') {
            formSubmitError = _('Please solve the captcha.');
            redraw();
            return;
        }
        formSubmitError = '';
        creatingTopic = true;
        redraw();
        const formData = new URLSearchParams({
            name,
            text,
            gameId: formCaptcha.gameId,
            move: captchaMoveDraft,
        });
        fetch(`/api/forum/${encodeURIComponent(categ)}/topic`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
            body: formData.toString(),
        })
            .then(parseJsonResponse)
            .then(({ status, data }) => {
                if (status >= 400 || data.type === 'error') handleApiError(data, status);
                window.location.assign(data.redirect || `/forum/${encodeURIComponent(categ)}`);
            })
            .catch(err => {
                console.warn('Failed to create topic.', err);
                void alertDialog({ text: err instanceof Error ? err.message : _('Could not create topic.') });
                creatingTopic = false;
                redraw();
            });
    }

    /** Submit a reply message in the currently opened topic. */
    function submitReply(event: Event) {
        event.preventDefault();
        const text = composeReply.trim();
        if (!text || sendingReply || !topicData) return;
        if (!formCaptcha || captchaState !== 'success') {
            formSubmitError = _('Please solve the captcha.');
            redraw();
            return;
        }
        formSubmitError = '';
        sendingReply = true;
        redraw();
        const formData = new URLSearchParams({
            text,
            gameId: formCaptcha.gameId,
            move: captchaMoveDraft,
        });
        fetch(`/api/forum/${encodeURIComponent(categ)}/${encodeURIComponent(slug)}/post`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
            body: formData.toString(),
        })
            .then(parseJsonResponse)
            .then(({ status, data }) => {
                if (status >= 400 || data.type === 'error') handleApiError(data, status);
                const redirectHref = data.redirect || window.location.href;
                if (!isSameDocumentForumRedirect(redirectHref)) {
                    window.location.assign(redirectHref);
                    return;
                }

                const redirect = new URL(redirectHref, window.location.href);
                const postId = redirect.hash.slice(1);
                window.history.pushState(null, '', `${redirect.pathname}${redirect.search}${redirect.hash}`);
                composeReply = '';
                sendingReply = false;
                loadTopic(() => document.getElementById(postId)?.scrollIntoView?.());
            })
            .catch(err => {
                console.warn('Failed to post reply.', err);
                void alertDialog({ text: err instanceof Error ? err.message : _('Could not post reply.') });
                sendingReply = false;
                redraw();
            });
    }

    /** Open custom delete-confirmation modal for one post. */
    function openDeleteModal(postId: string) {
        deletePostDraftId = postId;
        showDeleteModal = true;
        redraw();
    }

    function closeDeleteModal() {
        showDeleteModal = false;
        deletePostDraftId = '';
        redraw();
    }

    /** Delete a post using forum API and refresh location accordingly. */
    function deletePost(postId: string) {
        fetch(`/api/forum/post/${encodeURIComponent(postId)}/delete`, { method: 'POST' })
            .then(parseJsonResponse)
            .then(({ status, data }) => {
                if (status >= 400 || data.type === 'error') handleApiError(data, status);
                if (data.deletedTopic && categ) {
                    window.location.assign(`/forum/${encodeURIComponent(categ)}`);
                } else {
                    window.location.reload();
                }
            })
            .catch(err => {
                console.warn('Failed to delete post.', err);
                void alertDialog({ text: err instanceof Error ? err.message : _('Could not delete post.') });
            });
    }

    /** Toggle edit mode for one post and initialize draft from source text. */
    function editPost(post: ForumPost) {
        if (editDraftByPostId.has(post._id)) {
            editDraftByPostId.delete(post._id);
            savingEditPostIds.delete(post._id);
        } else {
            editDraftByPostId.set(post._id, post.text);
        }
        redraw();
    }

    /** Submit edited post text from inline form and refresh the current page. */
    function submitEditedPost(event: Event, post: ForumPost) {
        event.preventDefault();
        if (savingEditPostIds.has(post._id)) return;

        const draft = (editDraftByPostId.get(post._id) || '').trim();
        if (!draft) return;
        if (draft === post.text.trim()) {
            editDraftByPostId.delete(post._id);
            redraw();
            return;
        }

        savingEditPostIds.add(post._id);
        redraw();

        fetch(`/api/forum/post/${encodeURIComponent(post._id)}/edit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
            body: new URLSearchParams({ text: draft }).toString(),
        })
            .then(parseJsonResponse)
            .then(({ status, data }) => {
                savingEditPostIds.delete(post._id);
                if (status >= 400 || data.type === 'error') handleApiError(data, status);
                window.location.reload();
            })
            .catch(err => {
                savingEditPostIds.delete(post._id);
                redraw();
                console.warn('Failed to edit post.', err);
                void alertDialog({ text: err instanceof Error ? err.message : _('Could not edit post.') });
            });
    }

    /** Toggle topic closed/open state. */
    function toggleTopicClose() {
        fetch(`/api/forum/${encodeURIComponent(categ)}/${encodeURIComponent(slug)}/close`, { method: 'POST' })
            .then(parseJsonResponse)
            .then(({ status, data }) => {
                if (status >= 400 || data.type === 'error') handleApiError(data, status);
                window.location.reload();
            })
            .catch(err => {
                console.warn('Failed to toggle topic close state.', err);
                void alertDialog({ text: err instanceof Error ? err.message : _('Could not update topic.') });
            });
    }

    /** Toggle topic sticky/unsticky state. */
    function toggleTopicSticky() {
        fetch(`/api/forum/${encodeURIComponent(categ)}/${encodeURIComponent(slug)}/sticky`, { method: 'POST' })
            .then(parseJsonResponse)
            .then(({ status, data }) => {
                if (status >= 400 || data.type === 'error') handleApiError(data, status);
                window.location.reload();
            })
            .catch(err => {
                console.warn('Failed to toggle topic sticky state.', err);
                void alertDialog({ text: err instanceof Error ? err.message : _('Could not update topic.') });
            });
    }

    /** Subscribe or unsubscribe from future timeline posts in this forum topic. */
    function toggleTimelineSubscription() {
        if (timelineUnsubscribed === null || updatingTimelineSubscription || !topicData) return;
        const next = !timelineUnsubscribed;
        updatingTimelineSubscription = true;
        redraw();

        fetch('/api/timeline/unsubscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
            body: new URLSearchParams({
                channel: `forum:${topicData._id}`,
                unsubscribed: String(next),
            }).toString(),
        })
            .then(parseJsonResponse)
            .then(({ status, data }) => {
                if (status >= 400 || data.type === 'error') handleApiError(data, status);
                timelineUnsubscribed = Boolean(data.unsubscribed);
            })
            .catch(err => {
                console.warn('Failed to update timeline subscription.', err);
                void alertDialog({
                    text: err instanceof Error ? err.message : _('Could not update timeline subscription.'),
                });
            })
            .finally(() => {
                updatingTimelineSubscription = false;
                redraw();
            });
    }

    /** Add or remove a reaction and update local reaction state from API response. */
    function reactToPost(post: ForumPost, reaction: string) {
        if (!post.canReact) return;
        const key = `${post._id}:${reaction}`;
        if (reactingPostIds.has(key)) return;

        const mine = new Set(post.myReactions || []);
        const nextValue = !mine.has(reaction);

        reactingPostIds.add(key);
        redraw();

        fetch(
            `/api/forum/${encodeURIComponent(categ)}/react/${encodeURIComponent(post._id)}/${encodeURIComponent(reaction)}/${nextValue ? 'true' : 'false'}`,
            {
                method: 'POST',
            },
        )
            .then(parseJsonResponse)
            .then(({ status, data }) => {
                reactingPostIds.delete(key);
                if (status >= 400 || data.type === 'error') handleApiError(data, status);
                post.reactionCounts = data.reactionCounts || {};
                post.myReactions = data.myReactions || [];
                redraw();
            })
            .catch(err => {
                reactingPostIds.delete(key);
                redraw();
                console.warn('Failed to react to post.', err);
                void alertDialog({ text: err instanceof Error ? err.message : _('Could not react to this post.') });
            });
    }

    /** Relocate a full thread to another category via moderator endpoint. */
    function relocateThread(postId: string) {
        if (!relocateTargetDraft) return;
        const formData = new URLSearchParams({ categ: relocateTargetDraft });
        fetch(`/api/forum/post/${encodeURIComponent(postId)}/relocate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
            body: formData.toString(),
        })
            .then(parseJsonResponse)
            .then(({ status, data }) => {
                if (status >= 400 || data.type === 'error') handleApiError(data, status);
                window.location.assign(data.redirect || `/forum/${encodeURIComponent(relocateTargetDraft)}`);
            })
            .catch(err => {
                console.warn('Failed to relocate thread.', err);
                void alertDialog({ text: err instanceof Error ? err.message : _('Could not relocate this thread.') });
            });
    }

    /** Insert quoted markdown for a selected post into the reply textarea. */
    function quotePost(post: ForumPost) {
        const reply = document.querySelector('#forum-reply-text') as HTMLTextAreaElement | null;
        const lines = post.text.split('\n');
        if (lines[0]?.match(/^(?:> )*@.+ said (?:in #\d+:$|\[\^\]\()/)) lines.shift();
        if (lines.length === 0) return;

        const quote =
            `@${post.user} said [^](${postRedirectHref(post._id)})\n` +
            lines
                .map(line => `> ${line}\n`)
                .join('')
                .trim() +
            '\n\n';
        if (quotedReplies.has(quote)) return;
        quotedReplies.add(quote);

        if (reply) {
            const start = reply.selectionStart;
            const end = reply.selectionEnd;
            const before = reply.value.slice(0, start);
            const after = reply.value.slice(end);
            const newText = before + quote + after;
            composeReply = newText;
            redraw();
            window.requestAnimationFrame(() => {
                const updated = document.querySelector('#forum-reply-text') as HTMLTextAreaElement | null;
                if (updated) {
                    const pos = start + quote.length;
                    updated.focus();
                    updated.setSelectionRange(pos, pos);
                }
            });
            return;
        }

        composeReply = `${composeReply.trim()}\n\n${quote}`.trim();
        redraw();
    }

    /** Navigate to search route for the current draft text. */
    function submitSearch(event: Event) {
        event.preventDefault();
        const text = searchTextDraft.trim();
        if (!text) {
            window.location.assign('/forum');
            return;
        }
        window.location.assign(`/forum/search?text=${encodeURIComponent(text)}`);
    }

    /** Render the shared top-right search form used across forum modes. */
    function renderSearchBox() {
        return h(
            'form.search',
            {
                on: { submit: submitSearch },
            },
            [
                h('input', {
                    attrs: {
                        type: 'text',
                        name: 'text',
                        placeholder: _('Search'),
                        enterkeyhint: 'search',
                    },
                    props: { value: searchTextDraft },
                    on: {
                        input: (e: Event) => {
                            searchTextDraft = (e.target as HTMLInputElement).value;
                        },
                    },
                }),
            ],
        );
    }

    /** Render per-post reaction chips with counts and current-user selection state. */
    function renderReactions(post: ForumPost) {
        const canReactPost = Boolean(post.canReact);
        const reactionCounts = post.reactionCounts || {};
        const mine = new Set(post.myReactions || []);
        const showAll = expandedReactionPostIds.has(post._id);
        const visible = REACTIONS.filter(r => showAll || canReactPost || (reactionCounts[r.key] || 0) > 0);
        if (visible.length === 0) return null;

        const allReactionsVisible = REACTIONS.every(r => (reactionCounts[r.key] || 0) > 0);
        const loading = REACTIONS.some(r => reactingPostIds.has(`${post._id}:${r.key}`));
        return h(`div.reactions${canReactPost ? '.reactions-auth' : ''}${loading ? '.loading' : ''}`, [
            canReactPost && !allReactionsVisible
                ? h('button.reactions-toggle', {
                      props: {
                          type: 'button',
                      },
                      attrs: {
                          'data-icon': '+',
                          title: '+',
                      },
                      on: {
                          click: () => {
                              if (expandedReactionPostIds.has(post._id)) expandedReactionPostIds.delete(post._id);
                              else expandedReactionPostIds.add(post._id);
                              redraw();
                          },
                      },
                  })
                : null,
            ...visible.map(r => {
                const count = reactionCounts[r.key] || 0;
                const isMine = mine.has(r.key);
                return h(
                    `button${isMine ? '.mine' : ''}${count > 0 ? '.yes' : '.no'}`,
                    {
                        props: {
                            type: 'button',
                            disabled: !canReactPost,
                        },
                        attrs: {
                            title: r.key,
                        },
                        on: canReactPost ? { click: () => reactToPost(post, r.key) } : {},
                    },
                    [
                        // Reactions primarily use emoji webp assets, with optional per-reaction icon overrides.
                        h('img', {
                            attrs: {
                                src: r.icon
                                    ? `${model.assetURL}${r.icon}`
                                    : `${model.assetURL}/images/emoji/${encodeURIComponent(r.emoji)}.webp`,
                                alt: r.key,
                                width: '20',
                                height: '20',
                            },
                        }),
                        count > 0 ? h('span', `${count}`) : null,
                    ].filter(Boolean as any),
                );
            }),
        ]);
    }

    /** Render forum category index table. */
    function renderIndex() {
        return h('main.forum.index.box', [
            h('div.box__top', [
                h('h1', [
                    h('span.icon-bubbles4.forum-title-icon', { attrs: { 'aria-hidden': 'true' } }),
                    _('Pychess Forum'),
                ]),
                h('div.box__top__actions', [renderSearchBox()]),
            ]),
            h('table.categs.slist.slist-pad', [
                h('thead', [
                    h('tr', [
                        h('th', _('Category')),
                        h('th.right', _('Topics')),
                        h('th.right', _('Posts')),
                        h('th', _('Last post')),
                    ]),
                ]),
                h(
                    'tbody',
                    categories.map(c => {
                        const lastHref = c.lastPostId
                            ? postRedirectHref(c.lastPostId)
                            : `/forum/${encodeURIComponent(c._id)}`;
                        return h('tr', [
                            h('td.subject', [
                                h('h2', [h('a', { attrs: { href: `/forum/${encodeURIComponent(c._id)}` } }, c.name)]),
                                h('p', c.desc || ''),
                            ]),
                            h('td.right', `${c.nbTopics || 0}`),
                            h('td.right', `${c.nbPosts || 0}`),
                            h(
                                'td',
                                c.lastPostAt
                                    ? [
                                          h('a', { attrs: { href: lastHref } }, timeago(c.lastPostAt)),
                                          h('br'),
                                          h('span.forum-by', `${_('by')} ${c.lastPostUser || ''}`),
                                      ]
                                    : h('span.forum-empty', _('No posts yet.')),
                            ),
                        ]);
                    }),
                ),
            ]),
        ]);
    }

    /** Render one category page with topic list and actions. */
    function renderCateg() {
        const actions: VNode[] = [];
        if (canModerate) {
            actions.push(
                h(
                    'a.button.button-empty.text',
                    {
                        attrs: { href: `/forum/${encodeURIComponent(categ)}/mod-feed` },
                    },
                    _('Mod feed'),
                ),
            );
        }
        if (canWrite) {
            actions.push(
                h(
                    'a.button.button-empty.button-green.text',
                    {
                        attrs: { href: `/forum/${encodeURIComponent(categ)}/form` },
                    },
                    _('Create a new topic'),
                ),
            );
        }

        const backHref = categData?.teamId
            ? `/team/${encodeURIComponent(categData.teamId)}`
            : '/forum';
        return h('main.forum.forum-categ.box', [
            h('div.box__top', [
                h('h1', [
                    h('a.text', { attrs: { href: backHref } }, '‹'),
                    ...(categData?.teamId ? [h('span.team-icon.forum-team-icon', { attrs: { 'aria-hidden': 'true' } })] : []),
                    h('span.forum-categ__title', categData?.name || _('Forum')),
                ]),
                h('div.box__top__actions', actions),
            ]),
            h('table.topics.slist.slist-pad', [
                h('thead', [h('tr', [h('th', _('Topic')), h('th.right', _('Replies')), h('th', _('Last post'))])]),
                h(
                    'tbody',
                    topics.map(t =>
                        h(`tr.paginated${t.sticky ? '.sticky' : ''}`, [
                            h('td.subject', [
                                h(
                                    'a',
                                    {
                                        attrs: {
                                            href: `/forum/${encodeURIComponent(categ)}/${encodeURIComponent(t.slug)}`,
                                        },
                                    },
                                    forumTopicName(t),
                                ),
                            ]),
                            h('td.right', `${t.nbReplies || 0}`),
                            h('td', [
                                h(
                                    'a',
                                    {
                                        attrs: {
                                            href: postRedirectHref(t.lastPostId),
                                        },
                                    },
                                    timeago(t.lastPostAt),
                                ),
                                h('br'),
                                h('span.forum-by', `${_('by')} ${titleAndName(t.lastPostUserTitle, t.lastPostUser)}`),
                            ]),
                        ]),
                    ),
                ),
            ]),
            renderPagination(`/forum/${encodeURIComponent(categ)}`),
        ]);
    }

    /** Render one topic post card with controls and rich-text content. */
    function renderTopicPost(post: ForumPost, isFirst: boolean) {
        const erased = isErasedPost(post);
        const author = erased ? ERASED_POST_USER : titleAndName(post.userTitle, post.user);
        const isTopicAuthor = !erased && topicData?.user === post.user;
        const isAnonUser = model.anon === 'True' || model.anon === 'true';
        const canReport = !erased && !isAnonUser && model.username !== post.user;
        const editing = editDraftByPostId.has(post._id);
        const editDraft = editDraftByPostId.get(post._id) || post.text;
        const savingEdit = savingEditPostIds.has(post._id);
        return h(
            `article.forum-post${isFirst ? '.topic-first' : ''}${erased ? '.erased' : ''}`,
            {
                attrs: {
                    id: post._id,
                    'data-post-id': post._id,
                },
            },
            [
                h('div.forum-post__metas', [
                    h(
                        'div',
                        [
                            erased
                                ? h('span.author', author)
                                : h(
                                      `a.user-link.ulpt.author${isTopicAuthor ? '.author--op' : ''}`,
                                      {
                                          attrs: { href: `/@/${encodeURIComponent(post.user)}` },
                                      },
                                      author,
                                  ),
                            h(
                                'a',
                                {
                                    attrs: { href: `#${post._id}` },
                                },
                                post.updatedAt
                                    ? [h('span.post-edited', `${_('edited')} `), timeago(post.updatedAt)]
                                    : timeago(post.createdAt),
                            ),
                            post.canEdit && !erased
                                ? h(
                                      'button.forum-post__button.edit.button.button-empty.text',
                                      {
                                          props: { type: 'button' },
                                          attrs: {
                                              title: _('Edit'),
                                              'aria-label': _('Edit'),
                                          },
                                          on: { click: () => editPost(post) },
                                      },
                                      [h('i.icon.icon-pencil'), h('span', _('Edit'))],
                                  )
                                : null,
                            isFirst && canModerate && relocateTargets.length > 0
                                ? h(
                                      'button.forum-post__button.mod-relocate.button.button-empty.icon-only',
                                      {
                                          props: { type: 'button' },
                                          attrs: {
                                              title: _('Relocate'),
                                              'aria-label': _('Relocate'),
                                          },
                                          on: {
                                              click: () => {
                                                  if (!relocateTargetDraft && relocateTargets.length > 0) {
                                                      relocateTargetDraft = relocateTargets[0]._id;
                                                  }
                                                  showRelocateModal = true;
                                                  redraw();
                                              },
                                          },
                                      },
                                      [h('i.icon.icon-step-forward')],
                                  )
                                : null,
                            post.canDelete
                                ? h(
                                      'button.forum-post__button.delete.button.button-empty.icon-only',
                                      {
                                          props: { type: 'button' },
                                          attrs: {
                                              title: _('Delete'),
                                              'aria-label': _('Delete'),
                                          },
                                          on: { click: () => openDeleteModal(post._id) },
                                      },
                                      [h('i.icon.icon-trash-o')],
                                  )
                                : null,
                            canReply && !erased
                                ? h(
                                      'button.forum-post__button.quote.button.button-empty.text',
                                      {
                                          props: { type: 'button' },
                                          attrs: {
                                              title: _('Quote'),
                                              'aria-label': _('Quote'),
                                          },
                                          on: { click: () => quotePost(post) },
                                      },
                                      [h('span.quote-glyph', '❝'), h('span', _('Quote'))],
                                  )
                                : null,
                            canReport
                                ? h(
                                      'a.forum-post__button.report.button.button-empty.icon-only',
                                      {
                                          attrs: {
                                              href: reportPostHref(post),
                                              title: _('Report'),
                                              'aria-label': _('Report'),
                                          },
                                      },
                                      [h('i.icon.icon-warning')],
                                  )
                                : null,
                        ].filter(Boolean as any),
                    ),
                ]),
                h(
                    'div.forum-post__message.expand-text',
                    {
                        hook: erased
                            ? {}
                            : {
                                  insert(vnode) {
                                      enhanceForumPostMessage(vnode.elm as HTMLElement);
                                  },
                                  postpatch(_oldVnode, vnode) {
                                      enhanceForumPostMessage(vnode.elm as HTMLElement);
                                  },
                              },
                    },
                    erased ? ERASED_POST_TEXT : renderRichText(post.text, { imageClass: 'forum-post-inline-image' }),
                ),
                !erased ? h('div.forum-post__message-source', post.text) : null,
                !erased ? renderReactions(post) : null,
                editing && !erased
                    ? h(
                          'form.edit-post-form',
                          {
                              on: {
                                  submit: (event: Event) => submitEditedPost(event, post),
                              },
                          },
                          [
                              h('textarea.form-control.post-text-area.edit-post-box', {
                                  attrs: {
                                      required: true,
                                      rows: 10,
                                      maxlength: `${FORUM_MAX_POST_LEN}`,
                                      'data-topic': topicData?._id || '',
                                  },
                                  props: { value: editDraft },
                                  on: {
                                      input: (e: Event) => {
                                          editDraftByPostId.set(post._id, (e.target as HTMLTextAreaElement).value);
                                      },
                                  },
                              }),
                              h('div.edit-buttons', [
                                  h(
                                      'a.edit-post-cancel',
                                      {
                                          attrs: { href: '#' },
                                          on: {
                                              click: (event: Event) => {
                                                  event.preventDefault();
                                                  editDraftByPostId.delete(post._id);
                                                  savingEditPostIds.delete(post._id);
                                                  redraw();
                                              },
                                          },
                                      },
                                      _('Cancel'),
                                  ),
                                  h(
                                      'button.button',
                                      {
                                          props: {
                                              type: 'submit',
                                              disabled: savingEdit,
                                          },
                                      },
                                      _('Apply'),
                                  ),
                              ]),
                          ],
                      )
                    : null,
            ].filter(Boolean as any),
        );
    }

    /** Render moderator relocate modal for moving a thread between categories. */
    function renderRelocateModal(firstPostId: string) {
        if (!showRelocateModal) return null;
        return h('div.forum-relocate-modal', [
            h('div.forum-modal-backdrop', {
                on: {
                    click: () => {
                        showRelocateModal = false;
                        redraw();
                    },
                },
            }),
            h('div.forum-modal-body', [
                h('p', _('Move the entire thread to another forum')),
                h(
                    'form.form3',
                    {
                        on: {
                            submit: (e: Event) => {
                                e.preventDefault();
                                showRelocateModal = false;
                                redraw();
                                relocateThread(firstPostId);
                            },
                        },
                    },
                    [
                        h(
                            'select.form-control',
                            {
                                attrs: { name: 'categ' },
                                props: { value: relocateTargetDraft },
                                on: {
                                    change: (e: Event) => {
                                        relocateTargetDraft = (e.target as HTMLSelectElement).value;
                                    },
                                },
                            },
                            relocateTargets.map(target =>
                                h(
                                    'option',
                                    {
                                        attrs: { value: target._id },
                                    },
                                    target.name,
                                ),
                            ),
                        ),
                        h('div.form-actions', [
                            h(
                                'button.button.button-empty.cancel',
                                {
                                    props: { type: 'button' },
                                    on: {
                                        click: () => {
                                            showRelocateModal = false;
                                            redraw();
                                        },
                                    },
                                },
                                _('Cancel'),
                            ),
                            h('button.button.button-red', { props: { type: 'submit' } }, _('Relocate the thread')),
                        ]),
                    ],
                ),
            ]),
        ]);
    }

    function renderDeleteModal() {
        if (!showDeleteModal || !deletePostDraftId) return null;
        return h('div.forum-delete-modal', [
            h('div.forum-modal-backdrop', {
                on: {
                    click: () => closeDeleteModal(),
                },
            }),
            h('div.forum-modal-body', [
                h('p', _('Delete the post')),
                h(
                    'form.form3',
                    {
                        on: {
                            submit: (e: Event) => {
                                e.preventDefault();
                                const postId = deletePostDraftId;
                                closeDeleteModal();
                                deletePost(postId);
                            },
                        },
                    },
                    [
                        h('div.form-actions', [
                            h(
                                'button.button.button-empty.cancel',
                                {
                                    props: { type: 'button' },
                                    on: {
                                        click: () => closeDeleteModal(),
                                    },
                                },
                                _('Cancel'),
                            ),
                            h('button.button.button-red', { props: { type: 'submit' } }, _('Delete the post')),
                        ]),
                    ],
                ),
            ]),
        ]);
    }

    /** Render full topic page: header, posts, actions, and reply form. */
    function renderTopic() {
        const topicUrl = `/forum/${encodeURIComponent(categ)}/${encodeURIComponent(slug)}`;
        const firstPostId = topicPosts.length > 0 ? topicPosts[0]._id : '';
        const blogBackUrl = (topicData?.blogPostUrl || '').trim();
        const backHref = blogBackUrl || `/forum/${encodeURIComponent(categ)}`;
        return h(
            'main.forum.forum-topic.page-small.box.box-pad',
            [
                h('div.box__top', [
                    h('h1', [h('a.text', { attrs: { href: backHref } }, '‹'), topicData ? ` ${forumTopicName(topicData)}` : '']),
                ]),
                renderPagination(topicUrl),
                h(
                    'div.forum-topic__posts',
                    topicPosts.map((post, idx) => renderTopicPost(post, idx === 0 && page === 1)),
                ),
                renderPagination(topicUrl),
                h('div.forum-topic__actions', [
                    topicData?.closed
                        ? h('p', _('This topic is now closed.'))
                        : canReply
                          ? h('h2#reply', _('Reply to this topic'))
                          : h('p', _('You cannot post yet. Play some games first.')),
                    h(
                        'div',
                        [
                            timelineUnsubscribed !== null
                                ? h(
                                      'button.button.button-empty.text.timeline-unsubscribe',
                                      {
                                          props: { type: 'button', disabled: updatingTimelineSubscription },
                                          on: { click: toggleTimelineSubscription },
                                      },
                                      timelineUnsubscribed ? _('Subscribe') : _('Unsubscribe'),
                                  )
                                : null,
                            canClose
                                ? h(
                                      'button.button.button-empty.button-red',
                                      {
                                          props: { type: 'button' },
                                          on: { click: toggleTopicClose },
                                      },
                                      topicData?.closed ? _('Reopen') : _('Close'),
                                  )
                                : null,
                            canSticky
                                ? h(
                                      'button.button.button-empty.button-brag',
                                      {
                                          props: { type: 'button' },
                                          on: { click: toggleTopicSticky },
                                      },
                                      topicData?.sticky ? _('Unsticky') : _('Sticky'),
                                  )
                                : null,
                        ].filter(Boolean as any),
                    ),
                ]),
                canReply
                    ? h(
                          'form.form3.reply',
                          {
                              on: { submit: submitReply },
                          },
                          [
                              h('label', { attrs: { for: 'forum-reply-text' } }, _('Message')),
                              h('textarea#forum-reply-text.post-text-area.form-control', {
                                  attrs: {
                                      rows: 10,
                                      placeholder: _('Please be nice in the forum!'),
                                      maxlength: `${FORUM_MAX_POST_LEN}`,
                                      'data-topic': topicData?._id || '',
                                  },
                                  props: { value: composeReply },
                                  on: {
                                      input: (e: Event) => {
                                          composeReply = (e.target as HTMLTextAreaElement).value;
                                          if (formSubmitError) formSubmitError = '';
                                      },
                                  },
                              }),
                              h('div.forum-form-help.space-between', [
                                  h('span', _('Links and mentions available')),
                                  h(
                                      'a.text',
                                      {
                                          attrs: {
                                              href: '/page/forum-etiquette',
                                          },
                                      },
                                      _('Forum etiquette'),
                                  ),
                              ]),
                              formSubmitError ? h('div.forum-form-error.error', formSubmitError) : null,
                              renderCaptcha(),
                              h('div.form-actions', [
                                  h('a.button.button-empty', { attrs: { href: backHref } }, _('Cancel')),
                                  h(
                                      'button.button',
                                      {
                                          props: { type: 'submit', disabled: sendingReply },
                                      },
                                      sendingReply ? _('Sending...') : _('Reply'),
                                  ),
                              ]),
                          ],
                      )
                    : null,
                renderDeleteModal(),
                firstPostId ? renderRelocateModal(firstPostId) : null,
            ].filter(Boolean as any),
        );
    }

    /** Render new-topic form page. */
    function renderNewTopic() {
        return h('main.forum.forum-topic.topic-form.page-small.box.box-pad', [
            h('div.box__top', [
                h('h1', [
                    h('a.text', { attrs: { href: `/forum/${encodeURIComponent(categ)}` } }, '‹'),
                    ` ${_('New topic')}`,
                ]),
            ]),
            h('section.warning', [
                h('h2', _('Important')),
                h('p', _('Your question may already be answered in FAQ or community pages.')),
                h('p', _('Use reports for moderation issues; keep forum posts constructive and respectful.')),
                h('p', [
                    _('Make sure to read'),
                    ' ',
                    h('a', { attrs: { href: '/page/forum-etiquette' } }, _('Forum etiquette')),
                    '.',
                ]),
            ]),
            h(
                'form.form3',
                {
                    on: { submit: submitNewTopic },
                },
                [
                    h('label', { attrs: { for: 'forum-topic-title' } }, _('Subject')),
                    h('input#forum-topic-title.form-control', {
                        attrs: { type: 'text', maxlength: `${FORUM_MAX_TOPIC_NAME_LEN}`, required: true },
                        props: { value: topicTitleDraft },
                        on: {
                            input: (e: Event) => {
                                topicTitleDraft = (e.target as HTMLInputElement).value;
                                if (formSubmitError) formSubmitError = '';
                            },
                        },
                    }),
                    h('label', { attrs: { for: 'forum-topic-text' } }, _('Message')),
                    h('textarea#forum-topic-text.post-text-area.form-control', {
                        attrs: {
                            rows: 10,
                            maxlength: `${FORUM_MAX_POST_LEN}`,
                            placeholder: _('Please be nice in the forum!'),
                            required: true,
                        },
                        props: { value: topicTextDraft },
                        on: {
                            input: (e: Event) => {
                                topicTextDraft = (e.target as HTMLTextAreaElement).value;
                                if (formSubmitError) formSubmitError = '';
                            },
                        },
                    }),
                    h('div.forum-form-help.space-between', [
                        h('span', _('Links and mentions available')),
                        h(
                            'a.text',
                            {
                                attrs: {
                                    href: '/page/forum-etiquette',
                                },
                            },
                            _('Forum etiquette'),
                        ),
                    ]),
                    formSubmitError ? h('div.forum-form-error.error', formSubmitError) : null,
                    renderCaptcha(),
                    h('div.form-actions', [
                        h(
                            'a.button.button-empty',
                            { attrs: { href: `/forum/${encodeURIComponent(categ)}` } },
                            _('Cancel'),
                        ),
                        h(
                            'button.button',
                            {
                                props: { type: 'submit', disabled: creatingTopic },
                            },
                            creatingTopic ? _('Creating...') : _('Create the topic'),
                        ),
                    ]),
                ],
            ),
        ]);
    }

    /** Render search results page. */
    function renderSearch() {
        const text = searchParam('text').trim();
        return h('main.forum.box.search', [
            h('div.box__top', [
                h('h1', [
                    h('a.text', { attrs: { href: '/forum' } }, '‹'),
                    text ? `${_('Search')} "${text}"` : _('Search'),
                ]),
                h('div.box__top__actions', [renderSearchBox()]),
            ]),
            h('strong.nb-results.box__pad', `${total} ${_('forum posts')}`),
            h('table.slist.slist-pad.slist-invert.search__results', [
                h(
                    'tbody',
                    searchPosts.map(row => {
                        const post = row.post;
                        const erased = isErasedPost(post);
                        const postHref = postRedirectHref(post._id);
                        return h('tr.stack-row', [
                            h('td', [
                                h('a.post', { attrs: { href: postHref } }, `${forumCategoryName(row.categ._id, row.categ.name)} - ${forumTopicName(row.topic)}`),
                                h('p', shorten(erased ? ERASED_POST_TEXT : post.text, 220)),
                            ]),
                            h('td.info', [
                                h('span', timeago(post.createdAt)),
                                h('br'),
                                h('span', erased ? ERASED_POST_USER : titleAndName(row.postUserTitle, post.user)),
                            ]),
                        ]);
                    }),
                ),
            ]),
            renderPagination(`/forum/search?text=${encodeURIComponent(text)}`),
        ]);
    }

    /** Render moderator category feed table. */
    function renderModFeed() {
        return h('main.forum.forum-mod-feed.box', [
            h('div.box__top', [
                h('h1', [
                    h('a.text', { attrs: { href: `/forum/${encodeURIComponent(categ)}` } }, '‹'),
                    ` ${categData?.name || categ} ${_('mod feed')}`,
                ]),
            ]),
            h('table.slist.slist-pad', [
                h('thead', [
                    h('tr', [h('th', _('User')), h('th', _('Topic')), h('th', _('Post')), h('th', _('Date'))]),
                ]),
                h(
                    'tbody',
                    modFeedItems.map(item => {
                        const post = item.post;
                        const erased = isErasedPost(post);
                        return h('tr', [
                            h('td', [
                                erased
                                    ? h('span.user-link', ERASED_POST_USER)
                                    : h(
                                          'a.user-link',
                                          { attrs: { href: `/@/${encodeURIComponent(post.user)}` } },
                                          titleAndName(post.userTitle, post.user),
                                      ),
                            ]),
                            h('td', [
                                h(
                                    'a',
                                    {
                                        attrs: {
                                            href: `/forum/${encodeURIComponent(categ)}/${encodeURIComponent(item.topic.slug)}`,
                                        },
                                    },
                                    item.topic.name,
                                ),
                            ]),
                            h('td', shorten(erased ? ERASED_POST_TEXT : post.text, 280)),
                            h('td', [h('a', { attrs: { href: postRedirectHref(post._id) } }, timeago(post.createdAt))]),
                        ]);
                    }),
                ),
            ]),
            renderPagination(`/forum/${encodeURIComponent(categ)}/mod-feed`),
        ]);
    }

    /** Select and render page body for the active forum mode. */
    function render() {
        if (loading) {
            return h('main.forum.box', [h('div.box__pad', _('Loading...'))]);
        }
        if (error) {
            return h('main.forum.box', [h('div.box__pad.error', error)]);
        }
        if (mode === 'categ') return renderCateg();
        if (mode === 'topic') return renderTopic();
        if (mode === 'newTopic') return renderNewTopic();
        if (mode === 'search') return renderSearch();
        if (mode === 'modFeed') return renderModFeed();
        return renderIndex();
    }

    setTimeout(() => {
        appEl = document.getElementById('forum-app') as HTMLElement;
        if (mode === 'categ') loadCateg();
        else if (mode === 'topic') loadTopic();
        else if (mode === 'newTopic') {
            loading = false;
            redraw();
            loadCaptcha();
        } else if (mode === 'search') loadSearch();
        else if (mode === 'modFeed') loadModFeed();
        else loadIndex();
    }, 0);

    return h('main#forum-app.forum.box');
}
