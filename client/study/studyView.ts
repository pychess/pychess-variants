import { h, toVNode, type VNode } from 'snabbdom';
import ffishModule from 'ffish-es6';
import ffishAliceModule from 'ffish-alice-es6';

import { analysisUnderboard, renderEmbedPage } from '../analysis';
import { hasActiveEligibleLiveGame } from '../antiCheat';
import { alertDialog } from '../alertDialog';
import { analysisContext } from '../analysis/analysisContext';
import { analysisChart } from '../analysis/analysisChart';
import { AnalysisController } from '../analysis/analysisCtrl';
import { parentPath } from '../analysis/analysisTree';
import { renderAnalysisPage } from '../analysis/analysisPage';
import { copyTextToClipboard } from '../clipboard';
import { confirmDialog } from '../confirmDialog';
import { downloadText, notifyChessgroundResize, patch } from '../document';
import { _, ngettext } from '../i18n';
import { updateMovelist } from '../movelist';
import { renderLinkifiedText } from '../richTextEnhance';
import type { PyChessModel, StudyFeatureSelection, StudyPageModel } from '../types';
import { activateStudyEngineRules, loadCataloguedVariantsFromJson, variantConfigIni, VARIANTS } from '../variants';
import { ChessgroundKeyboard } from '../accessibility/chessgroundKeyboard';
import { buildStudyEngineRules } from './variantRules';
import { variantsIni } from '../variantsIni';
import { createWebsocket } from '../socket/webSocketUtils';
import { displayUsername, userLink } from '../user';
import { StaleStudyChapterSnapshotError, StudyChapterNavigation } from './chapterNavigation';
import { analysisTreeFromStudy } from './studyTree';
import { StudyAnalysisExtension, type StudyAnnotationState } from './studySync';
import { GLYPH_GROUPS, toggleGlyph } from '../analysis/glyphs';
import { StudyCommentEditor } from './commentEditor';
import { StudyGamebookEditor } from './studyGamebookEdit';
import { StudyGamebookPlayback } from './studyGamebookPlayback';
import { StudyPracticeSession, type StudyPracticeState } from './studyPractice';
import { StudyPracticeProgress } from './studyPracticeProgress';
import { studyPracticeGoalText } from './studyPracticeGoal';
import { fetchStudyChapterExportData, renderStudyChapterPgn, renderStudyPgn, studyPgnFilename } from './studyPgn';
import {
    parseStudyPgnForImportWithEngines,
    postStudyPgnImport,
    studyPgnGameUsesAlice,
    type StudyPgnImportProgressCallback,
} from './studyPgnImport';
import { pgnParser as studyPgnParser } from '../pgnParser';
import {
    studyChapterCreateForm,
    studyChapterModeField,
    studyChapterModeLabel,
    studyChapterOrientationField,
    settleStudyFormSubmit,
} from './studyChapterForm';
import { studySessionPolicy, type StudySessionPolicy } from './studyMode';
import { isConcealPlayback } from './studyConceal';

function dialogField(label: string, control: VNode): VNode {
    return h('label.study-dialog__field', [h('span', label), control]);
}

function studySetting(
    study: StudyPageModel,
    key: 'computer' | 'explorer' | 'cloneable' | 'shareable',
): StudyFeatureSelection {
    return study.settings?.[key] ?? 'everyone';
}

function studyCanShare(study: StudyPageModel): boolean {
    return study.canShare !== false;
}

function studyCanEmbed(study: StudyPageModel): boolean {
    return study.canEmbed ?? study.visibility !== 'private';
}

const studyPermissionChoices: [StudyFeatureSelection, string][] = [
    ['nobody', _('Nobody')],
    ['owner', _('Only me')],
    ['contributor', _('Contributors')],
    ['member', _('Members')],
    ['everyone', _('Everyone')],
];

function studyPermissionField(
    name: 'computer' | 'cloneable' | 'shareable',
    label: string,
    selected: StudyFeatureSelection,
): VNode {
    return dialogField(
        label,
        h(
            'select',
            { attrs: { name } },
            studyPermissionChoices.map(([value, text]) =>
                h('option', { attrs: { value, selected: selected === value } }, text),
            ),
        ),
    );
}

function studySettingsForm(study: StudyPageModel, formId: string): VNode {
    return h(`form#${formId}.study-dialog__form`, { attrs: { method: 'post', action: `/study/${study.id}/edit` } }, [
        dialogField(
            _('Name'),
            h('input', {
                attrs: {
                    type: 'text',
                    name: 'name',
                    value: study.name,
                    maxlength: '100',
                    autocomplete: 'off',
                },
            }),
        ),
        dialogField(
            _('Visibility'),
            h(
                'select',
                { attrs: { name: 'visibility' } },
                [
                    ['private', _('Private')],
                    ['unlisted', _('Unlisted')],
                    ['public', _('Public')],
                ].map(([value, label]) =>
                    h('option', { attrs: { value, selected: study.visibility === value } }, label),
                ),
            ),
        ),
        studyPermissionField('computer', _('Computer analysis'), studySetting(study, 'computer')),
        studyPermissionField('cloneable', _('Allow cloning'), studySetting(study, 'cloneable')),
        studyPermissionField('shareable', _('Share & export'), studySetting(study, 'shareable')),
        // PyChess does not have an opening explorer yet. Preserve the compatible
        // Lichess setting in the document without exposing a non-functional control.
        h('input', { attrs: { type: 'hidden', name: 'explorer', value: studySetting(study, 'explorer') } }),
    ]);
}

function chapterSettingsForm(
    study: StudyPageModel,
    chapter: StudyPageModel['chapters'][number],
    formId: string,
    beforeSubmit: () => Promise<boolean>,
): VNode {
    const descriptionPinned =
        chapter.descriptionPinned ?? (chapter.id === study.chapter.id && Boolean(study.chapter.description));
    return h(
        `form#${formId}.study-dialog__form`,
        {
            attrs: { method: 'post', action: `/study/${study.id}/${chapter.id}/edit` },
            on: {
                submit: (event: SubmitEvent) => settleStudyFormSubmit(event, beforeSubmit),
            },
        },
        [
            dialogField(
                _('Name'),
                h('input', {
                    attrs: {
                        type: 'text',
                        name: 'name',
                        value: chapter.name,
                        maxlength: '80',
                        autocomplete: 'off',
                    },
                }),
            ),
            h('div.study-dialog__split', [
                studyChapterOrientationField(chapter.orientation),
                studyChapterModeField(chapter.mode, study.enabledModes),
            ]),
            dialogField(
                _('Pinned chapter comment'),
                h('select', { attrs: { name: 'description' } }, [
                    h('option', { attrs: { value: '', selected: !descriptionPinned } }, _('No pinned comment')),
                    h('option', { attrs: { value: '1', selected: descriptionPinned } }, _('Right under the board')),
                ]),
            ),
        ],
    );
}

function dialogActions(saveFormId: string, saveLabel: string, destructive?: VNode): VNode {
    return h('div.study-dialog__actions', [
        destructive ?? h('span'),
        h('button.button', { attrs: { type: 'submit', form: saveFormId } }, saveLabel),
    ]);
}

function deleteForm(
    action: string,
    label: string,
    prompt: string,
    className?: string,
    hiddenFields?: Record<string, string>,
): VNode {
    return h(
        'form',
        {
            attrs: { method: 'post', action },
            class: className ? { [className]: true } : undefined,
            on: {
                submit: event => {
                    event.preventDefault();
                    const form = event.currentTarget as HTMLFormElement;
                    void confirmDialog({
                        text: prompt,
                        confirmText: label,
                        cancelText: _('Cancel'),
                        danger: true,
                    }).then(confirmed => {
                        if (confirmed) HTMLFormElement.prototype.submit.call(form);
                    });
                },
            },
        },
        [
            ...Object.entries(hiddenFields ?? {}).map(([name, value]) =>
                h('input', { attrs: { type: 'hidden', name, value } }),
            ),
            h('button.button.button-red', { attrs: { type: 'submit' } }, label),
        ],
    );
}

// Layout and controls adapted from lila ui/analyse/src/study/studyView.ts
// and studyChapters.ts: chapters at the side, editing tools under the board.
function icon(name: string): VNode {
    return h(`i.icon.icon-${name}`, { attrs: { 'aria-hidden': 'true' } });
}

function studyLikeControl(study: StudyPageModel): VNode {
    const label = study.liked ? _('Unlike') : _('Like');
    const content = [icon('heart'), h('span.study-like__count', String(study.likes))];
    if (!study.canLike)
        return h(
            'span.study-like.study-like--readonly',
            {
                class: { liked: study.liked },
                attrs: {
                    title: ngettext('%1 like', '%1 likes', study.likes),
                    'data-study-like': '',
                },
            },
            content,
        );
    return h(
        'button.study-like',
        {
            class: { liked: study.liked },
            attrs: {
                type: 'button',
                title: label,
                'aria-label': label,
                'aria-pressed': study.liked ? 'true' : 'false',
                'data-study-like': '',
            },
            props: { disabled: Boolean(study.likePending) },
            on: { click: () => void toggleStudyLike(study) },
        },
        content,
    );
}

function studyMetadataTitle(study: StudyPageModel): VNode {
    return h('h2.study-underboard__title', [
        h('span.study-underboard__name', [
            `${study.name}: ${study.chapter.name}`,
            ...((study.chapter.mode ?? 'normal') === 'normal'
                ? []
                : [h('span.study-underboard__mode', studyChapterModeLabel(study.chapter.mode ?? 'normal'))]),
        ]),
        studyLikeControl(study),
    ]);
}

function updateStudyLikeControl(study: StudyPageModel): void {
    const label = study.liked ? _('Unlike') : _('Like');
    document.querySelectorAll<HTMLElement>('[data-study-like]').forEach(element => {
        element.classList.toggle('liked', study.liked);
        const count = element.querySelector<HTMLElement>('.study-like__count');
        if (count) count.textContent = String(study.likes);
        if (element instanceof HTMLButtonElement) {
            element.title = label;
            element.setAttribute('aria-label', label);
            element.setAttribute('aria-pressed', study.liked ? 'true' : 'false');
            element.disabled = Boolean(study.likePending);
        } else element.title = ngettext('%1 like', '%1 likes', study.likes);
    });
}

async function toggleStudyLike(study: StudyPageModel): Promise<void> {
    if (!study.canLike || study.likePending) return;
    const previousLiked = study.liked;
    const previousLikes = study.likes;
    study.likePending = true;
    study.liked = !previousLiked;
    study.likes = Math.max(0, previousLikes + (study.liked ? 1 : -1));
    updateStudyLikeControl(study);
    try {
        const response = await fetch(`/study/${study.id}/like`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ liked: study.liked }),
        });
        if (!response.ok) throw new Error((await response.text()).trim() || response.statusText);
        const payload = (await response.json()) as { liked?: unknown; likes?: unknown };
        if (typeof payload.liked !== 'boolean' || !Number.isInteger(payload.likes) || (payload.likes as number) < 0)
            throw new Error(_('Invalid Study like response'));
        study.liked = payload.liked;
        study.likes = payload.likes as number;
    } catch (error) {
        study.liked = previousLiked;
        study.likes = previousLikes;
        void alertDialog({
            text: _('Could not update Study like: %1', error instanceof Error ? error.message : String(error)),
        });
    } finally {
        study.likePending = false;
        updateStudyLikeControl(study);
    }
}

function studyTopicHref(topic: string): string {
    return `/study/topic/${encodeURIComponent(topic)}`;
}

function studyTopicsView(study: StudyPageModel): VNode {
    return h('div.study-topics', { attrs: { 'data-study-topics': '' } }, [
        ...study.topics.map(topic => h('a.study-topic', { attrs: { href: studyTopicHref(topic) } }, topic)),
        ...(study.canWrite
            ? [
                  h(
                      'button.study-topics__manage',
                      {
                          attrs: { type: 'button' },
                          on: { click: () => openStudyTopicsDialog(study) },
                      },
                      _('Manage topics'),
                  ),
              ]
            : []),
    ]);
}

function updateStudyTopicsView(study: StudyPageModel): void {
    document
        .querySelectorAll<HTMLElement>('[data-study-topics]')
        .forEach(element => patch(toVNode(element), studyTopicsView(study)));
    const modal = document.querySelector<HTMLDialogElement>('#study-topics');
    if (modal && !modal.open) syncStudyTopicEditor(study);
}

function canonicalStudyTopic(value: string): string {
    return value.trim().replace(/\s+/g, ' ');
}

function studyTopicLength(value: string): number {
    return Array.from(value).length;
}

function studyTopicEditorTopics(editor: HTMLElement): string[] {
    return [...editor.querySelectorAll<HTMLElement>('[data-topic-value]')]
        .map(element => element.dataset.topicValue ?? '')
        .filter(Boolean);
}

function studyTopicEditorFeedback(editor: HTMLElement, message = '', invalid = false): void {
    const feedback = editor.closest('form')?.querySelector<HTMLElement>('[data-topic-feedback]');
    const input = editor.querySelector<HTMLInputElement>('.study-topic-editor__input');
    if (feedback) {
        feedback.textContent = message;
        feedback.classList.toggle('is-error', invalid);
    }
    if (input) input.setAttribute('aria-invalid', invalid ? 'true' : 'false');
}

function updateStudyTopicEditorMeta(study: StudyPageModel, editor: HTMLElement): void {
    const topics = studyTopicEditorTopics(editor);
    const input = editor.querySelector<HTMLInputElement>('.study-topic-editor__input');
    const count = editor.closest('form')?.querySelector<HTMLElement>('[data-topic-count]');
    const length = editor.closest('form')?.querySelector<HTMLElement>('[data-topic-length]');
    if (count) count.textContent = `${topics.length}/${study.maxTopics} ${_('topics')}`;
    if (length && input)
        length.textContent = `${studyTopicLength(input.value)}/${study.topicMaxLength} ${_('characters')}`;
    if (input) {
        input.disabled = topics.length >= study.maxTopics;
        if (input.disabled) input.placeholder = _('Maximum number of topics reached');
        else input.placeholder = _('Add a topic…');
    }
}

function renderStudyTopicEditorChips(study: StudyPageModel, editor: HTMLElement, topics: string[]): void {
    const selected = editor.querySelector<HTMLElement>('.study-topic-editor__selected');
    if (!selected) return;
    selected.replaceChildren();
    for (const topic of topics) {
        const chip = document.createElement('span');
        chip.className = 'study-topic-editor__chip';
        chip.dataset.topicValue = topic;
        const label = document.createElement('span');
        label.textContent = topic;
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'study-topic-editor__remove';
        remove.setAttribute('aria-label', _('Remove %1', topic));
        remove.textContent = '×';
        remove.addEventListener('click', () => {
            chip.remove();
            studyTopicEditorFeedback(editor);
            updateStudyTopicEditorMeta(study, editor);
            editor.querySelector<HTMLInputElement>('.study-topic-editor__input')?.focus();
        });
        chip.append(label, remove);
        selected.append(chip);
    }
    updateStudyTopicEditorMeta(study, editor);
}

function clearStudyTopicSuggestions(editor: HTMLElement): void {
    const suggestions = editor.querySelector<HTMLElement>('.study-topic-editor__suggestions');
    const input = editor.querySelector<HTMLInputElement>('.study-topic-editor__input');
    if (!suggestions) return;
    suggestions.replaceChildren();
    suggestions.hidden = true;
    input?.setAttribute('aria-expanded', 'false');
}

function validateStudyTopic(study: StudyPageModel, topic: string): string | null {
    const length = studyTopicLength(topic);
    if (length < study.topicMinLength) return _('Topics must have at least %1 characters.', study.topicMinLength);
    if (length > study.topicMaxLength) return _('Topics can have at most %1 characters.', study.topicMaxLength);
    return null;
}

function addStudyTopic(study: StudyPageModel, editor: HTMLElement, raw: string): boolean {
    const topic = canonicalStudyTopic(raw);
    if (!topic) return true;
    const error = validateStudyTopic(study, topic);
    if (error) {
        studyTopicEditorFeedback(editor, error, true);
        return false;
    }
    const topics = studyTopicEditorTopics(editor);
    if (topics.includes(topic)) {
        studyTopicEditorFeedback(editor, _('This topic is already added.'), true);
        return false;
    }
    if (topics.length >= study.maxTopics) {
        studyTopicEditorFeedback(editor, _('A study can have at most %1 topics.', study.maxTopics), true);
        return false;
    }
    renderStudyTopicEditorChips(study, editor, [...topics, topic]);
    const input = editor.querySelector<HTMLInputElement>('.study-topic-editor__input');
    if (input) input.value = '';
    studyTopicEditorFeedback(editor);
    clearStudyTopicSuggestions(editor);
    updateStudyTopicEditorMeta(study, editor);
    return true;
}

type StudyTopicEditorRequest = { timer?: number; abort?: AbortController };
const studyTopicEditorRequests = new WeakMap<HTMLElement, StudyTopicEditorRequest>();

function renderStudyTopicSuggestions(study: StudyPageModel, editor: HTMLElement, topics: string[]): void {
    const suggestions = editor.querySelector<HTMLElement>('.study-topic-editor__suggestions');
    if (!suggestions) return;
    const selected = new Set(studyTopicEditorTopics(editor));
    const usable = topics.filter(topic => !selected.has(topic));
    suggestions.replaceChildren();
    if (!usable.length) {
        suggestions.hidden = true;
        return;
    }
    for (const topic of usable) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'study-topic-editor__suggestion';
        button.setAttribute('role', 'option');
        button.textContent = topic;
        button.addEventListener('mousedown', event => event.preventDefault());
        button.addEventListener('click', () => {
            if (addStudyTopic(study, editor, topic))
                editor.querySelector<HTMLInputElement>('.study-topic-editor__input')?.focus();
        });
        suggestions.append(button);
    }
    suggestions.hidden = false;
    editor.querySelector<HTMLInputElement>('.study-topic-editor__input')?.setAttribute('aria-expanded', 'true');
}

function requestStudyTopicSuggestions(study: StudyPageModel, editor: HTMLElement, term: string): void {
    const state = studyTopicEditorRequests.get(editor) ?? {};
    if (state.timer !== undefined) window.clearTimeout(state.timer);
    state.abort?.abort();
    clearStudyTopicSuggestions(editor);
    if (studyTopicLength(term) < study.topicMinLength) {
        studyTopicEditorRequests.set(editor, state);
        return;
    }
    state.timer = window.setTimeout(() => {
        const abort = new AbortController();
        state.abort = abort;
        void fetch(`/study/topic/autocomplete?term=${encodeURIComponent(term)}`, { signal: abort.signal })
            .then(response => (response.ok ? response.json() : []))
            .then(payload => {
                if (Array.isArray(payload) && payload.every(topic => typeof topic === 'string'))
                    renderStudyTopicSuggestions(study, editor, payload as string[]);
            })
            .catch(error => {
                if (!(error instanceof DOMException && error.name === 'AbortError')) clearStudyTopicSuggestions(editor);
            });
    }, 150);
    studyTopicEditorRequests.set(editor, state);
}

function initializeStudyTopicEditor(study: StudyPageModel, editor: HTMLElement): void {
    const input = editor.querySelector<HTMLInputElement>('.study-topic-editor__input');
    if (!input || editor.dataset.initialized === 'true') return;
    editor.dataset.initialized = 'true';
    renderStudyTopicEditorChips(study, editor, study.topics);

    input.addEventListener('input', () => {
        const chars = Array.from(input.value);
        if (chars.length > study.topicMaxLength) {
            input.value = chars.slice(0, study.topicMaxLength).join('');
            studyTopicEditorFeedback(editor, _('Topics can have at most %1 characters.', study.topicMaxLength), true);
        } else studyTopicEditorFeedback(editor);
        updateStudyTopicEditorMeta(study, editor);
        requestStudyTopicSuggestions(study, editor, canonicalStudyTopic(input.value));
    });

    input.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ',') {
            event.preventDefault();
            addStudyTopic(study, editor, input.value);
        } else if (event.key === 'Backspace' && !input.value) {
            const chips = editor.querySelectorAll<HTMLElement>('[data-topic-value]');
            chips
                .item(chips.length - 1)
                ?.querySelector<HTMLButtonElement>('button')
                ?.click();
        } else if (event.key === 'Escape') clearStudyTopicSuggestions(editor);
    });

    input.addEventListener('paste', event => {
        const text = event.clipboardData?.getData('text') ?? '';
        if (!/[\n,]/.test(text)) return;
        event.preventDefault();
        for (const raw of text.split(/[\n,]+/)) {
            if (!addStudyTopic(study, editor, raw)) break;
        }
    });
}

function syncStudyTopicEditor(study: StudyPageModel): void {
    const editor = document.querySelector<HTMLElement>('#study-topics .study-topic-editor');
    if (!editor) return;
    renderStudyTopicEditorChips(study, editor, study.topics);
    const input = editor.querySelector<HTMLInputElement>('.study-topic-editor__input');
    if (input) input.value = '';
    studyTopicEditorFeedback(editor);
    clearStudyTopicSuggestions(editor);
    updateStudyTopicEditorMeta(study, editor);
}

function openStudyTopicsDialog(study: StudyPageModel): void {
    const modal = document.querySelector<HTMLDialogElement>('#study-topics');
    if (!modal) return;
    syncStudyTopicEditor(study);
    modal.showModal();
    modal.querySelector<HTMLInputElement>('.study-topic-editor__input')?.focus();
}

async function saveStudyTopics(study: StudyPageModel, form: HTMLFormElement): Promise<void> {
    const editor = form.querySelector<HTMLElement>('.study-topic-editor');
    const input = editor?.querySelector<HTMLInputElement>('.study-topic-editor__input');
    const button = form.querySelector<HTMLButtonElement>('button[type="submit"]');
    if (!editor || !input || !button) return;
    if (input.value.trim() && !addStudyTopic(study, editor, input.value)) {
        input.focus();
        return;
    }
    const topics = studyTopicEditorTopics(editor);
    button.disabled = true;
    try {
        const response = await fetch(`/study/${study.id}/topics`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topics }),
        });
        const payload = (await response.json().catch(() => ({}))) as {
            topics?: unknown;
            error?: unknown;
            message?: unknown;
        };
        if (!response.ok)
            throw new Error(
                typeof payload.message === 'string'
                    ? payload.message
                    : typeof payload.error === 'string'
                      ? payload.error
                      : response.statusText,
            );
        if (!Array.isArray(payload.topics) || !payload.topics.every(topic => typeof topic === 'string'))
            throw new Error(_('Invalid Study topics response'));
        study.topics = payload.topics as string[];
        updateStudyTopicsView(study);
        form.closest<HTMLDialogElement>('dialog')?.close();
    } catch (error) {
        studyTopicEditorFeedback(
            editor,
            _('Could not update Study topics: %1', error instanceof Error ? error.message : String(error)),
            true,
        );
        input.focus();
    } finally {
        button.disabled = false;
    }
}

function studyTopicsDialog(study: StudyPageModel): VNode {
    return dialog('study-topics', _('Topics'), [
        h('p#study-topics-help.study-topics__help', [
            _('Add topics to help people discover this study. Type a topic and press Enter or comma.'),
        ]),
        h(
            'form.study-topics__form',
            {
                on: {
                    submit: event => {
                        event.preventDefault();
                        void saveStudyTopics(study, event.currentTarget as HTMLFormElement);
                    },
                },
            },
            [
                h(
                    'div.study-topic-editor',
                    {
                        hook: {
                            insert: vnode => initializeStudyTopicEditor(study, vnode.elm as HTMLElement),
                        },
                        on: {
                            click: event => {
                                if ((event.target as HTMLElement).closest('button')) return;
                                (event.currentTarget as HTMLElement)
                                    .querySelector<HTMLInputElement>('.study-topic-editor__input')
                                    ?.focus();
                            },
                        },
                    },
                    [
                        h('div.study-topic-editor__selected', { attrs: { role: 'list' } }),
                        h('input.study-topic-editor__input', {
                            attrs: {
                                type: 'text',
                                autocomplete: 'off',
                                maxlength: String(study.topicMaxLength),
                                'aria-label': _('Add Study topic'),
                                'aria-describedby': 'study-topics-help study-topics-feedback',
                                'aria-autocomplete': 'list',
                                'aria-controls': 'study-topic-suggestions',
                                'aria-expanded': 'false',
                            },
                        }),
                        h('div#study-topic-suggestions.study-topic-editor__suggestions', {
                            attrs: { role: 'listbox', hidden: 'true' },
                        }),
                    ],
                ),
                h('div#study-topics-feedback.study-topic-editor__feedback', {
                    attrs: { 'data-topic-feedback': '', 'aria-live': 'polite' },
                }),
                h('div.study-topics__form-actions', [
                    h('span.study-topic-editor__limits', [
                        h('span', { attrs: { 'data-topic-count': '' } }),
                        h('span', { attrs: { 'data-topic-length': '' } }),
                    ]),
                    h('button.button', { attrs: { type: 'submit' } }, _('Save')),
                ]),
            ],
        ),
    ]);
}

function openDialog(id: string): void {
    const modal = document.querySelector<HTMLDialogElement>(`#${id}`);
    if (!modal) return;
    modal.showModal();
    const input = modal.querySelector<HTMLInputElement | HTMLTextAreaElement>('input[type="text"], textarea');
    input?.focus();
    if (input instanceof HTMLInputElement) input.select();
}

function dialog(id: string, title: string, content: VNode[]): VNode {
    return h(
        `dialog#${id}.study-dialog`,
        { attrs: { 'aria-labelledby': `${id}-title` }, on: { keydown: event => event.stopPropagation() } },
        [
            h('div.study-dialog__header', [
                h(`h2#${id}-title`, title),
                h(
                    'button.study-icon-button.study-dialog__close',
                    {
                        attrs: { type: 'button', 'aria-label': _('Close') },
                        on: { click: event => (event.currentTarget as HTMLElement).closest('dialog')?.close() },
                    },
                    '×',
                ),
            ]),
            ...content,
        ],
    );
}

function orderedStudyMembers(study: StudyPageModel): Array<[string, 'read' | 'write']> {
    return Object.entries(study.members).sort(([a, aRole], [b, bRole]) => {
        if (a === study.owner) return -1;
        if (b === study.owner) return 1;
        if (aRole !== bRole) return aRole === 'write' ? -1 : 1;
        return a.localeCompare(b);
    });
}

async function postStudyMemberAction(action: string, fields: Record<string, string>): Promise<void> {
    const response = await fetch(action, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams(fields),
        redirect: 'manual',
    });
    // Successful Study member mutations redirect back to the Study. With manual
    // redirect handling browsers expose that as an opaque redirect, avoiding an
    // unnecessary full-page GET while the websocket delivers the updated member map.
    if (response.type === 'opaqueredirect' || response.ok) return;
    const message = (await response.text()).trim();
    throw new Error(message || response.statusText || _('Could not update Study members'));
}

function reportStudyMemberError(error: unknown): void {
    void alertDialog({
        text: _('Could not update Study members: %1', error instanceof Error ? error.message : String(error)),
    });
}

function studyInviteDialog(study: StudyPageModel): VNode {
    const memberCount = Object.keys(study.members).length;
    return dialog('study-invite', _('Add members'), [
        h('p.study-invite__info', _('Add people you know and trust. New members start as read only.')),
        h(
            'form.study-invite__form',
            {
                attrs: { method: 'post', action: `/study/${study.id}/member` },
                on: {
                    submit: event => {
                        event.preventDefault();
                        const form = event.currentTarget as HTMLFormElement;
                        const input = form.elements.namedItem('username') as HTMLInputElement;
                        const submit = form.querySelector<HTMLButtonElement>('button[type="submit"]');
                        const username = input.value.trim();
                        if (!username) return;
                        if (submit) submit.disabled = true;
                        void postStudyMemberAction(`/study/${study.id}/member`, { username, role: 'read' })
                            .then(() => {
                                input.value = '';
                                form.closest<HTMLDialogElement>('dialog')?.close();
                            })
                            .catch(reportStudyMemberError)
                            .finally(() => {
                                if (submit?.isConnected) submit.disabled = false;
                            });
                    },
                },
            },
            [
                h('input', {
                    attrs: {
                        type: 'text',
                        name: 'username',
                        required: true,
                        maxlength: '20',
                        autocomplete: 'off',
                        placeholder: _('Search by username'),
                        'aria-label': _('Username'),
                    },
                }),
                h('button.button', { attrs: { type: 'submit' } }, _('Add member')),
            ],
        ),
        h('p.study-invite__limit', `${memberCount} / ${study.maxMembers} ${_('members')}`),
    ]);
}

type StudyModeActions = {
    toggleSticky: () => void;
    toggleWrite: () => void;
    requestServerAnalysis: () => void;
    showServerAnalysis: () => void;
    setDescription: (description: string) => void;
    settleWrites: () => Promise<boolean>;
    importPgn: (pgn: string, onProgress?: StudyPgnImportProgressCallback) => Promise<void>;
    resetConcealment: () => Promise<void>;
    enterGamebookPreview: () => Promise<void>;
    leaveGamebookPreview: () => Promise<void>;
    enterGamebookAnalysis: () => Promise<void>;
    leaveGamebookAnalysis: () => Promise<void>;
    enterPracticeAnalysis: () => Promise<void>;
    leavePracticeAnalysis: () => Promise<void>;
};

function studyRecordingKey(studyId: string): string {
    return `study.rec:${studyId}`;
}

function initializeStudyModes(study: StudyPageModel): void {
    if (study.practice) {
        study.sticky = false;
        study.write = false;
        study.behind = 0;
        return;
    }
    if (study.sticky === undefined) study.sticky = study.chapter.id === study.sharedChapter;
    if (study.behind === undefined) study.behind = 0;
    if (study.write === undefined) {
        const stored = localStorage.getItem(studyRecordingKey(study.id));
        study.write = stored !== 'false';
    }
}

function effectiveStudySessionPolicy(study: StudyPageModel): StudySessionPolicy {
    return studySessionPolicy({
        mode: study.chapter.mode ?? 'normal',
        canWrite: study.canWrite,
        computerAllowed: study.features?.computer ?? true,
        savedRecording: Boolean(study.write),
        savedSynchronization: Boolean(study.sticky),
        activeGame: hasActiveEligibleLiveGame(),
        override: study.modeOverride ?? null,
    });
}

function studyModeButtons(study: StudyPageModel, model: PyChessModel, actions: StudyModeActions): VNode[] {
    if (study.practice) return [];
    const policy = effectiveStudySessionPolicy(study);
    const behind = policy.synchronization ? (study.behind ?? 0) : 0;
    const isMember = Boolean(model.username && study.members[model.username]);
    const state = (on: boolean) => h('span.study-mode__state', on ? '✓' : '✕');
    return [
        h(
            'button.study-mode.study-mode--sync',
            {
                class: { on: policy.synchronization },
                attrs: {
                    type: 'button',
                    title: _('All Study members remain on the same position'),
                    'aria-pressed': String(policy.synchronization),
                    disabled: policy.preview,
                    hidden: !isMember,
                },
                on: { click: () => actions.toggleSticky() },
            },
            [behind ? h('span.study-mode__behind', String(behind)) : state(policy.synchronization), 'SYNC'],
        ),
        ...(study.canWrite
            ? [
                  h(
                      'button.study-mode.study-mode--write',
                      {
                          class: { on: policy.recording },
                          attrs: {
                              type: 'button',
                              title: _('Share changes with Study members'),
                              'aria-pressed': String(policy.recording),
                              disabled: policy.preview,
                          },
                          on: { click: () => actions.toggleWrite() },
                      },
                      [state(policy.recording), 'REC'],
                  ),
              ]
            : []),
    ];
}

function studyGamebookPreviewButton(study: StudyPageModel, actions: StudyModeActions): VNode {
    return h(
        'button.study-gamebook-preview-toggle',
        {
            attrs: {
                type: 'button',
                title: _('Preview'),
                'aria-label': _('Preview interactive lesson'),
                hidden: study.chapter.mode !== 'gamebook',
            },
            on: { click: () => void actions.enterGamebookPreview() },
        },
        [
            h('i.study-gamebook-preview-toggle__icon', { attrs: { 'aria-hidden': 'true' } }),
            h('span', _('PREVIEW')),
        ],
    );
}

function studyAnalysisTools(study: StudyPageModel): VNode {
    return h('div.study-gamebook-edit', {
        attrs: { hidden: effectiveStudySessionPolicy(study).session !== 'gamebook-author' },
    });
}

function studyChapterBaseUrl(study: StudyPageModel): string {
    return study.practice?.studyUrl ?? `/study/${study.id}`;
}

function studyChapterUrl(study: StudyPageModel, chapterId: string): string {
    return `${studyChapterBaseUrl(study)}/${chapterId}`;
}

function persistPracticeCompletion(study: StudyPageModel, chapterId: string, bestMoves?: number): void {
    const practice = study.practice;
    if (!practice?.persistProgress) return;
    void fetch(`${practice.studyUrl}/${encodeURIComponent(chapterId)}/complete`, {
        method: 'POST',
        credentials: 'same-origin',
        keepalive: true,
        ...(bestMoves === undefined
            ? {}
            : {
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ bestMoves }),
              }),
    })
        .then(response => {
            if (!response.ok) throw new Error(`Practice progress could not be saved (${response.status}).`);
        })
        .catch(error => console.error('Could not save Practice progress', error));
}

function chapterIdFromStudyUrl(study: StudyPageModel, pathname: string): string | undefined {
    const prefix = `${studyChapterBaseUrl(study)}/`;
    if (!pathname.startsWith(prefix)) return undefined;
    const chapterId = pathname.slice(prefix.length);
    return chapterId && !chapterId.includes('/') ? chapterId : undefined;
}

function studyDocumentTitle(study: StudyPageModel): string {
    if (study.practice?.preview) return `${study.name} • Practice Preview • PyChess`;
    return study.practice ? `${study.name} • Practice • PyChess` : `${study.name} • PyChess`;
}

function nextStudyChapter(study: StudyPageModel): StudyPageModel['chapters'][number] | undefined {
    const chapters = [...study.chapters].sort((a, b) => a.order - b.order);
    const current = chapters.findIndex(chapter => chapter.id === study.chapter.id);
    return current >= 0 ? chapters[current + 1] : undefined;
}

function studyMoveIndex(ply: number): string {
    return `${Math.ceil(ply / 2)}${ply % 2 === 1 ? '.' : '...'}`;
}

export function renderStudyMoveListEnd(
    study: StudyPageModel,
    ctrl: AnalysisController,
    goToChapter: (chapterId: string) => void,
): VNode[] {
    if (!effectiveStudySessionPolicy(study).tools.fullTree) return [];

    const nextChapter = nextStudyChapter(study);
    if (!nextChapter) return [];
    return [
        h(
            'button.study-next-chapter',
            {
                class: { highlighted: ctrl.analysisPath === ctrl.getTreeMainlineEndPath() },
                attrs: { type: 'button', title: nextChapter.name },
                on: { click: () => goToChapter(nextChapter.id) },
            },
            [icon('play'), h('span', _('Next chapter'))],
        ),
    ];
}

export function renderStudyMoveListFooter(study: StudyPageModel, ctrl: AnalysisController): VNode[] {
    if (!effectiveStudySessionPolicy(study).tools.fullTree) return [];

    const current = ctrl.getTreeNodeAtPath(ctrl.analysisPath ?? '');
    const forks =
        current?.children.filter(child => ctrl.analysisExtension?.isTreeNodeVisible?.(child) !== false) ?? [];
    if (forks.length <= 1) return [];

    const selectedPath = ctrl.getTreeMainChildPath();
    return [
        h(
            'div.study-move-fork',
            forks.map(child =>
                h(
                    'button.study-move-fork__move',
                    {
                        class: { selected: child.path === selectedPath },
                        attrs: { type: 'button', 'data-path': child.path },
                        on: {
                            click: () => ctrl.activateTreePath(child.path),
                            mouseenter: () => {
                                if (window.matchMedia('(hover: hover) and (pointer: fine)').matches)
                                    ctrl.setVariationHover(child.step.move);
                            },
                            mouseleave: () => ctrl.setVariationHover(),
                        },
                    },
                    [
                        h('span.study-move-fork__index', studyMoveIndex(child.ply)),
                        h('span.study-move-fork__san', child.step.san ?? child.step.sanSAN ?? child.step.move ?? '?'),
                    ],
                ),
            ),
        ),
    ];
}

function refreshStudyModeButtons(study: StudyPageModel): void {
    const policy = effectiveStudySessionPolicy(study);
    const update = (selector: string, on: boolean, behind = 0): void => {
        const button = document.querySelector<HTMLButtonElement>(`.study-tool-tabs > ${selector}`);
        if (!button) return;
        button.classList.toggle('on', on);
        button.setAttribute('aria-pressed', String(on));
        button.disabled = policy.preview;
        const indicator = button.querySelector<HTMLSpanElement>('.study-mode__state, .study-mode__behind');
        if (!indicator) return;
        indicator.className = behind ? 'study-mode__behind' : 'study-mode__state';
        indicator.textContent = behind ? String(behind) : on ? '✓' : '✕';
    };
    update('.study-mode--sync', policy.synchronization, policy.synchronization ? (study.behind ?? 0) : 0);
    update('.study-mode--write', policy.recording);
}

function isGamebookPlayback(policy: StudySessionPolicy): boolean {
    return policy.session === 'gamebook-play' || policy.session === 'gamebook-preview';
}

function isPracticePlayback(policy: StudySessionPolicy): boolean {
    return policy.session === 'practice-play';
}

function syncStudyPlaybackUi(study: StudyPageModel, modeActions: StudyModeActions): void {
    const policy = effectiveStudySessionPolicy(study);
    const app = document.querySelector<HTMLElement>('.study-app');
    app?.classList.toggle('study-conceal-playback', isConcealPlayback(policy));
    app?.classList.toggle('study-gamebook-playback', isGamebookPlayback(policy));
    app?.classList.toggle('study-gamebook-preview', policy.session === 'gamebook-preview');
    app?.classList.toggle('study-gamebook-analysis', policy.session === 'gamebook-analysis');
    app?.classList.toggle('study-practice-playback', isPracticePlayback(policy));
    app?.classList.toggle('study-practice-analysis', policy.session === 'practice-analysis');
    const selected = document.querySelector<HTMLButtonElement>('[data-study-tab][aria-selected="true"]');
    const serverEval = document.querySelector<HTMLButtonElement>('#study-tab-serverEval');
    const hideServerEval = !policy.tools.evaluationDisplay && !policy.tools.serverAnalysis;
    if (serverEval) serverEval.hidden = hideServerEval;
    if (isGamebookPlayback(policy) || isPracticePlayback(policy)) {
        if (selected && selected.dataset.studyTab !== 'tags') selectStudyTab('tags');
    } else if (hideServerEval && selected?.dataset.studyTab === 'serverEval') {
        // Conceal readers cannot use evaluation surfaces. Do not leave them on
        // an empty tool panel when changing from a normal chapter.
        selectStudyTab('tags');
    }
    refreshStudyModeButtons(study);
    updateStudyGamebookStatus(study, modeActions);
}

type StudySideTab = 'chapters' | 'members';

function selectStudySideTab(study: StudyPageModel, tab: StudySideTab, focus = false): void {
    study.sideTab = tab;
    const side = document.querySelector<HTMLElement>('.study-side');
    if (!side) return;
    side.querySelectorAll<HTMLButtonElement>('[data-study-side-tab]').forEach(button => {
        const selected = button.dataset.studySideTab === tab;
        button.classList.toggle('active', selected);
        button.setAttribute('aria-selected', String(selected));
        button.tabIndex = selected ? 0 : -1;
        if (selected && focus) button.focus();
    });
    side.querySelectorAll<HTMLElement>('[data-study-side-panel]').forEach(panel => {
        panel.hidden = panel.dataset.studySidePanel !== tab;
    });
    notifyChessgroundResize();
}

function studySideTabButton(study: StudyPageModel, tab: StudySideTab, label: string): VNode {
    const selected = (study.sideTab ?? 'chapters') === tab;
    return h(
        `button#study-side-tab-${tab}.study-side__tab`,
        {
            class: { active: selected },
            attrs: {
                type: 'button',
                role: 'tab',
                'aria-controls': `study-side-panel-${tab}`,
                'aria-selected': selected ? 'true' : 'false',
                tabindex: selected ? 0 : -1,
                'data-study-side-tab': tab,
            },
            on: {
                click: () => selectStudySideTab(study, tab),
                keydown: event => {
                    let next: StudySideTab | undefined;
                    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight')
                        next = tab === 'chapters' ? 'members' : 'chapters';
                    else if (event.key === 'Home') next = 'chapters';
                    else if (event.key === 'End') next = 'members';
                    if (!next) return;
                    event.preventDefault();
                    selectStudySideTab(study, next, true);
                },
            },
        },
        label,
    );
}

function selectStudyMemberConfig(study: StudyPageModel, username?: string): void {
    study.memberConfig = username && study.memberConfig !== username ? username : undefined;
    const side = document.querySelector<HTMLElement>('.study-side');
    if (!side) return;
    side.querySelectorAll<HTMLElement>('[data-study-member]').forEach(row => {
        row.classList.toggle('editing', row.dataset.studyMember === study.memberConfig);
    });
    side.querySelectorAll<HTMLButtonElement>('[data-study-member-config-button]').forEach(button => {
        button.setAttribute('aria-expanded', String(button.dataset.studyMemberConfigButton === study.memberConfig));
    });
    side.querySelectorAll<HTMLElement>('[data-study-member-config]').forEach(panel => {
        panel.hidden = panel.dataset.studyMemberConfig !== study.memberConfig;
    });
}

function studyMemberConfig(study: StudyPageModel, username: string, role: 'read' | 'write'): VNode {
    const contributor = role === 'write';
    return h(
        `div#study-member-config-${username}.study-members-side__config-panel`,
        {
            attrs: {
                'data-study-member-config': username,
                hidden: study.memberConfig !== username,
            },
        },
        [
            h('div.study-members-side__role-control', [
                h('label.switch', [
                    h('input', {
                        props: { type: 'checkbox', checked: contributor },
                        attrs: { 'aria-label': _('Contributor') },
                        on: {
                            change: event => {
                                const input = event.currentTarget as HTMLInputElement;
                                const nextRole = input.checked ? 'write' : 'read';
                                input.disabled = true;
                                selectStudyMemberConfig(study);
                                void postStudyMemberAction(`/study/${study.id}/member/role`, {
                                    username,
                                    role: nextRole,
                                }).catch(error => {
                                    input.checked = contributor;
                                    reportStudyMemberError(error);
                                });
                            },
                        },
                    }),
                    h('span.sw-slider'),
                ]),
                h('span', _('Contributor')),
            ]),
            h(
                'button.study-members-side__kick',
                {
                    attrs: {
                        type: 'button',
                        title: _('Remove %1 from this Study', username),
                        'aria-label': _('Remove %1 from this Study', username),
                    },
                    on: {
                        click: event => {
                            const button = event.currentTarget as HTMLButtonElement;
                            button.disabled = true;
                            selectStudyMemberConfig(study);
                            void postStudyMemberAction(`/study/${study.id}/member/remove`, { username }).catch(
                                error => {
                                    if (button.isConnected) button.disabled = false;
                                    reportStudyMemberError(error);
                                },
                            );
                        },
                    },
                },
                [h('span.study-members-side__kick-icon', { attrs: { 'aria-hidden': 'true' } }, '✖'), _('KICK')],
            ),
        ],
    );
}

function studyMembersSide(study: StudyPageModel, model: PyChessModel): VNode {
    const members = orderedStudyMembers(study);
    const myRole = model.username ? study.members[model.username] : undefined;
    const roleLabel = (username: string, role: 'read' | 'write') =>
        username === study.owner ? _('Owner') : role === 'write' ? _('Contributor') : _('Read only');

    if (study.memberConfig && !study.members[study.memberConfig]) study.memberConfig = undefined;

    return h('div.study-members-side', [
        h(
            'div.study-members-side__list',
            members.flatMap(([username, role]) => {
                const configurable = study.isOwner && username !== study.owner;
                const editing = study.memberConfig === username;
                return [
                    h(
                        'div.study-members-side__member',
                        {
                            class: { editing },
                            attrs: { 'data-study-member': username },
                        },
                        [
                            h('div.study-members-side__identity', [
                                h(
                                    `span.study-members-side__status.study-members-side__status--${role}`,
                                    {
                                        class: { current: username === model.username },
                                        attrs: {
                                            role: 'img',
                                            title: roleLabel(username, role),
                                            'aria-label': roleLabel(username, role),
                                        },
                                    },
                                    [h('i.study-members-side__role-icon', { attrs: { 'aria-hidden': 'true' } })],
                                ),
                                h('a', { attrs: { href: `/@/${username}` } }, username),
                            ]),
                            ...(configurable
                                ? [
                                      h(
                                          'button.study-icon-button.study-members-side__config',
                                          {
                                              attrs: {
                                                  type: 'button',
                                                  title: _('Manage %1', username),
                                                  'aria-label': _('Manage %1', username),
                                                  'aria-controls': `study-member-config-${username}`,
                                                  'aria-expanded': editing ? 'true' : 'false',
                                                  'data-study-member-config-button': username,
                                              },
                                              on: { click: () => selectStudyMemberConfig(study, username) },
                                          },
                                          [icon('cog')],
                                      ),
                                  ]
                                : []),
                        ],
                    ),
                    ...(configurable ? [studyMemberConfig(study, username, role)] : []),
                ];
            }),
        ),
        ...(study.isOwner && members.length < study.maxMembers
            ? [
                  h(
                      'button.study-side__add.study-members-side__add',
                      {
                          attrs: { type: 'button' },
                          on: { click: () => openDialog('study-invite') },
                      },
                      [icon('plus-square'), _('Add members')],
                  ),
              ]
            : []),
        ...(!study.isOwner && myRole
            ? [
                  h(
                      'form.study-members-side__leave',
                      {
                          attrs: { method: 'post', action: `/study/${study.id}/leave` },
                          on: {
                              submit: event => {
                                  event.preventDefault();
                                  const form = event.currentTarget as HTMLFormElement;
                                  void confirmDialog({
                                      text: _('Leave this Study?'),
                                      confirmText: _('Leave study'),
                                      cancelText: _('Cancel'),
                                      danger: true,
                                  }).then(confirmed => {
                                      if (confirmed) HTMLFormElement.prototype.submit.call(form);
                                  });
                              },
                          },
                      },
                      [h('button.button.button-empty', { attrs: { type: 'submit' } }, _('Leave study'))],
                  ),
              ]
            : []),
    ]);
}

function practiceStudySide(study: StudyPageModel, progress?: StudyPracticeProgress): VNode {
    const practice = study.practice!;
    const preview = Boolean(practice.preview);
    const chapters = [...study.chapters].sort((a, b) => a.order - b.order);

    const chapterNodes = chapters.map(item => {
        const active = item.id === study.chapter.id;
        const completed = Boolean(progress?.isComplete(item.id));
        const statusLabel = completed ? _('Completed') : active ? _('Current chapter') : _('Not completed');
        return h(
            'a.practice-study-chapter',
            {
                key: item.id,
                class: { active, completed },
                attrs: {
                    href: studyChapterUrl(study, item.id),
                    'aria-current': active ? 'page' : 'false',
                    'data-study-chapter-id': item.id,
                },
            },
            [
                h(
                    'span.practice-study-chapter__status',
                    { attrs: { title: statusLabel, 'aria-label': statusLabel } },
                    completed ? '✓' : active ? '▶' : '✓',
                ),
                h('h3.practice-study-chapter__name', item.name),
            ],
        );
    });

    return h('div.study-side.practice-study-side', [
        h('div.practice-study-side__title', [
            h('img.practice-study-side__icon', {
                attrs: {
                    src: `/static/images/practice/${practice.studyIcon}.svg`,
                    alt: '',
                    'aria-hidden': 'true',
                },
            }),
            h('div.practice-study-side__title-text', [
                h('h1', practice.studyTitle),
                ...(practice.studyDescription ? [h('em', practice.studyDescription)] : []),
            ]),
        ]),
        h('nav.practice-study-side__chapters', { attrs: { 'aria-label': _('Practice chapters') } }, chapterNodes),
        h('div.practice-study-side__footer', [
            h(
                'a.practice-study-side__back',
                {
                    attrs: {
                        href: practice.indexUrl,
                        title: preview ? _('Back to Study') : _('More practice'),
                        'aria-label': preview ? _('Back to Study') : _('More practice'),
                    },
                },
                '‹',
            ),
            ...(practice.menu.length
                ? [
                      h(
                          'select.practice-study-side__selector',
                          {
                              attrs: { 'aria-label': _('Practice list') },
                              on: {
                                  change: event => {
                                      const target = event.currentTarget as HTMLSelectElement;
                                      if (target.value) window.location.href = target.value;
                                  },
                              },
                          },
                          [
                              h('option', { attrs: { disabled: true } }, _('Practice list')),
                              ...practice.menu.map(section =>
                                  h(
                                      'optgroup',
                                      { attrs: { label: section.name } },
                                      section.studies.map(item =>
                                          h(
                                              'option',
                                              {
                                                  attrs: {
                                                      value: item.url,
                                                      selected: item.id === study.id,
                                                  },
                                              },
                                              item.name,
                                          ),
                                      ),
                                  ),
                              ),
                          ],
                      ),
                  ]
                : [
                      h(
                          'span.practice-study-side__preview-label',
                          preview ? _('Practice Preview') : practice.sectionName,
                      ),
                  ]),
        ]),
    ]);
}

function studySide(
    study: StudyPageModel,
    model: PyChessModel,
    modeActions: StudyModeActions,
    practiceProgress?: StudyPracticeProgress,
): VNode {
    if (study.practice) return practiceStudySide(study, practiceProgress);
    const chapter = study.chapter;
    // Lichess keeps structural chapter management tied to Study membership,
    // even while a writable member is in a disposable training/playback session.
    const canManageChapters = study.canWrite;
    const activeTab = study.sideTab ?? 'chapters';
    const memberCount = Object.keys(study.members).length;
    return h('div.study-side', [
        h('div.study-side__tabs', { attrs: { role: 'tablist', 'aria-label': _('Study navigation') } }, [
            studySideTabButton(study, 'chapters', ngettext('%1 chapter', '%1 chapters', study.chapters.length)),
            studySideTabButton(study, 'members', ngettext('%1 member', '%1 members', memberCount)),
            ...(study.isOwner
                ? [
                      h(
                          'button.study-icon-button.study-side__more',
                          {
                              attrs: { type: 'button', title: _('Edit study'), 'aria-label': _('Edit study') },
                              on: { click: () => openDialog('study-settings') },
                          },
                          [icon('bars')],
                      ),
                  ]
                : []),
        ]),
        h(
            'section#study-side-panel-chapters.study-side__panel',
            {
                attrs: {
                    role: 'tabpanel',
                    'aria-labelledby': 'study-side-tab-chapters',
                    'data-study-side-panel': 'chapters',
                    hidden: activeTab !== 'chapters',
                },
            },
            [
                h(
                    'nav.study-chapters',
                    { attrs: { 'aria-label': _('Chapters') } },
                    study.chapters.map(item =>
                        h('div.study-chapter__row', { class: { active: item.id === chapter.id } }, [
                            h(
                                'a',
                                {
                                    attrs: {
                                        href: studyChapterUrl(study, item.id),
                                        'aria-current': item.id === chapter.id ? 'page' : 'false',
                                        'data-study-chapter-id': item.id,
                                    },
                                },
                                [
                                    h('span.study-chapter__number', `${item.order}. `),
                                    h('span.study-chapter__name', item.name),
                                    ...(item.status ? [h('span.study-chapter__result', item.status)] : []),
                                ],
                            ),
                            ...(canManageChapters
                                ? [
                                      h(
                                          'button.study-icon-button.study-chapter__edit',
                                          {
                                              attrs: {
                                                  type: 'button',
                                                  title: _('Edit chapter'),
                                                  'aria-label': _('Edit chapter: %1', item.name),
                                              },
                                              on: { click: () => openDialog(`chapter-settings-${item.id}`) },
                                          },
                                          [icon('cog')],
                                      ),
                                  ]
                                : []),
                        ]),
                    ),
                ),
                ...(canManageChapters
                    ? [
                          h(
                              'button.study-side__add',
                              {
                                  attrs: { type: 'button' },
                                  on: { click: () => openDialog('study-new-chapter') },
                              },
                              [icon('plus-square'), _('Add a new chapter')],
                          ),
                          ...(study.canPreviewPractice
                              ? [
                                    h(
                                        'a.study-side__add.study-practice-preview',
                                        {
                                            attrs: {
                                                href: `/practice/preview/${study.id}/${chapter.id}`,
                                                title: _('Preview this Study as a Practice learner'),
                                            },
                                        },
                                        [icon('play'), _('Preview in Practice')],
                                    ),
                                ]
                              : []),
                      ]
                    : []),
            ],
        ),
        h(
            'section#study-side-panel-members.study-side__panel',
            {
                attrs: {
                    role: 'tabpanel',
                    'aria-labelledby': 'study-side-tab-members',
                    'data-study-side-panel': 'members',
                    hidden: activeTab !== 'members',
                },
            },
            [studyMembersSide(study, model)],
        ),
        ...(study.isOwner
            ? [
                  dialog('study-settings', _('Edit study'), [
                      studySettingsForm(study, 'study-settings-form'),
                      dialogActions(
                          'study-settings-form',
                          _('Save'),
                          deleteForm(
                              `/study/${study.id}/delete`,
                              _('Delete study'),
                              _('Delete this study?'),
                              'study-side__danger',
                          ),
                      ),
                  ]),
              ]
            : []),
        ...(canManageChapters
            ? [
                  studyTopicsDialog(study),
                  ...study.chapters.map(item =>
                      dialog(`chapter-settings-${item.id}`, _('Edit chapter'), [
                          chapterSettingsForm(
                              study,
                              item,
                              `chapter-settings-form-${item.id}`,
                              modeActions.settleWrites,
                          ),
                          h('div.study-dialog__secondary-actions', [
                              deleteForm(
                                  `/study/${study.id}/${item.id}/clear-annotations`,
                                  _('Clear annotations'),
                                  _('Clear all comments, drawings, glyphs, hints and lesson instructions in this chapter?'),
                              ),
                              deleteForm(
                                  `/study/${study.id}/${item.id}/clear-variations`,
                                  _('Clear variations'),
                                  _('Clear variations?'),
                              ),
                              ...(item.id === study.chapter.id && item.mode === 'conceal'
                                  ? [
                                        h(
                                            'button.button.button-empty',
                                            {
                                                attrs: { type: 'button' },
                                                on: {
                                                    click: () => {
                                                        void (async () => {
                                                            const confirmed = await confirmDialog({
                                                                title: _('Hide moves again'),
                                                                confirmText: _('Hide moves again'),
                                                                cancelText: _('Cancel'),
                                                                text: _(
                                                                    'Hide all moves and return the shared position to the start?',
                                                                ),
                                                            });
                                                            if (confirmed) await modeActions.resetConcealment();
                                                        })();
                                                    },
                                                },
                                            },
                                            _('Hide moves again'),
                                        ),
                                    ]
                                  : []),
                          ]),
                          dialogActions(
                              `chapter-settings-form-${item.id}`,
                              _('Save chapter'),
                              study.chapters.length > 1
                                  ? deleteForm(
                                        `/study/${study.id}/${item.id}/delete`,
                                        _('Delete chapter'),
                                        _('Delete this chapter?'),
                                    )
                                  : undefined,
                          ),
                      ]),
                  ),
                  dialog('study-new-chapter', _('Add a new chapter'), [
                      studyChapterCreateForm(
                          `/study/${study.id}/chapter`,
                          model.variant || 'chess',
                          {
                              orientation: study.chapter.orientation,
                              enabledModes: study.enabledModes,
                              sync: () => Boolean(study.sticky),
                              beforeSubmit: modeActions.settleWrites,
                              pgnImport: pgn => modeActions.importPgn(pgn),
                          },
                      ),
                  ]),
              ]
            : []),
        ...(study.isOwner && Object.keys(study.members).length < study.maxMembers ? [studyInviteDialog(study)] : []),
    ]);
}

type StudyTab = 'tags' | 'comments' | 'glyphs' | 'serverEval' | 'export';

function selectStudyTab(tab: string, focus = false): void {
    const requested = document.querySelector<HTMLButtonElement>(`[data-study-tab="${tab}"]`);
    if (requested?.hidden) tab = 'tags';
    document.querySelectorAll<HTMLButtonElement>('[data-study-tab]').forEach(button => {
        const selected = button.dataset.studyTab === tab;
        button.setAttribute('aria-selected', String(selected));
        button.tabIndex = selected ? 0 : -1;
        if (selected && focus) button.focus();
    });
    document.querySelectorAll<HTMLElement>('[data-study-panel]').forEach(panel => {
        panel.hidden = panel.dataset.studyPanel !== tab;
    });
    notifyChessgroundResize();
}

function toolPanel(tab: StudyTab, children: VNode[], selected: StudyTab = 'tags'): VNode {
    return h(
        `section#study-panel-${tab}.study-tool-panel`,
        {
            attrs: {
                role: 'tabpanel',
                'aria-labelledby': `study-tab-${tab}`,
                'data-study-panel': tab,
                hidden: tab !== selected,
            },
        },
        children,
    );
}

function studyPreferredMainlineLength(study: StudyPageModel): number {
    let parentId: string | null = null;
    let length = 0;
    while (true) {
        const children = study.chapter.tree.nodes
            .filter(node => node.parentId === parentId)
            .sort((a, b) => a.order - b.order);
        const next = children[0];
        if (!next || next.forceVariation) return length;
        length += 1;
        parentId = next.id;
    }
}

function studyServerAnalysisError(reason: string | undefined): string | undefined {
    if (!reason) return undefined;
    if (reason === 'fishnet_unavailable') return _('No Fishnet worker is available right now.');
    if (reason === 'variant_unavailable') return _('This chapter variant cannot be analysed on the server.');
    if (reason === 'too_short') return _('The chapter is too short to be analysed.');
    if (reason === 'forbidden') return _('Only contributors can request analysis.');
    if (reason === 'fishnet_failed') return _('Server analysis failed. You can request it again.');
    if (reason === 'already_requested') return _('Server analysis was requested recently. Try again in a few minutes.');
    if (reason === 'concurrent_analysis') return _('You already have a Study analysis in progress.');
    if (reason === 'daily_limit') return _('You have reached the daily Study analysis limit.');
    if (reason === 'weekly_limit') return _('You have reached the weekly Study analysis limit.');
    if (reason === 'not_found') return _('The chapter is no longer available.');
    return _('Server analysis is unavailable right now.');
}

function studyServerEvalContent(study: StudyPageModel, modeActions: StudyModeActions): VNode {
    const serverEval = study.chapter.serverEval;
    const hasAnalysis = Boolean(serverEval?.analysis.some(step => step !== null));
    const error = studyServerAnalysisError(study.serverAnalysisError);
    const content: VNode[] = [];
    if (error) content.push(h('p.study-server-eval__error', error));

    if (hasAnalysis) content.push(h('div#study-server-analysis-chart.study-server-eval__chart'));

    if (serverEval && !serverEval.done && serverEval.pending) {
        content.push(
            h('div.study-server-eval__progress', [
                h('span.study-server-eval__spinner', { attrs: { 'aria-hidden': 'true' } }),
                h('span', hasAnalysis ? _('Server analysis in progress…') : _('Server analysis requested…')),
            ]),
        );
        return h('div.study-server-eval__content', content);
    }

    if (serverEval?.done && hasAnalysis) return h('div.study-server-eval__content', content);

    if (studyPreferredMainlineLength(study) < 5) {
        content.push(h('p', _('The chapter is too short to be analysed.')));
    } else if (!study.canWrite) {
        content.push(h('p', _('Only contributors can request analysis.')));
    } else {
        content.push(
            h('p', [
                _('Get a full computer analysis of the chapter.'),
                h('br'),
                _('Make sure the chapter is complete before requesting it.'),
            ]),
            h(
                'button.button.study-server-eval__request',
                { attrs: { type: 'button' }, on: { click: () => modeActions.requestServerAnalysis() } },
                [icon('bar-chart'), h('span', _('Request computer analysis'))],
            ),
        );
    }
    return h('div.study-server-eval__content', content);
}

function updateStudyServerEvalContent(study: StudyPageModel, modeActions?: StudyModeActions): void {
    const content = document.querySelector<HTMLElement>('.study-server-eval__content');
    if (!content || !modeActions) return;
    patch(toVNode(content), studyServerEvalContent(study, modeActions));
    const panel = document.getElementById('study-panel-serverEval');
    if (panel && !panel.hidden) requestAnimationFrame(() => modeActions.showServerAnalysis());
}

function studyShareLinks(study: StudyPageModel, model: PyChessModel): VNode {
    const studyUrl = `${model.home}/study/${study.id}`;
    const chapterUrl = `${model.home}/study/${study.id}/${study.chapter.id}`;
    const embedUrl = `${model.home}/study/embed/${study.id}/${study.chapter.id}`;
    const embedCode = `<iframe width="600" height="371" src="${embedUrl}" frameborder="0"></iframe>`;
    const shareLink = (label: string, value: string, options: { disabled?: boolean; copyLabel?: string } = {}) =>
        h('label.study-share__link', [
            h('span', label),
            h('span.study-share__copy', [
                h('input', {
                    attrs: {
                        type: 'text',
                        value,
                        readonly: true,
                        ...(options.disabled ? { disabled: true } : {}),
                    },
                }),
                h(
                    'button.button.button-empty',
                    {
                        attrs: {
                            type: 'button',
                            title: options.copyLabel ?? _('Copy link'),
                            'aria-label': options.copyLabel ?? _('Copy link'),
                            ...(options.disabled ? { disabled: true } : {}),
                        },
                        on: { click: () => copyTextToClipboard(value) },
                    },
                    [icon('clipboard')],
                ),
            ]),
        ]);

    return h('div.study-share__links', [
        shareLink(_('Study link'), studyUrl),
        shareLink(_('Current chapter link'), chapterUrl),
        shareLink(
            _('Embed this chapter'),
            studyCanEmbed(study)
                ? embedCode
                : study.visibility === 'private'
                  ? _('Private Studies cannot be embedded.')
                  : _('Embedding is disabled by the Study sharing settings.'),
            {
                disabled: !studyCanEmbed(study),
                copyLabel: _('Copy embed code'),
            },
        ),
        ...(study.visibility === 'private'
            ? [h('p.study-share__private', _('This Study is private. Only authorized members can open these links.'))]
            : []),
    ]);
}

const EMPTY_PINNED_CHAPTER_COMMENT = '-';

function pinnedChapterCommentTitle(): string {
    return _('Pinned chapter comment');
}

function studyPinnedChapterComment(study: StudyPageModel, modeActions: StudyModeActions): VNode {
    const description = study.chapter.description;
    const editing = Boolean(study.chapterDescriptionEditing);
    const empty = description === EMPTY_PINNED_CHAPTER_COMMENT;
    let content: VNode | undefined;

    if (editing && study.canWrite) {
        content = h('div.study-desc-form', [
            h('div.title', [
                h('span', pinnedChapterCommentTitle()),
                h(
                    'button.button.button-empty.button-green',
                    {
                        attrs: { type: 'button', title: _('Save and close'), 'aria-label': _('Save and close') },
                        on: {
                            click: () => {
                                study.chapterDescriptionEditing = false;
                                redrawStudyPinnedChapterComment(study, modeActions);
                            },
                        },
                    },
                    [icon('check')],
                ),
            ]),
            h('textarea', {
                attrs: { maxlength: '10000', 'aria-label': pinnedChapterCommentTitle() },
                hook: {
                    insert: vnode => {
                        const textarea = vnode.elm as HTMLTextAreaElement;
                        textarea.value = empty ? '' : description;
                        textarea.focus();
                    },
                },
                on: {
                    input: event =>
                        modeActions.setDescription((event.currentTarget as HTMLTextAreaElement).value.trim()),
                },
            }),
        ]);
    } else if (description && (!empty || study.canWrite)) {
        content = h(`div.study-desc.chapter-desc${empty ? '.empty' : ''}`, [
            ...(study.canWrite && !empty
                ? [
                      h('div.contrib', [
                          h('span', pinnedChapterCommentTitle()),
                          h(
                              'button.study-desc__action',
                              {
                                  attrs: { type: 'button', title: _('Edit'), 'aria-label': _('Edit') },
                                  on: {
                                      click: () => {
                                          study.chapterDescriptionEditing = true;
                                          redrawStudyPinnedChapterComment(study, modeActions);
                                      },
                                  },
                              },
                              [icon('pencil')],
                          ),
                          h(
                              'button.study-desc__action',
                              {
                                  attrs: { type: 'button', title: _('Delete'), 'aria-label': _('Delete') },
                                  on: {
                                      click: () => {
                                          void confirmDialog({
                                              text: _('Delete permanent description?'),
                                              confirmText: _('Delete'),
                                              cancelText: _('Cancel'),
                                              danger: true,
                                          }).then(confirmed => {
                                              if (!confirmed) return;
                                              study.chapterDescriptionEditing = false;
                                              modeActions.setDescription('');
                                          });
                                      },
                                  },
                              },
                              [icon('trash-o')],
                          ),
                      ]),
                  ]
                : []),
            empty
                ? h(
                      'button.text.button',
                      {
                          attrs: { type: 'button' },
                          on: {
                              click: () => {
                                  study.chapterDescriptionEditing = true;
                                  redrawStudyPinnedChapterComment(study, modeActions);
                              },
                          },
                      },
                      pinnedChapterCommentTitle(),
                  )
                : h('div.text', renderLinkifiedText(description)),
        ]);
    }

    return h('div.study-desc-slot', content ? [content] : []);
}

function redrawStudyPinnedChapterComment(study: StudyPageModel, modeActions: StudyModeActions): void {
    const slot = document.querySelector<HTMLElement>('.study-desc-slot');
    if (slot) patch(toVNode(slot), studyPinnedChapterComment(study, modeActions));
}

function syncStudyPinnedDescriptionUi(study: StudyPageModel, modeActions?: StudyModeActions): void {
    const pinned = Boolean(study.chapter.description);
    const preview = study.chapters.find(chapter => chapter.id === study.chapter.id);
    if (preview) preview.descriptionPinned = pinned;
    const pinnedSelect = document.querySelector<HTMLSelectElement>(
        `#chapter-settings-${study.chapter.id} select[name="description"]`,
    );
    if (pinnedSelect) pinnedSelect.value = pinned ? '1' : '';
    if (modeActions && !study.chapterDescriptionEditing) redrawStudyPinnedChapterComment(study, modeActions);
}

function studyTag(study: StudyPageModel, name: string): string | undefined {
    const expected = name.toLowerCase();
    const entry = Object.entries(study.chapter.tags).find(([key]) => key.toLowerCase() === expected);
    return entry?.[1];
}

function studyChapterStatusFromTags(tags: Record<string, string>): StudyPageModel['chapters'][number]['status'] {
    const result = Object.entries(tags).find(([key]) => key.toLowerCase() === 'result')?.[1]?.trim();
    if (result === '1/2-1/2') return '½-½';
    return result === '1-0' || result === '0-1' || result === '½-½' || result === '*' ? result : undefined;
}

function studyHasGamePlayers(study: StudyPageModel): boolean {
    return Boolean(studyTag(study, 'White') && studyTag(study, 'Black'));
}

function studyPlayerIdentity(study: StudyPageModel, color: 'white' | 'black'): VNode {
    const prefix = color === 'white' ? 'White' : 'Black';
    const username = studyTag(study, prefix) ?? '?';
    const title = studyTag(study, `${prefix}Title`);
    const rating = studyTag(study, `${prefix}Elo`);
    const shownRating = rating && /^\d+\??$/.test(rating) ? rating : undefined;
    // Like lila's playerBars, show each player's share of the final result.
    const gameResult = studyTag(study, 'Result');
    const score =
        gameResult && /^(1-0|0-1|1\/2-1\/2|½-½)$/.test(gameResult)
            ? gameResult.split('-')[color === 'white' ? 0 : 1].replace('1/2', '½')
            : undefined;
    const name = displayUsername(username);
    const playerName =
        study.chapter.source?.kind === 'game' ? userLink(username, name, { className: 'name' }) : h('span.name', name);
    return h('div.left', [
        ...(score ? [h(`${score === '1' ? 'good' : score === '0' ? 'bad' : 'span'}.result`, score)] : []),
        h('span.info', [
            ...(title ? [h('player-title', title)] : []),
            playerName,
            ...(shownRating ? [h('span.elo', shownRating)] : []),
        ]),
    ]);
}

function studyPlayerColorAt(
    study: StudyPageModel,
    placement: 'top' | 'bottom',
    orientation = study.chapter.orientation,
) {
    if (placement === 'bottom') return orientation;
    return orientation === 'white' ? 'black' : 'white';
}

function studyHasClockData(study: StudyPageModel): boolean {
    return Boolean(study.chapter.tree.rootClocks || study.chapter.tree.nodes.some(node => node.clocks));
}

function studyPlayerBar(
    study: StudyPageModel,
    placement: 'top' | 'bottom',
    orientation = study.chapter.orientation,
): VNode {
    const clockId = placement === 'top' ? 'anal-clock-top' : 'anal-clock-bottom';
    const clock = studyHasClockData(study)
        ? h(`div#${clockId}.anal-clock.${placement}`, '-')
        : h(`div#${clockId}.study__player-clock-placeholder`);
    return h(`div.study__player.study__player-${placement === 'bottom' ? 'bot' : 'top'}`, [
        studyPlayerIdentity(study, studyPlayerColorAt(study, placement, orientation)),
        clock,
    ]);
}

function studyBoardParts(study: StudyPageModel): { boardTop?: VNode; boardBottom?: VNode } {
    return studyHasGamePlayers(study)
        ? { boardTop: studyPlayerBar(study, 'top'), boardBottom: studyPlayerBar(study, 'bottom') }
        : {};
}

function updateStudyPlayerIdentities(study: StudyPageModel, orientation: 'white' | 'black'): void {
    if (!studyHasGamePlayers(study)) return;
    const top = document.querySelector<HTMLElement>('.study__player-top > .left');
    const bottom = document.querySelector<HTMLElement>('.study__player-bot > .left');
    if (top) patch(toVNode(top), studyPlayerIdentity(study, studyPlayerColorAt(study, 'top', orientation)));
    if (bottom) patch(toVNode(bottom), studyPlayerIdentity(study, studyPlayerColorAt(study, 'bottom', orientation)));
}

function studyGamebookStatus(study: StudyPageModel, modeActions: StudyModeActions): VNode {
    const policy = effectiveStudySessionPolicy(study);
    if (study.chapter.mode === 'gamebook' && policy.session === 'gamebook-analysis') {
        return h('div.study-gamebook-status-container', [
            h('div.study-gamebook-status', [
                h('span', _('You are analysing this interactive lesson outside playback.')),
                h(
                    'button.button.button-empty.study-gamebook-return',
                    { attrs: { type: 'button' }, on: { click: () => void modeActions.leaveGamebookAnalysis() } },
                    _('Return to lesson'),
                ),
            ]),
        ]);
    }
    if (study.chapter.mode === 'practice' && policy.session === 'practice-analysis') {
        return h('div.study-gamebook-status-container', [
            h('div.study-gamebook-status', [
                h('span', _('You are analysing this practice chapter outside computer play.')),
                h(
                    'button.button.button-empty.study-gamebook-return',
                    { attrs: { type: 'button' }, on: { click: () => void modeActions.leavePracticeAnalysis() } },
                    _('Return to practice'),
                ),
            ]),
        ]);
    }
    return h('div.study-gamebook-status-container');
}

function updateStudyGamebookStatus(study: StudyPageModel, modeActions?: StudyModeActions): void {
    if (!modeActions) return;
    const current = document.querySelector<HTMLElement>('.study-gamebook-status-container');
    if (current) patch(toVNode(current), studyGamebookStatus(study, modeActions));
}

export function updateStudyUnderboardChapter(
    study: StudyPageModel,
    model: PyChessModel,
    modeActions?: StudyModeActions,
    practiceProgress?: StudyPracticeProgress,
): void {
    document.querySelectorAll<HTMLElement>('.study-underboard__title').forEach(title => {
        patch(toVNode(title), studyMetadataTitle(study));
    });

    const shareLinks = document.querySelector<HTMLElement>('.study-share__links');
    if (shareLinks) patch(toVNode(shareLinks), studyShareLinks(study, model));
    const practiceUnderboard = document.querySelector<HTMLElement>('.study-practice-underboard');
    if (study.practice && practiceUnderboard) {
        patch(toVNode(practiceUnderboard), practiceStudyUnderboard(study, practiceProgress));
    } else {
        syncStudyPinnedDescriptionUi(study, modeActions);
    }
    updateStudyGamebookStatus(study, modeActions);
    updateStudyServerEvalContent(study, modeActions);
    const preview = document.querySelector<HTMLButtonElement>('.study-gamebook-preview-toggle');
    if (preview) preview.hidden = study.chapter.mode !== 'gamebook';
}

function studyTagsTable(study: StudyPageModel, playback = false): VNode {
    return h(
        `table.study-tags${playback ? '.study-gamebook-play__tags' : ''}`,
        { attrs: { 'data-study-tags': '' } },
        Object.entries(study.chapter.tags).map(([key, value]) =>
            h('tr', { key }, [h('th', { attrs: { scope: 'row' } }, key), h('td', value)]),
        ),
    );
}

function practiceStudyUnderboard(
    study: StudyPageModel,
    practiceProgress?: StudyPracticeProgress,
    practiceState?: StudyPracticeState,
    onNextChapter?: () => void,
    onRetry?: () => void,
): VNode {
    const description = study.chapter.description;
    const hasDescription = Boolean(description && description !== EMPTY_PINNED_CHAPTER_COMMENT);

    if (study.chapter.mode === 'gamebook') {
        return h(
            'div.study-practice-underboard',
            hasDescription
                ? [
                      h('div.study-practice-underboard__feedback.ongoing', [
                          h('div.study-practice-underboard__comment', renderLinkifiedText(description)),
                      ]),
                  ]
                : [],
        );
    }

    const succeeded = practiceState?.kind === 'ended' && practiceState.goalDecision === 'success';
    if (succeeded) {
        const contents = [
            h('strong.study-practice-underboard__success-title', _('Success!')),
            h(
                'span.study-practice-underboard__success-action',
                onNextChapter ? _('Go to next exercise') : _('Back to practice menu'),
            ),
        ];
        if (practiceProgress?.autoNext) {
            return h('div.study-practice-underboard', [
                h('div.study-practice-underboard__feedback.success', [
                    h('strong.study-practice-underboard__success-title', _('Success!')),
                ]),
            ]);
        }
        return h('div.study-practice-underboard', [
            onNextChapter
                ? h(
                      'button.study-practice-underboard__feedback.success.action',
                      { attrs: { type: 'button' }, on: { click: onNextChapter } },
                      contents,
                  )
                : h(
                      'a.study-practice-underboard__feedback.success.action',
                      { attrs: { href: study.practice?.indexUrl ?? '/practice' } },
                      contents,
                  ),
        ]);
    }

    const failed = practiceState?.kind === 'ended' && practiceState.goalDecision === 'failure';
    const goal = study.practice?.goal;
    if (failed && goal && onRetry) {
        return h('div.study-practice-underboard', [
            h(
                'button.study-practice-underboard__feedback.fail.action',
                { attrs: { type: 'button' }, on: { click: onRetry } },
                [
                    h(
                        'span.study-practice-underboard__failure-goal',
                        studyPracticeGoalText(goal, study.chapter.orientation),
                    ),
                    h('strong', _('Click to retry')),
                ],
            ),
        ]);
    }

    const feedback = goal
        ? h('div.study-practice-underboard__feedback.ongoing', [
              h(
                  'div.study-practice-underboard__goal',
                  studyPracticeGoalText(goal, study.chapter.orientation),
              ),
              ...(hasDescription
                  ? [h('div.study-practice-underboard__comment', renderLinkifiedText(description))]
                  : []),
          ])
        : hasDescription
          ? h('div.study-practice-underboard__feedback.ongoing', [
                h('div.study-practice-underboard__comment', renderLinkifiedText(description)),
            ])
          : undefined;
    const autoNext = practiceProgress
        ? h('div.study-practice-underboard__auto-next', [
              h('label.switch', [
                  h('input#practice-auto-next', {
                      props: { type: 'checkbox', checked: practiceProgress.autoNext },
                      attrs: { 'aria-label': _('Load next exercise immediately') },
                      on: {
                          change: event => {
                              practiceProgress.autoNext = (event.currentTarget as HTMLInputElement).checked;
                          },
                      },
                  }),
                  h('span.sw-slider'),
              ]),
              h('label', { attrs: { for: 'practice-auto-next' } }, _('Load next exercise immediately')),
          ])
        : undefined;
    return h('div.study-practice-underboard', [feedback, autoNext].filter(Boolean) as VNode[]);
}

function updatePracticeStudyUnderboardState(
    study: StudyPageModel,
    practiceProgress: StudyPracticeProgress | undefined,
    practiceState: StudyPracticeState,
    onNextChapter?: () => void,
    onRetry?: () => void,
): void {
    const current = document.querySelector<HTMLElement>('.study-practice-underboard');
    if (current)
        patch(
            toVNode(current),
            practiceStudyUnderboard(study, practiceProgress, practiceState, onNextChapter, onRetry),
        );
}

function studyUnderboard(
    study: StudyPageModel,
    model: PyChessModel,
    modeActions: StudyModeActions,
    practiceProgress?: StudyPracticeProgress,
): VNode {
    if (study.practice) return practiceStudyUnderboard(study, practiceProgress);

    const defaultTab: StudyTab = 'tags';
    const policy = effectiveStudySessionPolicy(study);
    const hideServerEval = !policy.tools.evaluationDisplay && !policy.tools.serverAnalysis;
    const tabs: [StudyTab, string, VNode | string][] = [
        ['tags', _('PGN tags'), h('i.study-tag-icon', { attrs: { 'aria-hidden': 'true' } })],
        ...(study.canWrite
            ? ([
                  ['comments', _('Comment this position'), icon('comment-o')],
                  ['glyphs', _('Annotate with glyphs'), '!?'],
              ] as [StudyTab, string, VNode | string][])
            : []),
        ['serverEval', _('Server analysis'), icon('bar-chart')],
        ...(studyCanShare(study)
            ? ([['export', _('Share & export'), icon('share')]] as [StudyTab, string, VNode][])
            : []),
    ];
    return h('div.study-underboard', [
        h('div.study-gamebook-play-underboard', [h('div.study-gamebook-play-buttons', { attrs: { hidden: 'true' } })]),
        studyPinnedChapterComment(study, modeActions),
        h('div.study-gamebook-play__metadata', [studyMetadataTitle(study), studyTagsTable(study, true)]),
        studyGamebookStatus(study, modeActions),
        h('nav.study-tool-tabs', { attrs: { role: 'tablist', 'aria-label': _('Study tools') } }, [
            ...studyModeButtons(study, model, modeActions),
            ...tabs.map(([tab, label, symbol]) =>
                h(
                    `button#study-tab-${tab}`,
                    {
                        attrs: {
                            type: 'button',
                            role: 'tab',
                            title: label,
                            'aria-label': label,
                            'aria-controls': `study-panel-${tab}`,
                            'aria-selected': tab === defaultTab ? 'true' : 'false',
                            tabindex: tab === defaultTab ? 0 : -1,
                            'data-study-tab': tab,
                            ...(tab === 'serverEval' && hideServerEval ? { hidden: true } : {}),
                        },
                        on: {
                            click: () => {
                                selectStudyTab(tab);
                                if (tab === 'serverEval') modeActions.showServerAnalysis();
                            },
                            keydown: event => {
                                const available = tabs.filter(([key]) => {
                                    const button = document.getElementById(`study-tab-${key}`);
                                    return !(button instanceof HTMLButtonElement) || !button.hidden;
                                });
                                const index = available.findIndex(([key]) => key === tab);
                                let next: number;
                                if (event.key === 'ArrowRight') next = (index + 1) % available.length;
                                else if (event.key === 'ArrowLeft') next = (index + available.length - 1) % available.length;
                                else if (event.key === 'Home') next = 0;
                                else if (event.key === 'End') next = available.length - 1;
                                else return;
                                event.preventDefault();
                                event.stopPropagation();
                                selectStudyTab(available[next][0], true);
                                if (available[next][0] === 'serverEval') modeActions.showServerAnalysis();
                            },
                        },
                    },
                    [
                        symbol,
                        ...(tab === 'comments' || tab === 'glyphs'
                            ? [h('span.study-tool-count', { attrs: { 'data-count-for': tab } })]
                            : []),
                    ],
                ),
            ),
            ...(study.canWrite ? [studyGamebookPreviewButton(study, modeActions)] : []),
        ]),
        toolPanel('tags', [
            studyMetadataTitle(study),
            studyTopicsView(study),
            studyTagsTable(study),
            ...(study.canWrite
                ? [
                      h('details.study-annotations__tags', [
                          h('summary', _('Edit PGN tags')),
                          h('textarea', {
                              attrs: {
                                  rows: '6',
                                  'aria-label': _('PGN tags'),
                                  placeholder: 'Event=\nSite=\nDate=',
                              },
                          }),
                          h('button.button', { attrs: { type: 'button' } }, _('Save tags')),
                      ]),
                  ]
                : []),
        ], defaultTab),
        ...(study.canWrite
            ? [
                  toolPanel('comments', [h('div.study-annotations__comments')], defaultTab),
                  toolPanel('glyphs', [
                      h(
                          'div.study-annotations__nags',
                          Object.entries(GLYPH_GROUPS).map(([group, glyphs]) =>
                              h(
                                  `div.study-glyph-group.study-glyph-group--${group}`,
                                  glyphs.map(glyph =>
                                      h(
                                          'button.study-annotations__nag',
                                          {
                                              attrs: {
                                                  type: 'button',
                                                  'data-nag': String(glyph.id),
                                                  'data-symbol': glyph.symbol,
                                                  'aria-pressed': 'false',
                                              },
                                          },
                                          glyph.name(),
                                      ),
                                  ),
                              ),
                          ),
                      ),
                  ], defaultTab),
              ]
            : []),
        toolPanel('serverEval', [studyServerEvalContent(study, modeActions)], defaultTab),
        ...(studyCanShare(study)
            ? [
                  toolPanel('export', [
                      studyShareLinks(study, model),
                      h('div.study-export__actions', [
                          ...(study.canClone
                              ? [
                                    h(
                                        'form.study-share__clone',
                                        { attrs: { method: 'post', action: `/study/${study.id}/clone` } },
                                        [h('button.button', { attrs: { type: 'submit' } }, _('Clone study'))],
                                    ),
                                ]
                              : []),
                          h(
                              'button.button.study-export__chapter',
                              { attrs: { type: 'button' } },
                              _('Download chapter PGN'),
                          ),
                          h(
                              'button.button.study-export__study',
                              { attrs: { type: 'button' } },
                              _('Download study PGN'),
                          ),
                      ]),
                      h('details.study-position-export', [
                          h('summary', _('FEN & PGN')),
                          ...analysisUnderboard(model, analysisContext(model), false),
                      ]),
                  ], defaultTab),
              ]
            : []),
    ]);
}

function tagsText(tags: Record<string, string>): string {
    return Object.entries(tags)
        .map(([name, value]) => `${name}=${value}`)
        .join('\n');
}

function parseTags(text: string): Record<string, string> {
    const tags: Record<string, string> = {};
    for (const line of text.split(/\r?\n/)) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        const separator = trimmed.indexOf('=');
        if (separator <= 0) continue;
        const name = trimmed.slice(0, separator).trim();
        const value = trimmed.slice(separator + 1).trim();
        if (/^[A-Za-z][A-Za-z0-9_]{0,63}$/.test(name) && value) tags[name] = value.slice(0, 512);
    }
    return tags;
}

function updateStudyMetadataPanel(
    study: StudyPageModel,
    modeActions: StudyModeActions,
    state: StudyAnnotationState,
): void {
    document.querySelectorAll<HTMLTableElement>('[data-study-tags]').forEach(table => {
        table.replaceChildren(
            ...Object.entries(state.tags).map(([key, value]) => {
                const row = document.createElement('tr');
                const name = document.createElement('th');
                name.scope = 'row';
                name.textContent = key;
                const cell = document.createElement('td');
                cell.textContent = value;
                row.append(name, cell);
                return row;
            }),
        );
    });

    study.chapter.description = state.description;
    study.chapter.tags = { ...state.tags };
    syncStudyPinnedDescriptionUi(study, modeActions);
    const tags = document.querySelector<HTMLTextAreaElement>('.study-annotations__tags textarea');
    if (tags && document.activeElement !== tags) tags.value = tagsText(state.tags);
}

function updateAnnotationPanel(
    study: StudyPageModel,
    modeActions: StudyModeActions,
    state: StudyAnnotationState,
    editor?: StudyCommentEditor,
): void {
    editor?.update(state.path, state.annotations.comments);
    document.querySelectorAll<HTMLButtonElement>('.study-annotations__nag').forEach(button => {
        const nag = Number(button.dataset.nag);
        button.classList.toggle('active', state.annotations.nags.includes(nag));
        button.setAttribute('aria-pressed', String(state.annotations.nags.includes(nag)));
        button.disabled = state.path === '';
    });

    document.querySelectorAll<HTMLElement>('[data-count-for]').forEach(count => {
        const value =
            count.dataset.countFor === 'comments' ? state.annotations.comments.length : state.annotations.nags.length;
        count.textContent = value ? String(value) : '';
    });
    updateStudyMetadataPanel(study, modeActions, state);
}

function bindAnnotationPanel(getExtension: () => StudyAnalysisExtension): void {
    document.querySelectorAll<HTMLButtonElement>('.study-annotations__nag').forEach(button => {
        button.addEventListener('click', () => {
            const nag = Number(button.dataset.nag);
            const current = getExtension().annotationState.annotations.nags;
            getExtension().setNags(toggleGlyph(current, nag));
        });
    });
    const tags = document.querySelector<HTMLTextAreaElement>('.study-annotations__tags textarea');
    document.querySelector<HTMLButtonElement>('.study-annotations__tags .button')?.addEventListener('click', () => {
        if (tags) getExtension().setTags(parseTags(tags.value));
    });
}

function bindExportPanel(getExtension: () => StudyAnalysisExtension, study: StudyPageModel): void {
    const chapterButton = document.querySelector<HTMLButtonElement>('.study-export__chapter');
    chapterButton?.addEventListener('click', () => {
        const pgnStudy = getExtension().pgnStudy;
        const chapter = getExtension().pgnChapter;
        if (!pgnStudy || !chapter) return;
        downloadText(studyPgnFilename(study.name, chapter.name), renderStudyChapterPgn(pgnStudy, chapter));
    });

    const studyButton = document.querySelector<HTMLButtonElement>('.study-export__study');
    studyButton?.addEventListener('click', async () => {
        const pgnStudy = getExtension().pgnStudy;
        const currentChapter = getExtension().pgnChapter;
        if (!pgnStudy || !currentChapter || !studyButton) return;
        studyButton.disabled = true;
        try {
            const chapters = [];
            for (const preview of [...study.chapters].sort((a, b) => a.order - b.order)) {
                chapters.push(
                    preview.id === currentChapter.id
                        ? currentChapter
                        : await fetchStudyChapterExportData(study.id, preview.id),
                );
            }
            downloadText(studyPgnFilename(study.name), renderStudyPgn(pgnStudy, chapters));
        } catch (error) {
            const detail = error instanceof Error ? error.message : String(error);
            await alertDialog({ text: _('Could not export Study PGN: %1', detail) });
        } finally {
            studyButton.disabled = false;
        }
    });
}

function studyContextMenu(ctrl: AnalysisController, path: string): VNode[] {
    const action = (tab: 'comments' | 'glyphs', label: string, symbol: VNode | string) =>
        h(
            'button',
            {
                attrs: { type: 'button' },
                on: {
                    click: () => {
                        ctrl.activateTreePath(path);
                        ctrl.closeTreeContextMenu();
                        selectStudyTab(tab);
                        document
                            .querySelector<HTMLElement>(
                                `#study-panel-${tab} ${tab === 'comments' ? 'textarea' : 'button'}`,
                            )
                            ?.focus();
                    },
                },
            },
            [typeof symbol === 'string' ? h('i.study-glyph-icon', symbol) : symbol, h('span', label)],
        );
    return [
        action('comments', _('Comment on this move'), icon('comment-o')),
        action('glyphs', _('Annotate with glyphs'), '!?'),
    ];
}

function syncPracticeLearnerBoardHeight(board: HTMLElement, study: StudyPageModel): void {
    if (!study.practice) return;
    const app = board.closest<HTMLElement>('.study-app');
    if (!app) return;

    const update = () => {
        const height = board.getBoundingClientRect().height;
        if (height > 0) app.style.setProperty('--study-practice-board-height', `${height}px`);
    };
    update();
    if (typeof ResizeObserver !== 'undefined') {
        const observer = new ResizeObserver(update);
        observer.observe(board);
    }
}

function runStudyGround(
    vnode: VNode,
    model: PyChessModel,
    study: StudyPageModel,
    sideVNode: VNode,
    modeActions: StudyModeActions,
    keyboard: ChessgroundKeyboard,
    practiceProgress?: StudyPracticeProgress,
): void {
    let extension!: StudyAnalysisExtension;
    let ctrl!: AnalysisController;
    let policy = effectiveStudySessionPolicy(study);
    let serverAnalysisChart: ReturnType<typeof analysisChart> | undefined;
    let navigation: StudyChapterNavigation | undefined;
    let gamebookScriptReloadPending = false;
    const reloadGamebookScript = (): void => {
        gamebookScriptReloadPending = true;
        if (!navigation) return;
        gamebookScriptReloadPending = false;
        void navigation.reload();
    };
    const paths = new Map<string, string>();
    const modules = new Map<boolean, Promise<PyChessModel['ffish']>>([
        [model.variant === 'alice', Promise.resolve(model.ffish)],
    ]);
    const loadStudyModule = (alice: boolean): Promise<PyChessModel['ffish']> => {
        if (!modules.has(alice)) {
            const script = document.querySelector<HTMLScriptElement>('script[src*="/static/pychess-variants.js"]');
            const version = script ? new URL(script.src).search : '';
            modules.set(
                alice,
                (alice ? ffishAliceModule : ffishModule)({
                    locateFile: (path: string, prefix: string) =>
                        path.endsWith('.wasm') ? `/static/${path}${version}` : prefix + path,
                }).catch((error: unknown) => {
                    modules.delete(alice);
                    throw error;
                }),
            );
        }
        return modules.get(alice)!;
    };
    const commentsElement = document.querySelector<HTMLElement>('.study-annotations__comments');
    const editor =
        study.canWrite && commentsElement
            ? new StudyCommentEditor(commentsElement, (path, id, text) => extension.setComment(id, text, path))
            : undefined;
    let gamebookEditorRoot: HTMLElement | undefined;
    let gamebookEditor: StudyGamebookEditor | undefined;
    const ensureGamebookEditor = (): StudyGamebookEditor | undefined => {
        const root = document.querySelector<HTMLElement>('.study-gamebook-edit') ?? undefined;
        if (root === gamebookEditorRoot && gamebookEditor) return gamebookEditor;
        gamebookEditor?.flush();
        gamebookEditor = undefined;
        gamebookEditorRoot = root;
        if (!study.canWrite || !root) return undefined;
        gamebookEditor = new StudyGamebookEditor(root, {
            editComment: () => {
                selectStudyTab('comments');
                document.querySelector<HTMLTextAreaElement>('.study-annotations__comment-input')?.focus();
            },
            navigateToParent: path => ctrl.activateTreePath(parentPath(path)),
            saveGamebook: (field, value, path) => extension.setGamebook(field, value, path),
        });
        return gamebookEditor;
    };
    const updateGamebookEditor = (): void => {
        const root = document.querySelector<HTMLElement>('.study-gamebook-edit');
        const visible = study.canWrite && policy.session === 'gamebook-author';
        if (root) root.hidden = !visible;
        const tree = ctrl?.analysisTree;
        const currentEditor = ensureGamebookEditor();
        if (!visible || !currentEditor || !tree) return;
        currentEditor.update({
            tree,
            path: ctrl.analysisPath ?? '',
            orientation: study.chapter.orientation,
        });
    };
    const socket = study.practice
        ? undefined
        : createWebsocket(
              `wsstudy/${study.id}`,
              () => extension.onSocketOpen(),
              () => extension.onSocketReconnect(),
              () => extension.onSocketClose(),
              event => {
                  if (event.data === '/n') return;
                  const message = JSON.parse(event.data);
                  extension.onSocketMessage(message.type, message);
              },
          );
    const mount = (el: HTMLElement, keyboard: ChessgroundKeyboard, snapshotVerified = false) => {
        policy = effectiveStudySessionPolicy(study);
        syncPracticeLearnerBoardHeight(el, study);
        let gamebookPlayback: StudyGamebookPlayback | undefined;
        const installGamebookPlayback = (analysisCtrl: AnalysisController): void => {
            if (gamebookPlayback || !isGamebookPlayback(policy) || !analysisCtrl.analysisTree) return;
            // The board insert hook can run before later analysis-shell siblings have
            // settled in the DOM. Wait for the normal post-constructor retry when the
            // tools column is not available yet instead of aborting Interactive Lesson
            // playback for the whole chapter.
            if (!document.querySelector<HTMLElement>('.analysis-tools')) return;

            const orderedChapters = [...study.chapters].sort((a, b) => a.order - b.order);
            const chapterIndex = orderedChapters.findIndex(chapter => chapter.id === study.chapter.id);
            const nextChapter = chapterIndex >= 0 ? orderedChapters[chapterIndex + 1] : undefined;
            gamebookPlayback = new StudyGamebookPlayback(analysisCtrl, {
                chapterId: study.chapter.id,
                orientation: study.chapter.orientation,
                preview: policy.session === 'gamebook-preview',
                canAnalyse: !study.canWrite,
                hasNextChapter: Boolean(nextChapter),
                ...(study.practice && practiceProgress
                    ? {
                          practice: {
                              onComplete: chapterId => {
                                  if (!practiceProgress.complete(chapterId)) return;
                                  sideVNode = patch(
                                      sideVNode,
                                      studySide(study, model, modeActions, practiceProgress),
                                  );
                              },
                          },
                      }
                    : {}),
                ...(nextChapter
                    ? { onNextChapter: () => void navigation?.go(nextChapter.id, 'push') }
                    : {}),
                ...(policy.session === 'gamebook-preview'
                    ? { onReturnToEditor: () => void modeActions.leaveGamebookPreview() }
                    : {}),
                ...(!study.canWrite ? { onAnalyse: () => void modeActions.enterGamebookAnalysis() } : {}),
            });
            extension.setGamebookPlayback(gamebookPlayback);
        };
        ctrl = new AnalysisController(el, model, keyboard, analysisCtrl => {
            extension = new StudyAnalysisExtension(analysisCtrl, {
                socket,
                studyId: study.id,
                chapterId: study.chapter.id,
                revision: study.chapter.revision,
                snapshotToken: study.chapter.snapshotToken,
                roomSnapshotToken: study.roomSnapshotToken,
                snapshotVerified: study.practice ? true : snapshotVerified,
                tree: study.chapter.tree,
                orientation: study.chapter.orientation,
                mode: study.chapter.mode,
                description: study.chapter.description,
                tags: study.chapter.tags,
                studyName: study.name,
                chapterName: study.chapter.name,
                chapterOrder: study.chapter.order,
                owner: study.owner,
                home: model.home,
                variant: study.chapter.variant,
                chess960: study.chapter.chess960,
                initialFen: study.chapter.initialFen,
                variantIni: study.chapter.variantIni ?? undefined,
                createdAt: study.chapter.createdAt,
                serverEval: study.chapter.serverEval,
                concealPly: study.chapter.mode === 'conceal' ? (study.chapter.concealPly ?? 0) : undefined,
                policy,
                memberRole: model.username ? study.members[model.username] : undefined,
                // Interactive Lesson playback depends on the persisted Study tree.
                // Initial board/tree hydration happens inside AnalysisController's
                // constructor, so start the learner adapter at the exact point where
                // StudySync has loaded that tree instead of assuming it was already
                // present immediately after controller construction.
                onInitialTreeLoaded: () => queueMicrotask(() => installGamebookPlayback(analysisCtrl)),
                onAnnotationStateChanged: state => {
                    if (policy.tools.annotations) updateAnnotationPanel(study, modeActions, state, editor);
                    else updateStudyMetadataPanel(study, modeActions, state);
                    const preview = study.chapters.find(chapter => chapter.id === study.chapter.id);
                    if (preview) {
                        const status = studyChapterStatusFromTags(state.tags);
                        if (preview.status !== status) {
                            preview.status = status;
                            sideVNode = patch(sideVNode, studySide(study, model, modeActions, practiceProgress));
                        }
                    }
                    updateGamebookEditor();
                },
                onServerEvalChanged: serverEval => {
                    study.chapter.serverEval = serverEval ?? null;
                    study.serverAnalysisError = undefined;
                    updateStudyServerEvalContent(study, modeActions);
                },
                onServerAnalysisVisibilityChanged: () => modeActions.showServerAnalysis?.(),
                onServerAnalysisUnavailable: reason => {
                    study.serverAnalysisError = reason;
                    updateStudyServerEvalContent(study, modeActions);
                },
                onGamebookScriptChanged: () => {
                    if (isGamebookPlayback(policy)) reloadGamebookScript();
                },
                onOrientationChanged: orientation => updateStudyPlayerIdentities(study, orientation),
                onLocalPathChanged: path => {
                    if (!policy.synchronization) return;
                    if (policy.canPublishSharedPosition) extension.sharePosition(study.chapter.id, path);
                    else {
                        study.sticky = false;
                        study.behind = Math.max(1, study.behind ?? 0);
                        refreshStudyModeButtons(study);
                    }
                },
                onChaptersChanged: (chapters, sharedChapter) => {
                    study.chapters = chapters.map(chapter => ({ ...chapter }));
                    const current = study.chapters.find(chapter => chapter.id === study.chapter.id);
                    sideVNode = patch(sideVNode, studySide(study, model, modeActions, practiceProgress));
                    if (!current) {
                        const fallback =
                            study.chapters.find(chapter => chapter.id === sharedChapter)?.id ?? study.chapters[0]?.id;
                        if (fallback) void navigation?.go(fallback, 'replace');
                        return;
                    }
                    study.chapter.name = current.name;
                    study.chapter.order = current.order;
                    study.chapter.orientation = current.orientation;
                    extension.updateChapterMetadata(current);
                    updateMovelist(analysisCtrl, true, false);
                },
                onConcealChanged: (concealPly, revision) => {
                    study.chapter.concealPly = concealPly;
                    study.chapter.revision = revision;
                    const preview = study.chapters.find(chapter => chapter.id === study.chapter.id);
                    if (preview) preview.concealPly = concealPly;
                },
                onSharedPositionChanged: (chapterId, path) => {
                    const changed = study.sharedChapter !== chapterId || study.sharedPath !== path;
                    study.sharedChapter = chapterId;
                    study.sharedPath = path;
                    if (!policy.canFollowSharedPosition) {
                        if (changed) study.behind = (study.behind ?? 0) + 1;
                        refreshStudyModeButtons(study);
                        return;
                    }
                    if (!study.sticky) {
                        if (changed) study.behind = (study.behind ?? 0) + 1;
                        refreshStudyModeButtons(study);
                        return;
                    }
                    study.behind = 0;
                    refreshStudyModeButtons(study);
                    if (chapterId !== study.chapter.id) void navigation?.go(chapterId, 'replace');
                    else if (!extension.followSharedPath(path)) window.location.reload();
                },
                onMembersChanged: members => {
                    study.members = { ...members };
                    if (study.memberConfig && !members[study.memberConfig]) study.memberConfig = undefined;
                    const canWrite = model.username ? members[model.username] === 'write' : false;
                    const accessChanged = canWrite !== study.canWrite;
                    study.canWrite = canWrite;
                    if (!canWrite && study.modeOverride === 'preview') study.modeOverride = null;
                    policy = effectiveStudySessionPolicy(study);
                    extension.setPolicy(policy, !accessChanged);
                    const syncButton = document.querySelector<HTMLButtonElement>('.study-mode--sync');
                    if (syncButton) syncButton.hidden = !(model.username && members[model.username]);
                    updateMovelist(analysisCtrl, true, false);
                    sideVNode = patch(sideVNode, studySide(study, model, modeActions, practiceProgress));
                    updateStudyUnderboardChapter(study, model, modeActions, practiceProgress);
                    updateGamebookEditor();
                    syncStudyPlaybackUi(study, modeActions);
                },
                onLikesChanged: likes => {
                    study.likes = likes;
                    updateStudyLikeControl(study);
                },
                onTopicsChanged: topics => {
                    study.topics = [...topics];
                    updateStudyTopicsView(study);
                },
                contextMenuActions: policy.tools.annotations ? path => studyContextMenu(analysisCtrl, path) : undefined,
                renderMoveListEnd: () =>
                    renderStudyMoveListEnd(study, analysisCtrl, chapterId => void navigation?.go(chapterId, 'push')),
                renderMoveListFooter: () => renderStudyMoveListFooter(study, analysisCtrl),
                writable: study.canWrite,
                recording: policy.recording,
            });
            return extension;
        });
        installGamebookPlayback(ctrl);
        if (isPracticePlayback(policy)) {
            const orderedChapters = [...study.chapters].sort((a, b) => a.order - b.order);
            const chapterIndex = orderedChapters.findIndex(chapter => chapter.id === study.chapter.id);
            const nextChapter = chapterIndex >= 0 ? orderedChapters[chapterIndex + 1] : undefined;
            let practiceSession: StudyPracticeSession;
            practiceSession = new StudyPracticeSession(ctrl, {
                initialFen: study.chapter.initialFen,
                learnerColor: study.chapter.orientation,
                access: () => {
                    if (!(study.features?.computer ?? true)) {
                        return { available: false, reason: 'computer-disabled' as const };
                    }
                    if (ctrl.isLocalAnalysisBlockedByAntiCheat()) {
                        return { available: false, reason: 'active-game' as const };
                    }
                    return { available: true };
                },
                canAnalyse: study.canWrite,
                ...(study.practice?.goal ? { goal: study.practice.goal } : {}),
                ...(study.practice && practiceProgress
                    ? {
                          autoNext: () => practiceProgress.autoNext,
                          hasNextChapter: Boolean(nextChapter),
                          onStateChange: state =>
                              updatePracticeStudyUnderboardState(
                                  study,
                                  practiceProgress,
                                  state,
                                  nextChapter ? () => void navigation?.go(nextChapter.id, 'push') : undefined,
                                  () => practiceSession.reset(),
                              ),
                          onComplete: (moves: number) => {
                              const changed = practiceProgress.complete(study.chapter.id, moves);
                              if (!changed) return;
                              sideVNode = patch(
                                  sideVNode,
                                  studySide(study, model, modeActions, practiceProgress),
                              );
                          },
                      }
                    : {}),
                ...(nextChapter
                    ? {
                          onNextChapter: () => void navigation?.go(nextChapter.id, 'push'),
                          showNextChapterOnEnd: !study.practice,
                      }
                    : {}),
                ...(study.canWrite ? { onAnalyse: () => void modeActions.enterPracticeAnalysis() } : {}),
            });
            extension.setPracticeSession(practiceSession);
        }
        modeActions.requestServerAnalysis = () => {
            if (!policy.tools.serverAnalysis) return;
            study.serverAnalysisError = undefined;
            updateStudyServerEvalContent(study, modeActions);
            extension.requestServerAnalysis();
        };
        modeActions.showServerAnalysis = () => {
            serverAnalysisChart?.destroy();
            serverAnalysisChart = undefined;
            if (!policy.tools.evaluationDisplay) return;
            const chart = document.getElementById('study-server-analysis-chart');
            if (!chart || !study.chapter.serverEval?.analysis.some(step => step !== null)) return;
            serverAnalysisChart = analysisChart(ctrl, 'study-server-analysis-chart');
        };
        modeActions.setDescription = description => extension.setDescription(description);
        modeActions.settleWrites = async () => {
            editor?.flush();
            gamebookEditor?.flush();
            try {
                await extension.whenIdle();
                return true;
            } catch {
                await alertDialog({ text: _('Study changes could not be saved. Please try again.') });
                return false;
            }
        };
        modeActions.importPgn = async (pgn, onProgress) => {
            const chapters = await parseStudyPgnForImportWithEngines(
                studyPgnParser,
                game => loadStudyModule(studyPgnGameUsesAlice(game)),
                pgn,
                onProgress,
            );
            onProgress?.({ phase: 'saving', completed: 0, total: 1 });
            const result = await postStudyPgnImport(study.id, chapters, fetch, Boolean(study.sticky));
            onProgress?.({ phase: 'saving', completed: 1, total: 1 });
            if (!result.chapterId) throw new Error(_('Study PGN import did not return a chapter.'));
            const importDialog = document.querySelector<HTMLDialogElement>('#study-new-chapter');
            if (importDialog?.open) importDialog.close();
            if (navigation) await navigation.go(result.chapterId, 'push');
            else if (result.url) window.location.assign(result.url);
        };
        modeActions.resetConcealment = async () => {
            if (!(await modeActions.settleWrites())) return;
            extension.resetConcealment();
        };
        modeActions.enterGamebookPreview = async () => {
            if (study.chapter.mode !== 'gamebook' || !study.canWrite || policy.preview) return;
            if (!(await modeActions.settleWrites())) return;
            study.modeOverride = 'preview';
            policy = effectiveStudySessionPolicy(study);
            extension.setPolicy(policy);
            updateGamebookEditor();
            await navigation?.reload();
        };
        modeActions.leaveGamebookPreview = async () => {
            if (policy.session !== 'gamebook-preview') return;
            if (!(await modeActions.settleWrites())) return;
            study.modeOverride = null;
            await navigation?.reload();
        };
        modeActions.enterGamebookAnalysis = async () => {
            if (policy.session !== 'gamebook-play') return;
            // Keep the old playback extension restricted until reload replaces the
            // disposable lesson attempt with the authoritative chapter tree.
            study.modeOverride = 'analysis';
            await navigation?.reload();
        };
        modeActions.leaveGamebookAnalysis = async () => {
            if (policy.session !== 'gamebook-analysis') return;
            study.modeOverride = null;
            await navigation?.reload();
        };
        modeActions.enterPracticeAnalysis = async () => {
            if (policy.session !== 'practice-play' || !study.canWrite) return;
            // Keep the disposable practice tree and engine ownership isolated until
            // the authoritative chapter remount replaces this controller.
            study.modeOverride = 'analysis';
            await navigation?.reload();
        };
        modeActions.leavePracticeAnalysis = async () => {
            if (policy.session !== 'practice-analysis') return;
            study.modeOverride = null;
            await navigation?.reload();
        };
        if (socket?.ws.readyState === WebSocket.OPEN) extension.onSocketOpen();
        const serverPanel = document.getElementById('study-panel-serverEval');
        if (serverPanel && !serverPanel.hidden) modeActions.showServerAnalysis();
        if (policy.tools.annotations) updateAnnotationPanel(study, modeActions, extension.annotationState, editor);
        else updateStudyMetadataPanel(study, modeActions, extension.annotationState);
        updateGamebookEditor();
        syncStudyPlaybackUi(study, modeActions);
        window['onFSFline'] = ctrl.onFSFline;
    };
    mount(vnode.elm as HTMLElement, keyboard);
    if (study.canWrite) bindAnnotationPanel(() => extension);
    bindExportPanel(() => extension, study);

    const restoreSessionPosition = (): void => {
        policy = effectiveStudySessionPolicy(study);
        extension.setPolicy(policy);
        if (policy.startPath === 'root') {
            if (ctrl.analysisPath !== '') ctrl.activateTreePath('', true, 'reset');
            return;
        }
        if (policy.canFollowSharedPosition && study.chapter.id === study.sharedChapter) {
            if (!study.sharedPath) {
                if (ctrl.analysisPath !== '') ctrl.activateTreePath('', true, 'reset');
            } else if (!extension.followSharedPath(study.sharedPath)) window.location.reload();
            return;
        }
        if (policy.startPath === 'shared-or-root') {
            if (ctrl.analysisPath !== '') ctrl.activateTreePath('', true, 'reset');
            return;
        }
        const path = paths.get(study.chapter.id);
        if (path && ctrl.getTreeNodeAtPath(path)) ctrl.activateTreePath(path, true, 'reset');
    };

    navigation = new StudyChapterNavigation({
        studyId: study.id,
        currentChapter: () => study.chapter.id,
        chapterUrl: chapterId => studyChapterUrl(study, chapterId),
        flush: () => {
            editor?.flush();
            gamebookEditor?.flush();
            return extension.whenIdle();
        },
        busy: busy => {
            const app = document.querySelector<HTMLElement>('.study-app')!;
            app.setAttribute('aria-busy', String(busy));
            for (const child of app.children) {
                if (!child.classList.contains('sidebar-first')) (child as HTMLElement).inert = busy;
            }
        },
        error: error => {
            console.error('Could not load chapter', error);
            void alertDialog({ text: _('Could not load chapter: %1', String(error)) });
        },
        apply: async (data, isCurrent) => {
            // Validate the tree and load the required WASM module before touching
            // the current board. Alice and the ordinary variants use separate modules.
            analysisTreeFromStudy(data.board.steps[0], data.study.chapter.tree);
            const alice = data.study.chapter.variant === 'alice';
            const rules = data.study.chapter.variantIni
                ? await buildStudyEngineRules(data.study.chapter.variant, variantsIni, data.cataloguedVariants)
                : undefined;
            const ffish = await loadStudyModule(alice);
            await ctrl.whenEngineConfigured();
            if (!isCurrent()) return;
            if (
                !study.practice &&
                !(await extension.verifySnapshot(
                    data.study.chapter.id,
                    data.study.chapter.snapshotToken,
                    data.study.roomSnapshotToken,
                ))
            ) {
                throw new StaleStudyChapterSnapshotError('Study chapter changed while loading.');
            }
            if (!isCurrent()) return;
            const previousChapterId = study.chapter.id;
            paths.set(previousChapterId, ctrl.analysisPath);
            serverAnalysisChart?.destroy();
            serverAnalysisChart = undefined;
            ctrl.destroy();
            editor?.reset();
            gamebookEditor?.reset();
            Object.assign(study, data.study);
            if (study.chapter.id !== previousChapterId) study.modeOverride = null;
            study.chapterDescriptionEditing = false;
            study.serverAnalysisError = undefined;
            model = {
                ...model,
                study,
                ffish,
                board: data.board,
                variant: study.chapter.variant,
                chess960: study.chapter.chess960 ? 'True' : 'False',
                initialFen: study.chapter.initialFen,
                fen: study.chapter.initialFen,
                ply: 0,
            };
            updateStudyUnderboardChapter(study, model, modeActions, practiceProgress);
            loadCataloguedVariantsFromJson(JSON.stringify(data.cataloguedVariants));
            activateStudyEngineRules(rules);
            ffish.loadVariantConfig(variantConfigIni(variantsIni, model.variant));
            document.body.dataset.variant = model.variant;
            document.title = studyDocumentTitle(study);
            // Patch only chapter-dependent parts. The main grid, sidebar, tool tabs
            // and underboard editors remain mounted throughout the switch.
            // A chapter can change the variant, so it gets its own keyboard layer.
            const keyboard = new ChessgroundKeyboard(VARIANTS[model.variant], '');
            const next = renderAnalysisPage(model, {
                side: [],
                underboard: [],
                ongoing: false,
                mountBoard: () => {},
                keyboard,
                toolsAfterMoves: studyAnalysisTools(study),
                ...studyBoardParts(study),
            })[0];
            const app = document.querySelector<HTMLElement>('.study-app')!;
            app.classList.toggle('has-players', studyHasGamePlayers(study));
            const selectors = [
                '#mainboard',
                '#gauge',
                '.pocket-top',
                '.analysis-tools',
                '.analysis-settings',
                '#move-controls',
                '.pocket-bot',
            ];
            for (const selector of selectors) {
                const current = app.querySelector<HTMLElement>(
                    `:scope > ${selector === '#move-controls' ? '#btn-controls-top' : selector}`,
                );
                if (selector === '.analysis-settings') current?.replaceChildren();
                const replacement = (next.children as VNode[]).find(child => child.sel?.includes(selector));
                if (current && replacement) patch(toVNode(current), replacement);
            }
            sideVNode = patch(sideVNode, studySide(study, model, modeActions, practiceProgress));
            syncStudyPlaybackUi(study, modeActions);
            mount(app.querySelector<HTMLElement>('#mainboard > .cg-wrap')!, keyboard, true);
            // Re-apply chapter-dependent underboard content after the replacement
            // controller has mounted. This keeps pinned comments in sync across
            // chapter A -> B -> A navigation in both Study and Practice views.
            updateStudyUnderboardChapter(study, model, modeActions, practiceProgress);
            restoreSessionPosition();
            notifyChessgroundResize();
            if (window.fsf) {
                ctrl.loadVariantsIntoFsfEngine();
            }
        },
    });
    if (gamebookScriptReloadPending) reloadGamebookScript();

    const followAuthoritativePosition = (): void => {
        policy = effectiveStudySessionPolicy(study);
        extension.setPolicy(policy);
        if (!policy.canFollowSharedPosition) {
            refreshStudyModeButtons(study);
            return;
        }
        study.behind = 0;
        refreshStudyModeButtons(study);
        if (study.sharedChapter !== study.chapter.id) void navigation?.go(study.sharedChapter, 'replace');
        else void navigation?.reload();
    };
    modeActions.toggleSticky = () => {
        if (policy.preview) return;
        study.sticky = !study.sticky;
        policy = effectiveStudySessionPolicy(study);
        extension.setPolicy(policy);
        if (policy.synchronization) followAuthoritativePosition();
        else refreshStudyModeButtons(study);
    };
    modeActions.toggleWrite = () => {
        if (!study.canWrite || policy.preview) return;
        study.write = !study.write;
        localStorage.setItem(studyRecordingKey(study.id), String(study.write));
        policy = effectiveStudySessionPolicy(study);
        extension.setPolicy(policy);
        refreshStudyModeButtons(study);
        void navigation?.reload();
    };

    restoreSessionPosition();

    document.querySelector('.sidebar-first')!.addEventListener('click', event => {
        const mouse = event as MouseEvent;
        const link = (event.target as Element).closest<HTMLAnchorElement>('[data-study-chapter-id]');
        if (!link || mouse.button !== 0 || mouse.ctrlKey || mouse.metaKey || mouse.shiftKey || mouse.altKey) return;
        const chapterId = link.dataset.studyChapterId;
        if (!chapterId) return;
        event.preventDefault();
        if (chapterId !== study.chapter.id) study.modeOverride = null;
        if (policy.synchronization) {
            if (policy.canPublishSharedPosition && extension.sharePosition(chapterId, '')) return;
            study.sticky = false;
            study.behind = Math.max(1, study.behind ?? 0);
            refreshStudyModeButtons(study);
        }
        void navigation?.go(chapterId);
    });
    window.addEventListener('popstate', () => {
        const chapterId = chapterIdFromStudyUrl(study, window.location.pathname);
        if (!chapterId) return;
        if (chapterId !== study.chapter.id) study.modeOverride = null;
        if (policy.synchronization && chapterId !== study.sharedChapter) {
            study.sticky = false;
            refreshStudyModeButtons(study);
        }
        void navigation?.go(chapterId, 'pop');
    });
    window.addEventListener('beforeunload', event => {
        editor?.flush();
        gamebookEditor?.flush();
        if (extension.pendingCount > 0) {
            event.preventDefault();
            event.returnValue = '';
        }
    });
}

function studyEmbedPolicy(study: StudyPageModel): StudySessionPolicy {
    return studySessionPolicy({
        mode: study.chapter.mode ?? 'normal',
        canWrite: false,
        computerAllowed: study.features?.computer ?? true,
        savedRecording: false,
        savedSynchronization: false,
        activeGame: hasActiveEligibleLiveGame(),
    });
}

function runStudyEmbedGround(
    vnode: VNode,
    model: PyChessModel,
    study: StudyPageModel,
    policy: StudySessionPolicy,
    keyboard: ChessgroundKeyboard,
): void {
    const rootOnlyPreview = (study.chapter.mode ?? 'normal') !== 'normal';
    const ctrl = new AnalysisController(vnode.elm as HTMLElement, model, keyboard, analysisCtrl =>
        new StudyAnalysisExtension(analysisCtrl, {
            studyId: study.id,
            chapterId: study.chapter.id,
            revision: study.chapter.revision,
            snapshotToken: study.chapter.snapshotToken,
            tree: study.chapter.tree,
            orientation: study.chapter.orientation,
            mode: study.chapter.mode,
            description: study.chapter.description,
            tags: study.chapter.tags,
            studyName: study.name,
            chapterName: study.chapter.name,
            chapterOrder: study.chapter.order,
            owner: study.owner,
            home: model.home,
            variant: study.chapter.variant,
            chess960: study.chapter.chess960,
            initialFen: study.chapter.initialFen,
            variantIni: study.chapter.variantIni ?? undefined,
            createdAt: study.chapter.createdAt,
            concealPly: study.chapter.mode === 'conceal' ? (study.chapter.concealPly ?? 0) : undefined,
            policy,
            rootOnlyPreview,
            writable: false,
        }),
    );
    window['onFSFline'] = ctrl.onFSFline;
}

export function studyEmbedView(model: PyChessModel): VNode[] {
    const study = model.study;
    if (!study) return [h('div.box.box-pad', _('Study data is unavailable.'))];

    const policy = studyEmbedPolicy(study);
    const chapterMode = study.chapter.mode ?? 'normal';
    const preview = chapterMode !== 'normal';
    const studyUrl = `/study/${study.id}/${study.chapter.id}`;
    const keyboard = new ChessgroundKeyboard(VARIANTS[model.variant], '');
    const page = renderEmbedPage(
        model,
        keyboard,
        vnode => runStudyEmbedGround(vnode, model, study, policy, keyboard),
        h(
            'a.gamelink',
            {
                attrs: {
                    rel: 'noopener',
                    target: '_blank',
                    href: studyUrl,
                },
            },
            `${study.name} • ${study.chapter.name}`,
        ),
        preview
            ? h(
                  'a.button.study-embed-preview__open',
                  {
                      attrs: {
                          rel: 'noopener',
                          target: '_blank',
                          href: studyUrl,
                      },
                  },
                  chapterMode === 'gamebook' ? _('Start') : _('Open study'),
              )
            : undefined,
    );
    page[0].data = {
        ...page[0].data,
        class: {
            ...page[0].data?.class,
            'study-embed-preview': preview,
            'study-embed-gamebook': chapterMode === 'gamebook',
        },
    };
    return page;
}

export function studyView(model: PyChessModel): VNode[] {
    const study = model.study;
    if (!study) return [h('div.box.box-pad', _('Study data is unavailable.'))];

    initializeStudyModes(study);
    const practiceProgress = study.practice
        ? new StudyPracticeProgress(
              localStorage,
              study.practice.completedChapterIds,
              (chapterId, bestMoves) => persistPracticeCompletion(study, chapterId, bestMoves),
          )
        : undefined;
    const modeActions: StudyModeActions = {
        toggleSticky: () => {},
        toggleWrite: () => {},
        requestServerAnalysis: () => {},
        showServerAnalysis: () => {},
        setDescription: () => {},
        settleWrites: async () => true,
        importPgn: async () => {},
        resetConcealment: async () => {},
        enterGamebookPreview: async () => {},
        leaveGamebookPreview: async () => {},
        enterGamebookAnalysis: async () => {},
        leaveGamebookAnalysis: async () => {},
        enterPracticeAnalysis: async () => {},
        leavePracticeAnalysis: async () => {},
    };
    const side = studySide(study, model, modeActions, practiceProgress);
    const keyboard = new ChessgroundKeyboard(VARIANTS[model.variant], '');
    const page = renderAnalysisPage(model, {
        side,
        underboard: studyUnderboard(study, model, modeActions, practiceProgress),
        mountBoard: vnode => runStudyGround(vnode, model, study, side, modeActions, keyboard, practiceProgress),
        keyboard,
        ongoing: false,
        toolsAfterMoves: studyAnalysisTools(study),
        ...studyBoardParts(study),
    });
    page[0].data = {
        ...page[0].data,
        class: {
            ...page[0].data?.class,
            'study-app': true,
            'has-players': studyHasGamePlayers(study),
            'study-conceal-playback': isConcealPlayback(effectiveStudySessionPolicy(study)),
            'study-gamebook-playback': isGamebookPlayback(effectiveStudySessionPolicy(study)),
            'study-gamebook-preview': effectiveStudySessionPolicy(study).session === 'gamebook-preview',
            'study-gamebook-analysis': effectiveStudySessionPolicy(study).session === 'gamebook-analysis',
            'study-practice-playback': isPracticePlayback(effectiveStudySessionPolicy(study)),
            'study-practice-analysis': effectiveStudySessionPolicy(study).session === 'practice-analysis',
        },
    };
    return page;
}
