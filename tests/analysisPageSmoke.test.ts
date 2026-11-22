import { afterEach, beforeEach, describe, expect, jest, test } from '@jest/globals';
import { h, type VNode } from 'snabbdom';

import type { AnalysisController } from '../client/analysis/analysisCtrl';
import { addOrSelectChild, createAnalysisTree, mainlinePathAtPly } from '../client/analysis/analysisTree';
import { patch } from '../client/document';
import { Step } from '../client/messages';
import { updateMovelist } from '../client/movelist';
import { StudyConcealController } from '../client/study/studyConceal';
import { studySessionPolicy } from '../client/study/studyMode';
import { PyChessModel, StudyPageModel } from '../client/types';

jest.useFakeTimers();

jest.unstable_mockModule('../client/analysis/analysisCtrl', () => ({
    AnalysisController: class AnalysisController {
        analysisPath = '';
        analysisTree = undefined;
        chessground = { setShapes: jest.fn() };
        username = 'tester';
        onFSFline = jest.fn();

        constructor(_el: HTMLElement, _model: PyChessModel, extensionFactory?: (ctrl: unknown) => unknown) {
            extensionFactory?.(this);
        }
    },
}));
jest.unstable_mockModule('../client/puzzleCtrl', () => ({
    PuzzleController: class PuzzleController {},
}));
jest.unstable_mockModule('../client/roundCtrl', () => ({
    RoundController: class RoundController {},
}));
jest.unstable_mockModule('../client/analysis/analysisSettings', () => ({
    analysisSettings: {
        settings: { showGauge: { value: true } },
        view: () => h('div.analysis-settings'),
        engineView: () => h('div#analysis-engine-preferences.analysis-engine-preferences'),
    },
    EngineSettings: class EngineSettings {
        view() {
            return h('div.engine-toggle');
        }
    },
}));

const { analysisView, embedView, renderAnalysisPage } = await import('../client/analysis');
const { puzzleView } = await import('../client/puzzle');
const { renderStudyMoveListEnd, renderStudyMoveListFooter, studyEmbedView, studyView, updateStudyUnderboardChapter } =
    await import('../client/study/studyView');
const { roundView } = await import('../client/round');

function makeModel(overrides: Partial<PyChessModel> = {}): PyChessModel {
    return {
        ffish: {} as PyChessModel['ffish'],
        username: 'tester',
        home: 'http://127.0.0.1:8080',
        anon: '',
        profileid: '',
        title: '',
        variant: 'chess',
        chess960: 'False',
        rated: '0',
        corr: '',
        level: 8,
        gameId: '',
        gameCategory: 'all',
        tournamentId: '',
        tournamentname: '',
        simulId: '',
        simulname: '',
        tournamentcreator: '',
        inviter: '',
        challengeId: '',
        ply: 0,
        ct: '',
        board: '',
        wplayer: 'White',
        wtitle: '',
        wrating: '1500',
        wrdiff: 0,
        wberserk: '',
        bplayer: 'Black',
        btitle: '',
        brating: '1500',
        brdiff: 0,
        bberserk: '',
        fen: 'rn1qkbnr/pppb1ppp/8/3pp3/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        posnum: 0,
        initialFen: 'rn1qkbnr/pppb1ppp/8/3pp3/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        base: 300,
        inc: 5,
        byo: 0,
        result: '*',
        status: 1,
        tsystem: 0,
        rounds: 0,
        date: '2026-05-06T12:00:00Z',
        tv: false,
        embed: false,
        seekEmpty: false,
        tournamentDirector: false,
        assetURL: '',
        puzzle: '',
        wplayerB: '',
        wtitleB: '',
        wratingB: '',
        bplayerB: '',
        btitleB: '',
        bratingB: '',
        blogs: '',
        corrGames: '',
        simulGames: '',
        simulHost: false,
        oauthUsernameSelection: null,
        ...overrides,
    };
}

function renderNodes(nodes: VNode[]): HTMLElement {
    const host = document.createElement('div');
    document.body.appendChild(host);
    const vnode = patch(host, h('div.test-root', nodes));
    return vnode.elm as HTMLElement;
}

function makeStep(fen: string, move: string | undefined, turnColor: 'white' | 'black', san?: string): Step {
    return {
        fen,
        move,
        check: false,
        turnColor,
        san,
        sanSAN: san,
    };
}

beforeEach(() => {
    document.body.innerHTML = '';
    Object.defineProperty(globalThis, 'DataTransfer', {
        configurable: true,
        writable: true,
        value: class DataTransfer {
            items = {
                add: (_file: File) => undefined,
            };
            files = [] as unknown as FileList;
        },
    });
});

afterEach(() => {
    jest.clearAllTimers();
    document.body.innerHTML = '';
});

describe('analysis page smoke coverage', () => {
    test('standalone analysis page keeps PGN tools and move controls', () => {
        const root = renderNodes(analysisView(makeModel({ gameId: '', status: 1 })));

        expect(root.querySelector('#movelist')).not.toBeNull();
        expect(root.querySelector('#move-controls')).not.toBeNull();
        expect(root.querySelector('#pgntext')).not.toBeNull();
        expect(root.querySelector('.pgn-toolbar .analysis-add-to-study')?.textContent).toBe('Add to Study');
        expect(root.querySelectorAll('[role="tab"]').length).toBeGreaterThan(0);
    });

    test('finished-game analysis page keeps chat, PGN and controls', () => {
        const root = renderNodes(analysisView(makeModel({ gameId: 'cPeP5Di1', status: 1 })));

        expect(root.querySelector('#roundchat')).not.toBeNull();
        expect(root.querySelector('#movelist')).not.toBeNull();
        expect(root.querySelector('#move-controls')).not.toBeNull();
        expect(root.querySelector('#pgntext')).not.toBeNull();
        expect(root.querySelector('.pgn-toolbar .analysis-add-to-study')?.textContent).toBe('Add to Study');
    });

    test('ongoing and anonymous analysis do not offer Add to Study', () => {
        const ongoing = renderNodes(analysisView(makeModel({ gameId: 'cPeP5Di1', status: -1 })));
        expect([...ongoing.querySelectorAll('button')].some(button => button.textContent === 'Add to Study')).toBe(
            false,
        );

        document.body.innerHTML = '';
        const anonymous = renderNodes(analysisView(makeModel({ gameId: '', status: 1, anon: 'True' })));
        expect([...anonymous.querySelectorAll('button')].some(button => button.textContent === 'Add to Study')).toBe(
            false,
        );
    });

    test('reusable analysis shell composes page-specific side and under-board content', () => {
        const mountBoard = jest.fn();
        const model = makeModel({ gameId: '', status: 1 });
        const root = renderNodes(
            renderAnalysisPage(model, {
                side: h('div.study-side', 'Study chapters'),
                underboard: h('div.study-underboard', 'Study notes'),
                mountBoard,
                ongoing: false,
                toolsAfterMoves: h('div.study-gamebook-edit', 'Lesson authoring'),
            }),
        );

        expect(mountBoard).toHaveBeenCalledTimes(1);
        expect(mountBoard.mock.calls[0][1]).toBe(model);
        expect(root.querySelector('.study-side')).not.toBeNull();
        expect(root.querySelector('.study-underboard')).not.toBeNull();
        expect(root.querySelector('#mainboard')).not.toBeNull();
        expect(root.querySelector('#movelist')).not.toBeNull();
        expect(root.querySelector('#movelist-footer')).not.toBeNull();
        expect(root.querySelector('.analysis-tools > #movelist-footer + .study-gamebook-edit')?.textContent).toBe(
            'Lesson authoring',
        );
        expect(root.querySelector('#move-controls')).not.toBeNull();
        expect(root.querySelector('.analysis-settings')).not.toBeNull();
        expect(root.querySelector('#pgntext')).toBeNull();
        expect(root.querySelector('#roundchat')).toBeNull();
    });

    test('study view composes the analysis shell with chapter navigation', () => {
        const root = renderNodes(
            studyView(
                makeModel({
                    gameId: '',
                    status: 0,
                    study: {
                        id: 'StUdY001',
                        name: 'Opening ideas',
                        owner: 'tester',
                        visibility: 'private',
                        isOwner: true,
                        canWrite: true,
                        canPreviewPractice: true,
                        canClone: true,
                        canLike: true,
                        liked: true,
                        likes: 1,
                        topics: ['Opening', 'King pawn'],
                        maxTopics: 30,
                        topicMinLength: 2,
                        topicMaxLength: 50,
                        members: { tester: 'write', writer: 'write', reader: 'read' },
                        maxMembers: 30,
                        sharedChapter: 'ChAp0001',
                        sharedPath: '',
                        chapter: {
                            id: 'ChAp0001',
                            name: 'Main line',
                            revision: 3,
                            order: 1,
                            orientation: 'white',
                            variant: 'chess',
                            chess960: false,
                            initialFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
                            variantIni: null,
                            createdAt: '2026-09-05T08:00:00+00:00',
                            description: 'Chapter description',
                            tags: { Event: 'Test event', Site: 'PyChess' },
                            tree: {
                                rootAnnotations: {
                                    shapes: [],
                                    comments: [{ id: 'Comment001', author: 'tester', text: 'Root note' }],
                                    nags: [1],
                                },
                                nodes: [],
                            },
                        },
                        chapters: [
                            { id: 'ChAp0001', name: 'Main line', order: 1, orientation: 'white' },
                            { id: 'ChAp0002', name: 'Sideline', order: 2, orientation: 'black' },
                        ],
                    },
                }),
            ),
        );

        expect(root.querySelector('.study-side')).not.toBeNull();
        expect(root.querySelector('.study-side__metadata')).toBeNull();
        expect(root.querySelector('#study-side-tab-chapters')?.getAttribute('aria-selected')).toBe('true');
        expect(root.querySelector('#study-side-tab-members')?.getAttribute('aria-selected')).toBe('false');
        expect(root.querySelectorAll('.study-chapter__row')).toHaveLength(2);
        expect(root.querySelector('.study-chapter__row.active a')?.getAttribute('href')).toBe(
            '/study/StUdY001/ChAp0001',
        );
        expect(root.querySelector<HTMLElement>('#study-side-panel-members')!.hidden).toBe(true);
        const membersTab = root.querySelector<HTMLButtonElement>('#study-side-tab-members')!;
        membersTab.click();
        expect(membersTab.getAttribute('aria-selected')).toBe('true');
        expect(root.querySelector<HTMLElement>('#study-side-panel-chapters')!.hidden).toBe(true);
        expect(root.querySelector<HTMLElement>('#study-side-panel-members')!.hidden).toBe(false);
        expect(root.querySelectorAll('.study-members-side__member')).toHaveLength(3);
        expect(root.querySelector('.study-members-side__add')?.textContent).toContain('Add members');
        membersTab.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true }));
        expect(root.querySelector('#study-side-tab-chapters')?.getAttribute('aria-selected')).toBe('true');
        expect(document.activeElement).toBe(root.querySelector('#study-side-tab-chapters'));
        expect(root.querySelector('#mainboard')).not.toBeNull();
        expect(root.querySelector('#movelist')).not.toBeNull();
        expect(root.querySelector('#pgntext')).not.toBeNull();
        expect(root.querySelector('#roundchat')).toBeNull();
        expect([...root.querySelectorAll('button')].some(button => button.textContent === 'Add to Study')).toBe(false);
        expect(root.querySelector('dialog#study-new-chapter .study-side__new-chapter')).not.toBeNull();
        expect(root.querySelector<HTMLAnchorElement>('.study-practice-preview')?.getAttribute('href')).toBe(
            '/practice/preview/StUdY001/ChAp0001',
        );
        expect(root.querySelector('.study-practice-preview')?.textContent).toContain('Preview in Practice');
        const newChapterForm = root.querySelector<HTMLFormElement>(
            'dialog#study-new-chapter .study-side__new-chapter',
        )!;
        expect(newChapterForm.querySelector<HTMLSelectElement>('select[name="orientation"]')?.value).toBe('white');
        expect(
            [...newChapterForm.querySelectorAll<HTMLOptionElement>('select[name="mode"] option')].map(
                option => option.value,
            ),
        ).toEqual(['normal', 'practice', 'gamebook']);
        expect(root.querySelector('dialog#study-members')).toBeNull();
        const writerRow = root.querySelector<HTMLElement>('[data-study-member="writer"]')!;
        const writerConfigButton = writerRow.querySelector<HTMLButtonElement>('[data-study-member-config-button]')!;
        const writerConfig = root.querySelector<HTMLElement>('[data-study-member-config="writer"]')!;
        expect(writerConfig.hidden).toBe(true);
        writerConfigButton.click();
        expect(writerRow.classList.contains('editing')).toBe(true);
        expect(writerConfig.hidden).toBe(false);
        expect(writerConfig.querySelector<HTMLInputElement>('input[type="checkbox"]')?.checked).toBe(true);
        expect(writerConfig.querySelector('.study-members-side__kick')?.textContent).toContain('KICK');
        expect(writerConfigButton.getAttribute('aria-expanded')).toBe('true');
        writerConfigButton.click();
        expect(writerConfig.hidden).toBe(true);
        expect(writerConfigButton.getAttribute('aria-expanded')).toBe('false');
        expect(root.querySelector('dialog#study-invite .study-invite__form')).not.toBeNull();
        expect(root.querySelector('dialog#study-invite select[name="role"]')).toBeNull();
        expect(root.querySelector('input[name="fen"]')).not.toBeNull();
        expect(root.querySelector('input[name="gameId"]')).not.toBeNull();
        expect(root.querySelector('dialog#study-new-chapter [data-study-chapter-source="pgn"]')).not.toBeNull();
        expect(root.querySelector('dialog#study-new-chapter textarea[name="pgn"]')).not.toBeNull();
        expect(root.querySelector('dialog#study-new-chapter input[type="file"][accept=".pgn"]')).not.toBeNull();
        const studySettings = root.querySelector<HTMLDialogElement>('#study-settings')!;
        expect(studySettings.querySelector('#study-settings-form input[name="name"]')?.getAttribute('value')).toBe(
            'Opening ideas',
        );
        expect(
            studySettings.querySelector('.study-dialog__actions button[form="study-settings-form"]')?.textContent,
        ).toBe('Save');
        expect(studySettings.querySelector<HTMLSelectElement>('select[name="computer"]')?.value).toBe('everyone');
        expect(studySettings.querySelector<HTMLSelectElement>('select[name="cloneable"]')?.value).toBe('everyone');
        expect(studySettings.querySelector<HTMLSelectElement>('select[name="shareable"]')?.value).toBe('everyone');
        expect(studySettings.querySelector<HTMLInputElement>('input[name="explorer"]')?.value).toBe('everyone');
        const secondChapterSettings = root.querySelector<HTMLDialogElement>('#chapter-settings-ChAp0002')!;
        expect(secondChapterSettings.querySelector<HTMLSelectElement>('select[name="orientation"]')?.value).toBe(
            'black',
        );
        const chapterMode = secondChapterSettings.querySelector<HTMLSelectElement>('select[name="mode"]')!;
        expect(chapterMode.disabled).toBe(false);
        expect(chapterMode.value).toBe('normal');
        expect([...chapterMode.options].map(option => option.value)).toEqual(['normal', 'practice', 'gamebook']);
        expect(
            secondChapterSettings.querySelector('.study-chapter-orientation .study-dialog__help')?.textContent,
        ).toContain('learner side');
        expect(secondChapterSettings.querySelector<HTMLSelectElement>('select[name="description"]')?.value).toBe('');
        expect(
            secondChapterSettings.querySelector('.study-dialog__actions button[form="chapter-settings-form-ChAp0002"]')
                ?.textContent,
        ).toBe('Save chapter');
        expect(
            secondChapterSettings.querySelector<HTMLFormElement>(
                'form[action="/study/StUdY001/ChAp0002/clear-annotations"]',
            )?.textContent,
        ).toBe('Clear annotations');
        expect(
            secondChapterSettings.querySelector<HTMLFormElement>(
                'form[action="/study/StUdY001/ChAp0002/clear-variations"]',
            )?.textContent,
        ).toBe('Clear variations');
        expect(root.querySelector('under-board .study-underboard')).not.toBeNull();
        expect(root.querySelector('under-board .study-tool-tabs > .study-mode--sync')).not.toBeNull();
        expect(root.querySelector('under-board .study-tool-tabs > .study-mode--write')).not.toBeNull();
        expect(root.querySelector('#study-tab-lesson')).toBeNull();
        expect(root.querySelector<HTMLButtonElement>('.study-gamebook-preview-toggle')?.hidden).toBe(true);
        expect(root.querySelector('.analysis-tools > .study-gamebook-edit')).not.toBeNull();
        expect(root.querySelector<HTMLElement>('.analysis-tools > .study-gamebook-edit')?.hidden).toBe(true);
        expect(root.querySelector('#study-tab-tags')?.getAttribute('aria-selected')).toBe('true');
        expect(root.querySelector<HTMLButtonElement>('.study-like')?.getAttribute('aria-pressed')).toBe('true');
        expect(root.querySelector('.study-like__count')?.textContent).toBe('1');
        expect([...root.querySelectorAll<HTMLAnchorElement>('.study-topic')].map(topic => topic.textContent)).toEqual([
            'Opening',
            'King pawn',
        ]);
        expect(root.querySelector<HTMLAnchorElement>('.study-topic')?.getAttribute('href')).toBe(
            '/study/topic/Opening',
        );
        expect(root.querySelector('.study-topics__manage')?.textContent).toBe('Manage topics');
        expect(root.querySelector('#study-topics textarea[name="topics"]')).toBeNull();
        expect(
            [...root.querySelectorAll<HTMLElement>('#study-topics [data-topic-value]')].map(
                topic => topic.dataset.topicValue,
            ),
        ).toEqual(['Opening', 'King pawn']);
        expect(root.querySelector('#study-topics [data-topic-count]')?.textContent).toBe('2/30 topics');
        const topicInput = root.querySelector<HTMLInputElement>('#study-topics .study-topic-editor__input')!;
        expect(root.querySelector('#study-topics [data-topic-length]')?.textContent).toBe('0/50 characters');
        topicInput.value = 'x'.repeat(60);
        topicInput.dispatchEvent(new Event('input', { bubbles: true }));
        expect(Array.from(topicInput.value)).toHaveLength(50);
        expect(root.querySelector('#study-topics [data-topic-feedback]')?.textContent).toContain('50');
        topicInput.value = '';
        topicInput.dispatchEvent(new Event('input', { bubbles: true }));
        expect(root.querySelector('.study-side .study-mode')).toBeNull();
        expect(root.querySelector('.study-annotations__comment-input')).not.toBeNull();
        expect(root.querySelectorAll('.study-annotations__nag')).toHaveLength(24);
        expect(root.querySelector('.study-desc.chapter-desc .text')?.textContent).toBe('Chapter description');
        expect(root.querySelector('#study-tab-description')).toBeNull();
        expect(
            root.querySelector<HTMLSelectElement>('#chapter-settings-ChAp0001 select[name="description"]')?.value,
        ).toBe('1');
        expect((root.querySelector('.study-annotations__tags textarea') as HTMLTextAreaElement).value).toBe(
            'Event=Test event\nSite=PyChess',
        );
        expect(root.querySelector('.study-export__chapter')?.textContent).toBe('Download chapter PGN');
        expect(root.querySelector('.study-export__study')?.textContent).toBe('Download study PGN');
        const privateEmbedInput = root.querySelector<HTMLInputElement>(
            '.study-share__link:nth-child(3) .study-share__copy input',
        )!;
        expect(privateEmbedInput.disabled).toBe(true);
        expect(privateEmbedInput.value).toBe('Private Studies cannot be embedded.');
        const comments = root.querySelector<HTMLButtonElement>('#study-tab-comments')!;
        comments.click();
        expect(root.querySelector<HTMLElement>('#study-panel-comments')!.hidden).toBe(false);
        expect(root.querySelector<HTMLElement>('#study-panel-tags')!.hidden).toBe(true);
        comments.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
        expect(root.querySelector('#study-tab-glyphs')?.getAttribute('aria-selected')).toBe('true');
        expect(document.activeElement).toBe(root.querySelector('#study-tab-glyphs'));
        expect(root.querySelector<HTMLElement>('#study-panel-comments')!.hidden).toBe(true);
    });

    test('game-source Study chapters render Lichess-style player bars and clocks', () => {
        const study: StudyPageModel = {
            id: 'StUdY001',
            name: 'Game study',
            owner: 'tester',
            visibility: 'private',
            isOwner: true,
            canWrite: true,
            canClone: true,
            canLike: true,
            liked: true,
            likes: 1,
            topics: [],
            maxTopics: 30,
            topicMinLength: 2,
            topicMaxLength: 50,
            members: { tester: 'write' },
            maxMembers: 30,
            sharedChapter: 'ChAp0001',
            sharedPath: '',
            roomSnapshotToken: 'room-snapshot',
            chapter: {
                id: 'ChAp0001',
                name: 'Played game',
                revision: 1,
                order: 1,
                orientation: 'white',
                variant: 'chess',
                chess960: false,
                initialFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
                variantIni: null,
                createdAt: '2026-09-07T08:00:00+00:00',
                source: { kind: 'game', id: 'game0001' },
                description: '',
                tags: {
                    White: 'Alice',
                    Black: 'Bob',
                    WhiteElo: '2107',
                    BlackElo: '2224',
                    WhiteTitle: 'FM',
                },
                tree: { nodes: [], rootClocks: [300000, 300000] },
            },
            chapters: [{ id: 'ChAp0001', name: 'Played game', order: 1, orientation: 'white' }],
        };
        const model = makeModel({ gameId: '', status: 0, study });
        const root = renderNodes(studyView(model));

        expect(root.querySelector('.study-app')?.classList.contains('has-players')).toBe(true);
        expect(root.querySelector('.study__player-top .name')?.textContent).toBe('Bob');
        expect(root.querySelector('.study__player-top .elo')?.textContent).toBe('2224');
        expect(root.querySelector('.study__player-bot player-title')?.textContent).toBe('FM');
        expect(root.querySelector('.study__player-bot .name')?.textContent).toBe('Alice');
        expect(root.querySelector('.study__player-bot .elo')?.textContent).toBe('2107');
        expect(root.querySelector('#anal-clock-top')).not.toBeNull();
        expect(root.querySelector('#anal-clock-bottom')).not.toBeNull();

        study.chapter.description = 'Pinned after render';
        updateStudyUnderboardChapter(study, model);
        expect(
            root.querySelector<HTMLSelectElement>('#chapter-settings-ChAp0001 select[name="description"]')?.value,
        ).toBe('1');
        expect(study.chapters[0].descriptionPinned).toBe(true);

        study.isOwner = false;
        study.canWrite = false;
        study.chapter.source = { kind: 'import' };
        study.chapter.tags = {
            ...study.chapter.tags,
            Event: 'World Blitz 2025 Open',
            Result: '0-1',
        };
        study.chapter.tree = { nodes: [] };
        study.chapters[0].status = '0-1';
        const importedRoot = renderNodes(studyView(makeModel({ gameId: '', status: 0, study })));

        expect(importedRoot.querySelector('.study-app')?.classList.contains('has-players')).toBe(true);
        expect(importedRoot.querySelector('.study-chapter__result')?.textContent).toBe('0-1');
        expect(importedRoot.querySelector('.study__player-top .name')?.textContent).toBe('Bob');
        expect(importedRoot.querySelector('.study__player-top .name')?.tagName).toBe('SPAN');
        expect(importedRoot.querySelector('.study__player-top .result')?.textContent).toBe('1');
        expect(importedRoot.querySelector('.study__player-bot .result')?.textContent).toBe('0');
        expect(importedRoot.querySelector('.study__player .anal-clock')).toBeNull();

        study.chapter.mode = 'gamebook';
        study.chapters[0].mode = 'gamebook';
        study.modeOverride = 'analysis';
        const metadataRoot = renderNodes(studyView(makeModel({ gameId: '', status: 0, study })));
        const pinnedComment = metadataRoot.querySelector('.study-desc-slot');
        const playbackMetadata = metadataRoot.querySelector('.study-gamebook-play__metadata');
        const playbackTags = playbackMetadata?.querySelector('.study-tags');
        expect(pinnedComment?.textContent).toContain('Pinned after render');
        expect(playbackMetadata).not.toBeNull();
        expect(
            Boolean(pinnedComment?.compareDocumentPosition(playbackMetadata!) & Node.DOCUMENT_POSITION_FOLLOWING),
        ).toBe(true);
        expect(playbackTags).not.toBeNull();
        expect(playbackTags?.textContent).toContain('World Blitz 2025 Open');
        expect(playbackTags?.textContent).toContain('Alice');
        expect(metadataRoot.querySelector('.study-gamebook-play__metadata #study-panel-tags')).toBeNull();
    });

    test('read-only study view hides mutation controls while keeping sharing available', () => {
        const study: StudyPageModel = {
            id: 'StUdY001',
            name: 'Shared ideas',
            owner: 'owner',
            visibility: 'unlisted',
            isOwner: false,
            canWrite: false,
            canClone: true,
            canLike: true,
            liked: false,
            likes: 1,
            topics: [],
            maxTopics: 30,
            topicMinLength: 2,
            topicMaxLength: 50,
            members: { owner: 'write', tester: 'read' },
            maxMembers: 30,
            sharedChapter: 'ChAp0001',
            sharedPath: '',
            roomSnapshotToken: 'room-snapshot',
            chapter: {
                id: 'ChAp0001',
                name: 'Shared line',
                revision: 1,
                order: 1,
                orientation: 'white',
                variant: 'chess',
                chess960: false,
                initialFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
                variantIni: null,
                createdAt: '2026-09-06T08:00:00+00:00',
                description: 'Shared description',
                tags: { Event: 'Shared study' },
                tree: { nodes: [] },
            },
            chapters: [{ id: 'ChAp0001', name: 'Shared line', order: 1, orientation: 'white' }],
        };
        const root = renderNodes(studyView(makeModel({ gameId: '', status: 0, study })));

        expect(root.querySelector('.study-side__readonly')).toBeNull();
        const sync = root.querySelector<HTMLButtonElement>('under-board .study-tool-tabs > .study-mode--sync');
        expect(sync?.textContent).toContain('SYNC');
        expect(sync?.hidden).toBe(false);

        const nonMemberRoot = renderNodes(studyView(makeModel({ gameId: '', status: 0, username: 'spectator', study })));
        expect(nonMemberRoot.querySelector<HTMLButtonElement>('.study-mode--sync')?.hidden).toBe(true);
        expect(nonMemberRoot.querySelector('.study-side__readonly')).toBeNull();

        expect(root.querySelector('.study-mode--write')).toBeNull();
        expect(root.querySelector('.study-side .study-mode')).toBeNull();
        expect(root.querySelector('.study-side__add')).toBeNull();
        expect(root.querySelector('dialog#study-settings')).toBeNull();
        expect(root.querySelector('#study-tab-comments')).toBeNull();
        expect(root.querySelector('#study-tab-glyphs')).toBeNull();
        expect(root.querySelector('.study-annotations__tags textarea')).toBeNull();
        expect(root.querySelector('.study-tags th')?.textContent).toBe('Event');
        expect(root.querySelector('.study-tags td')?.textContent).toBe('Shared study');
        expect(root.querySelector('#study-tab-description')).toBeNull();
        expect(root.querySelector('.study-desc.chapter-desc .text')?.textContent).toBe('Shared description');
        expect(root.querySelector('.study-desc.chapter-desc .contrib')).toBeNull();
        const shareLinks = [...root.querySelectorAll<HTMLInputElement>('.study-share__copy input')].map(
            input => input.value,
        );
        expect(shareLinks).toEqual([
            'http://127.0.0.1:8080/study/StUdY001',
            'http://127.0.0.1:8080/study/StUdY001/ChAp0001',
            '<iframe width="600" height="371" src="http://127.0.0.1:8080/study/embed/StUdY001/ChAp0001" frameborder="0"></iframe>',
        ]);
        expect(root.querySelector<HTMLFormElement>('.study-share__clone')?.action).toContain('/study/StUdY001/clone');
        expect(root.querySelector('.study-share__clone button')?.textContent).toBe('Clone study');
        expect(root.querySelector('.study-export__chapter')?.textContent).toBe('Download chapter PGN');
        expect(root.querySelector('.study-export__study')?.textContent).toBe('Download study PGN');
    });

    test('Study move list keeps next chapter scrollable and fork choices fixed', () => {
        const study = {
            canWrite: false,
            chapter: { id: 'ChAp0001', mode: 'normal' },
            chapters: [
                { id: 'ChAp0001', name: 'First', order: 1, orientation: 'white', mode: 'normal' },
                { id: 'ChAp0002', name: 'Second', order: 2, orientation: 'white', mode: 'normal' },
            ],
        } as unknown as StudyPageModel;
        const e4 = {
            id: 'e4',
            path: 'e4',
            ply: 1,
            step: makeStep('e4 b - - 0 1', 'e2e4', 'black', 'e4'),
            children: [],
        };
        const e3 = {
            id: 'e3',
            path: 'e3',
            ply: 1,
            step: makeStep('e3 b - - 0 1', 'e2e3', 'black', 'e3'),
            children: [],
        };
        const d4 = {
            id: 'd4',
            path: 'd4',
            ply: 1,
            step: makeStep('d4 b - - 0 1', 'd2d4', 'black', 'd4'),
            children: [],
        };
        const activateTreePath = jest.fn();
        const ctrl = {
            analysisPath: '',
            analysisExtension: { isTreeNodeVisible: () => true },
            getTreeMainlineEndPath: () => '',
            getTreeNodeAtPath: () => ({ children: [e4, e3, d4] }),
            getTreeMainChildPath: () => 'e4',
            activateTreePath,
        } as unknown as AnalysisController;
        const goToChapter = jest.fn();
        const moveListEnd = renderNodes(renderStudyMoveListEnd(study, ctrl, goToChapter));
        const footer = renderNodes(renderStudyMoveListFooter(study, ctrl));

        const next = moveListEnd.querySelector<HTMLButtonElement>('.study-next-chapter')!;
        expect(next.textContent).toContain('Next chapter');
        expect(next.classList.contains('highlighted')).toBe(true);
        expect([...footer.querySelectorAll('.study-move-fork__move')].map(move => move.textContent)).toEqual([
            '1.e4',
            '1.e3',
            '1.d4',
        ]);
        expect(footer.querySelector('.study-move-fork__move.selected')?.getAttribute('data-path')).toBe('e4');

        footer.querySelector<HTMLButtonElement>('[data-path="e3"]')!.click();
        expect(activateTreePath).toHaveBeenCalledWith('e3');
        next.click();
        expect(goToChapter).toHaveBeenCalledWith('ChAp0002');
    });

    test('study sharing permission hides share and export tools', () => {
        const study: StudyPageModel = {
            id: 'StUdY001',
            name: 'Restricted ideas',
            owner: 'owner',
            visibility: 'public',
            isOwner: false,
            canWrite: false,
            canClone: false,
            canShare: false,
            canEmbed: false,
            features: { computer: false, explorer: false },
            settings: {
                computer: 'owner',
                explorer: 'owner',
                cloneable: 'owner',
                shareable: 'owner',
            },
            canLike: true,
            liked: false,
            likes: 0,
            topics: [],
            maxTopics: 30,
            topicMinLength: 2,
            topicMaxLength: 50,
            members: { owner: 'write' },
            maxMembers: 30,
            sharedChapter: 'ChAp0001',
            sharedPath: '',
            roomSnapshotToken: 'room-snapshot',
            chapter: {
                id: 'ChAp0001',
                name: 'Shared line',
                revision: 1,
                order: 1,
                orientation: 'white',
                variant: 'chess',
                chess960: false,
                initialFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
                variantIni: null,
                createdAt: '2026-09-06T08:00:00+00:00',
                description: '',
                tags: {},
                tree: { nodes: [] },
            },
            chapters: [{ id: 'ChAp0001', name: 'Shared line', order: 1, orientation: 'white' }],
        };
        const root = renderNodes(studyView(makeModel({ gameId: '', status: 0, study })));

        expect(root.querySelector<HTMLButtonElement>('.study-mode--sync')?.hidden).toBe(true);
        expect(root.querySelector('#study-tab-export')).toBeNull();
        expect(root.querySelector('#study-panel-export')).toBeNull();
        expect(root.querySelector('.study-share__copy')).toBeNull();
        expect(root.querySelector('.study-export__chapter')).toBeNull();
        expect(root.querySelector('.study-export__study')).toBeNull();
    });

    test('switching Study chapters refreshes share and embed links', () => {
        const study: StudyPageModel = {
            id: 'StUdY001',
            name: 'Shared ideas',
            owner: 'owner',
            visibility: 'public',
            isOwner: false,
            canWrite: true,
            canClone: true,
            canLike: true,
            liked: false,
            likes: 2,
            topics: [],
            maxTopics: 30,
            topicMinLength: 2,
            topicMaxLength: 50,
            members: { owner: 'write', tester: 'write' },
            maxMembers: 30,
            sharedChapter: 'ChAp0001',
            sharedPath: '',
            roomSnapshotToken: 'room-snapshot',
            chapter: {
                id: 'ChAp0001',
                name: 'First line',
                revision: 1,
                order: 1,
                orientation: 'white',
                variant: 'chess',
                chess960: false,
                initialFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
                variantIni: null,
                createdAt: '2026-09-06T08:00:00+00:00',
                description: '',
                tags: {},
                tree: { nodes: [] },
            },
            chapters: [
                { id: 'ChAp0001', name: 'First line', order: 1, orientation: 'white' },
                { id: 'ChAp0002', name: 'Second line', order: 2, orientation: 'black' },
            ],
        };
        const model = makeModel({ gameId: '', status: 0, study });
        const root = renderNodes(studyView(model));

        study.chapter = { ...study.chapter, id: 'ChAp0002', name: 'Second line', order: 2 };
        updateStudyUnderboardChapter(study, model);

        const shareLinks = [...root.querySelectorAll<HTMLInputElement>('.study-share__copy input')].map(
            input => input.value,
        );
        expect(shareLinks).toEqual([
            'http://127.0.0.1:8080/study/StUdY001',
            'http://127.0.0.1:8080/study/StUdY001/ChAp0002',
            '<iframe width="600" height="371" src="http://127.0.0.1:8080/study/embed/StUdY001/ChAp0002" frameborder="0"></iframe>',
        ]);
        expect(root.querySelector('.study-underboard__name')?.textContent).toBe('Shared ideas: Second line');
    });

    test('Practice learner uses the dedicated compact sidebar and lesson underboard', () => {
        const study: StudyPageModel = {
            id: 'PrAc0001',
            name: 'Imported practice study',
            owner: 'teacher',
            visibility: 'public',
            isOwner: false,
            canWrite: false,
            canClone: false,
            canLike: false,
            liked: false,
            likes: 0,
            topics: [],
            maxTopics: 30,
            topicMinLength: 2,
            topicMaxLength: 50,
            members: { teacher: 'write' },
            maxMembers: 30,
            sharedChapter: 'ChAp0002',
            sharedPath: '',
            roomSnapshotToken: 'practice-room',
            practice: {
                variant: 'chess',
                sectionId: 'pawn-endgames',
                sectionName: 'Pawn Endgames',
                studyTitle: '7th-Rank Rook Pawn',
                studyDescription: 'Versus a Queen',
                studyIcon: 'stone-tower',
                menu: [
                    {
                        id: 'pawn-endgames',
                        name: 'Pawn Endgames',
                        studies: [
                            {
                                id: 'PrAc0001',
                                name: '7th-Rank Rook Pawn',
                                url: '/practice/chess/PrAc0001',
                            },
                        ],
                    },
                ],
                indexUrl: '/practice/chess',
                studyUrl: '/practice/chess/PrAc0001',
                completedChapterIds: ['ChAp0001'],
                persistProgress: false,
                goal: { result: 'mate' },
            },
            chapter: {
                id: 'ChAp0002',
                name: 'Not a Bishop or Rook pawn = Win',
                revision: 1,
                order: 2,
                orientation: 'white',
                mode: 'normal',
                variant: 'chess',
                chess960: false,
                initialFen: '7K/8/1Q6/8/8/8/3kp3/8 w - - 0 1',
                variantIni: null,
                createdAt: '2026-09-26T08:00:00+00:00',
                description: 'Chapter lesson text',
                tags: { Event: 'Should not be shown in Practice' },
                tree: { nodes: [] },
            },
            chapters: [
                { id: 'ChAp0001', name: 'Exercise: Queen in front = Win', order: 1, orientation: 'white' },
                { id: 'ChAp0002', name: 'Not a Bishop or Rook pawn = Win', order: 2, orientation: 'white' },
            ],
        };

        localStorage.removeItem('practice_autoNext');
        const root = renderNodes(studyView(makeModel({ gameId: '', status: 0, study })));

        expect(root.querySelector('.practice-study-side__title h1')?.textContent).toBe('7th-Rank Rook Pawn');
        expect(root.querySelector('.practice-study-side__title em')?.textContent).toBe('Versus a Queen');
        expect(root.querySelector('.study-side__tabs')).toBeNull();
        expect(root.querySelectorAll('.practice-study-chapter')).toHaveLength(2);
        expect(root.querySelector('.practice-study-chapter.completed .practice-study-chapter__status')?.textContent).toBe(
            '✓',
        );
        expect(root.querySelector('.practice-study-chapter.active .practice-study-chapter__status')?.textContent).toBe(
            '▶',
        );
        expect(root.querySelectorAll('.study-side__add')).toHaveLength(0);
        expect(root.querySelector<HTMLAnchorElement>('.practice-study-side__back')?.getAttribute('href')).toBe(
            '/practice/chess',
        );
        expect(root.querySelector<HTMLSelectElement>('.practice-study-side__selector')?.value).toBe(
            '/practice/chess/PrAc0001',
        );
        expect(root.querySelector('.study-practice-underboard__goal')?.textContent).toBe('Checkmate the opponent.');
        expect(root.querySelector('.study-practice-underboard__comment')?.textContent).toBe('Chapter lesson text');
        const autoNext = root.querySelector<HTMLInputElement>('#practice-auto-next')!;
        expect(autoNext.checked).toBe(true);
        autoNext.checked = false;
        autoNext.dispatchEvent(new Event('change', { bubbles: true }));
        expect(localStorage.getItem('practice_autoNext')).toBe('false');
        study.chapter.description = 'Restored after chapter navigation';
        updateStudyUnderboardChapter(study, makeModel({ gameId: '', status: 0, study }));
        expect(root.querySelector('.study-practice-underboard__comment')?.textContent).toBe(
            'Restored after chapter navigation',
        );
        expect(root.querySelector('.study-tags')).toBeNull();
        expect(root.querySelector('.study-tool-tabs')).toBeNull();
    });

    test('study embed reuses the lean analysis embed shell', () => {
        const study: StudyPageModel = {
            id: 'StUdY001',
            name: 'Shared ideas',
            owner: 'owner',
            visibility: 'unlisted',
            isOwner: false,
            canWrite: false,
            canClone: false,
            canLike: false,
            liked: false,
            likes: 1,
            topics: [],
            maxTopics: 30,
            topicMinLength: 2,
            topicMaxLength: 50,
            members: { owner: 'write' },
            maxMembers: 30,
            sharedChapter: 'ChAp0001',
            sharedPath: '',
            roomSnapshotToken: 'room-snapshot',
            chapter: {
                id: 'ChAp0001',
                name: 'Shared line',
                revision: 1,
                order: 1,
                orientation: 'black',
                variant: 'chess',
                chess960: false,
                initialFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
                variantIni: null,
                createdAt: '2026-09-06T08:00:00+00:00',
                description: '',
                tags: {},
                tree: { nodes: [] },
            },
            chapters: [{ id: 'ChAp0001', name: 'Shared line', order: 1, orientation: 'black' }],
        };
        const root = renderNodes(studyEmbedView(makeModel({ gameId: '', embed: true, status: 0, study })));

        expect(root.querySelector('.embed-app')).not.toBeNull();
        expect(root.querySelector('#movelist')).not.toBeNull();
        expect(root.querySelector('.study-side')).toBeNull();
        expect(root.querySelector('.study-underboard')).toBeNull();
        const link = root.querySelector<HTMLAnchorElement>('.footer .gamelink')!;
        expect(link.href).toContain('/study/StUdY001/ChAp0001');
        expect(link.textContent).toBe('Shared ideas • Shared line');

        const lessonStudy: StudyPageModel = {
            ...study,
            chapter: { ...study.chapter, mode: 'gamebook' },
            chapters: [{ ...study.chapters[0], mode: 'gamebook' }],
        };
        expect(root.querySelector('.study-embed-preview')).toBeNull();
        expect(root.querySelector('.study-embed-preview__open')).toBeNull();

        const lessonRoot = renderNodes(
            studyEmbedView(makeModel({ gameId: '', embed: true, status: 0, study: lessonStudy })),
        );
        expect(lessonRoot.querySelector('.embed-app')?.classList.contains('study-embed-preview')).toBe(true);
        expect(lessonRoot.querySelector('.embed-app')?.classList.contains('study-embed-gamebook')).toBe(true);
        const start = lessonRoot.querySelector<HTMLAnchorElement>('.study-embed-preview__open')!;
        expect(start.textContent).toBe('Start');
        expect(start.href).toContain('/study/StUdY001/ChAp0001');
        expect(lessonRoot.querySelector('.study-gamebook-play')).toBeNull();

        const practiceStudy: StudyPageModel = {
            ...study,
            chapter: { ...study.chapter, mode: 'practice' },
            chapters: [{ ...study.chapters[0], mode: 'practice' }],
        };
        const practiceRoot = renderNodes(
            studyEmbedView(makeModel({ gameId: '', embed: true, status: 0, study: practiceStudy })),
        );
        expect(practiceRoot.querySelector('.embed-app')?.classList.contains('study-embed-preview')).toBe(true);
        expect(practiceRoot.querySelector('.embed-app')?.classList.contains('study-embed-gamebook')).toBe(false);
        expect(practiceRoot.querySelector('.study-embed-preview__open')?.textContent).toBe('Open study');
        expect(practiceRoot.querySelector('.study-gamebook-play')).toBeNull();

        const concealStudy: StudyPageModel = {
            ...study,
            chapter: { ...study.chapter, mode: 'conceal', concealPly: 3 },
            chapters: [{ ...study.chapters[0], mode: 'conceal' }],
        };
        const concealRoot = renderNodes(
            studyEmbedView(makeModel({ gameId: '', embed: true, status: 0, study: concealStudy })),
        );
        expect(concealRoot.querySelector('.embed-app')?.classList.contains('study-embed-preview')).toBe(true);
        expect(concealRoot.querySelector('.study-embed-preview__open')?.textContent).toBe('Open study');
    });

    test('embed view stays lean and does not render PGN tab content', () => {
        const root = renderNodes(embedView(makeModel({ gameId: 'cPeP5Di1', embed: true })));

        expect(root.querySelector('#movelist')).not.toBeNull();
        expect(root.querySelector('#move-controls')).not.toBeNull();
        expect(root.querySelector('#pgntext')).toBeNull();
        expect(root.querySelector('.footer .gamelink')).not.toBeNull();
    });

    test('puzzle view keeps analysis tools but omits PGN tab content', () => {
        const root = renderNodes(
            puzzleView(
                makeModel({
                    gameId: '',
                    puzzle: JSON.stringify({
                        _id: 'abcde',
                        v: 'chess',
                        f: 'rn1qkbnr/pppb1ppp/8/3pp3/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
                        m: 'e2e4,e7e5',
                        t: 'advantage',
                        e: '+1.2',
                    }),
                }),
            ),
        );

        expect(root.querySelector('#movelist')).not.toBeNull();
        expect(root.querySelector('#move-controls')).not.toBeNull();
        expect(root.querySelector('.analysis-settings')).not.toBeNull();
        expect(root.querySelector('#pgntext')).toBeNull();
    });

    test('round view stays on the legacy round chrome', () => {
        const root = renderNodes(roundView(makeModel({ gameId: 'cPeP5Di1', status: -1 })));

        expect(root.querySelector('#movelist')).not.toBeNull();
        expect(root.querySelector('#move-controls')).not.toBeNull();
        expect(root.querySelector('#game-controls')).not.toBeNull();
        expect(root.querySelector('#pgntext')).toBeNull();
    });

    test('round view keeps the Janggi setup controls in the board grid', () => {
        const root = renderNodes(roundView(makeModel({ variant: 'janggi', gameId: 'cPeP5Di1', status: -2 })));

        expect(root.querySelector('.round-app > #janggi-setup-buttons')).not.toBeNull();
        expect(root.querySelector('under-board #janggi-setup-buttons')).toBeNull();
    });

    test('only the Alice round view includes the optional second board', () => {
        const round = renderNodes(roundView(makeModel({ variant: 'alice', gameId: 'cPeP5Di1', status: -1 })));
        expect(round.querySelector('.round-app.alice-round #aliceboard')).not.toBeNull();

        document.body.innerHTML = '';
        const analysis = renderNodes(analysisView(makeModel({ variant: 'alice', gameId: '', status: 1 })));
        expect(analysis.querySelector('#aliceboard')).toBeNull();
    });
});

describe('analysis tree movelist gating', () => {
    test('tree mode applies analysis-tree classes only when explicitly enabled', () => {
        document.body.innerHTML = '<div id="movelist"></div>';

        const steps: Step[] = [
            makeStep('start w - - 0 1', undefined, 'white'),
            makeStep('s1 b - - 0 1', 'e2e4', 'black', 'e4'),
            makeStep('s2 w - - 0 1', 'e7e5', 'white', 'e5'),
        ];
        const tree = createAnalysisTree(steps);

        const ctrl = {
            steps,
            status: -1,
            result: '*',
            ply: 2,
            plyVari: 0,
            vmovelist: document.getElementById('movelist'),
            variant: { name: 'chess' },
            fog: false,
            mycolor: 'white',
            spectator: true,
            analysisTree: tree,
            hasAnalysisTree: () => true,
            isTreeInlineNotation: () => false,
            getTreeActivePath: () => tree.root.children[0].children[0].path,
            activateTreePath: () => undefined,
        } as any;

        updateMovelist(ctrl, true, false, false);

        const movelist = document.getElementById('movelist')!;
        expect(movelist.classList.contains('analysis-tree')).toBe(true);
        expect(movelist.classList.contains('tview2-column')).toBe(true);
    });

    test('analysis extensions render move-list footer outside the scrolling move tree', () => {
        document.body.innerHTML =
            '<div class="movelist-block"><div id="movelist"></div></div><div id="movelist-footer"></div>';

        const steps: Step[] = [
            makeStep('start w - - 0 1', undefined, 'white'),
            makeStep('s1 b - - 0 1', 'e2e4', 'black', 'e4'),
        ];
        const tree = createAnalysisTree(steps);
        const ctrl = {
            steps,
            status: -1,
            result: '*',
            ply: 1,
            plyVari: 0,
            vmovelist: document.getElementById('movelist'),
            variant: { name: 'chess' },
            fog: false,
            mycolor: 'white',
            spectator: true,
            analysisTree: tree,
            analysisExtension: {
                renderMoveListEnd: () => [h('button.study-next-chapter', 'Next chapter')],
                renderMoveListFooter: () => [h('button.study-move-fork', 'Forks')],
            },
            hasAnalysisTree: () => true,
            isTreeInlineNotation: () => false,
            getTreeActivePath: () => tree.root.children[0].path,
            activateTreePath: () => undefined,
        } as any;

        updateMovelist(ctrl, true, false, false);
        updateMovelist(ctrl, true, false, false);

        const nextButtons = document.querySelectorAll('#movelist .study-next-chapter');
        expect(nextButtons).toHaveLength(1);
        expect(nextButtons[0].textContent).toBe('Next chapter');
        expect(document.querySelector('#movelist .study-move-fork')).toBeNull();
        const footerButtons = document.querySelectorAll('#movelist-footer .study-move-fork');
        expect(footerButtons).toHaveLength(1);
        expect(footerButtons[0].textContent).toBe('Forks');
    });

    test('study comments interrupt move pairs and keep imported text inert', () => {
        document.body.innerHTML = '<div id="movelist"></div>';
        const steps = [
            makeStep('start w - - 0 1', undefined, 'white'),
            makeStep('s1 b - - 0 1', 'e2e4', 'black', 'e4'),
            makeStep('s2 w - - 0 1', 'e7e5', 'white', 'e5'),
        ];
        const tree = createAnalysisTree(steps);
        tree.root.annotations = {
            shapes: [],
            nags: [],
            comments: [{ id: 'rootnote', author: 'tester', text: 'Start here\nlichess.org/study/example' }],
        };
        tree.root.children[0].annotations = {
            shapes: [],
            nags: [],
            comments: [{ id: 'movenote', author: 'tester', text: '<img src=x onerror=alert(1)>' }],
        };
        const ctrl = {
            steps,
            status: 0,
            result: '*',
            ply: 2,
            plyVari: 0,
            vmovelist: document.getElementById('movelist'),
            variant: { name: 'chess' },
            analysisContext: { capabilities: { gamePanels: false } },
            fog: false,
            mycolor: 'white',
            spectator: true,
            analysisTree: tree,
            hasAnalysisTree: () => true,
            isTreeInlineNotation: () => false,
            getTreeActivePath: () => '',
            activateTreePath: () => undefined,
        } as any;
        updateMovelist(ctrl, true, false);
        const list = document.getElementById('movelist')!;
        expect(list.querySelectorAll('interrupt .tree-comment')).toHaveLength(2);
        expect(list.querySelector('img')).toBeNull();
        const commentLink = list.querySelector<HTMLAnchorElement>('.tree-comment a')!;
        expect(commentLink.getAttribute('href')).toBe('https://lichess.org/study/example');
        expect(commentLink.textContent).toBe('lichess.org/study/example');
        expect(list.querySelector('.result, .status')).toBeNull();
        expect([...list.children].map(el => el.tagName.toLowerCase())).toEqual([
            'interrupt',
            'index',
            'move',
            'move',
            'interrupt',
            'index',
            'move',
            'move',
        ]);
        ctrl.isTreeInlineNotation = () => true;
        updateMovelist(ctrl, true, false);
        expect(document.querySelectorAll('#movelist .tree-comment')).toHaveLength(2);
        expect(document.querySelectorAll('#movelist move:not(.empty)')).toHaveLength(2);
    });

    test('legacy controllers keep the old movelist structure', () => {
        document.body.innerHTML = '<div id="movelist"></div>';

        const steps: Step[] = [
            makeStep('start w - - 0 1', undefined, 'white'),
            makeStep('s1 b - - 0 1', 'e2e4', 'black', 'e4'),
            makeStep('s2 w - - 0 1', 'e7e5', 'white', 'e5'),
        ];

        const ctrl = {
            steps,
            status: -1,
            result: '*',
            ply: 2,
            plyVari: 0,
            vmovelist: document.getElementById('movelist'),
            variant: { name: 'chess' },
            fog: false,
            mycolor: 'white',
            spectator: true,
            goPly: () => undefined,
        } as any;

        updateMovelist(ctrl, true, false, false);

        const movelist = document.getElementById('movelist')!;
        expect(movelist.classList.contains('analysis-tree')).toBe(false);
        expect(movelist.classList.contains('tview2-column')).toBe(false);
        expect(movelist.querySelector('move.counter')).not.toBeNull();
    });

    test('disclosure mode hides buttons but still respects collapsed sidelines when disabled', () => {
        document.body.innerHTML = '<div id="movelist"></div>';

        const steps: Step[] = [
            makeStep('start w - - 0 1', undefined, 'white'),
            makeStep('s1 b - - 0 1', 'e2e4', 'black', 'e4'),
            makeStep('s2 w - - 0 1', 'e7e5', 'white', 'e5'),
        ];
        const tree = createAnalysisTree(steps);
        const ply1Path = mainlinePathAtPly(tree, 1);
        addOrSelectChild(tree, ply1Path, makeStep('v1 w - - 0 1', 'c7c5', 'white', 'c5'), false);
        const parent = tree.root.children[0];
        parent.collapsed = true;

        const ctrl = {
            steps,
            status: -1,
            result: '*',
            ply: 2,
            plyVari: 0,
            vmovelist: document.getElementById('movelist'),
            variant: { name: 'chess' },
            fog: false,
            mycolor: 'white',
            spectator: true,
            analysisTree: tree,
            hasAnalysisTree: () => true,
            isTreeInlineNotation: () => true,
            isTreeDisclosureMode: () => true,
            getTreeActivePath: () => tree.root.children[0].children[0].path,
            getTreeSelectedChildPath: () => tree.root.children[0].children[0].path,
            activateTreePath: () => undefined,
            toggleTreeCollapsed: () => undefined,
        } as any;

        updateMovelist(ctrl, true, false, false);
        expect(document.getElementById('movelist')!.textContent).not.toContain('c5');
        expect(document.querySelector('#movelist button.disclosure')).not.toBeNull();

        ctrl.isTreeDisclosureMode = () => false;
        updateMovelist(ctrl, true, false, false);
        expect(document.getElementById('movelist')!.textContent).not.toContain('c5');
        expect(document.querySelector('#movelist button.disclosure')).toBeNull();
    });

    test('inline notation keeps sibling sidelines as siblings, not nested sub-variations', () => {
        document.body.innerHTML = '<div id="movelist"></div>';

        const steps: Step[] = [
            makeStep('start w - - 0 1', undefined, 'white'),
            makeStep('s1 b - - 0 1', 'e2e4', 'black', 'e4'),
            makeStep('s2 w - - 0 1', 'e7e5', 'white', 'e5'),
            makeStep('s3 b - - 0 1', 'g1f3', 'black', 'Nf3'),
            makeStep('s4 w - - 0 1', 'g8f6', 'white', 'Nf6'),
        ];
        const tree = createAnalysisTree(steps);
        const blackReplyPath = mainlinePathAtPly(tree, 3);
        addOrSelectChild(tree, blackReplyPath, makeStep('v1 w - - 0 1', 'h7h6', 'white', 'h6'), false);
        addOrSelectChild(tree, blackReplyPath, makeStep('v2 w - - 0 1', 'd7d5', 'white', 'd5'), false);

        const ctrl = {
            steps,
            status: -1,
            result: '*',
            ply: 4,
            plyVari: 0,
            vmovelist: document.getElementById('movelist'),
            variant: { name: 'chess' },
            fog: false,
            mycolor: 'white',
            spectator: true,
            analysisTree: tree,
            hasAnalysisTree: () => true,
            isTreeInlineNotation: () => true,
            isTreeDisclosureMode: () => false,
            getTreeActivePath: () => mainlinePathAtPly(tree, 4),
            getTreeSelectedChildPath: () => undefined,
            activateTreePath: () => undefined,
            toggleTreeCollapsed: () => undefined,
        } as any;

        updateMovelist(ctrl, true, false, false);

        const sans = [...document.querySelectorAll('#movelist san')].map(el => el.textContent);
        expect(sans.filter(san => san === 'h6')).toHaveLength(1);
        expect(sans.filter(san => san === 'd5')).toHaveLength(1);
        expect(document.querySelectorAll('#movelist inline inline')).toHaveLength(0);
    });

    test('column disclosure button is rendered on the branched reply move', () => {
        document.body.innerHTML = '<div id="movelist"></div>';

        const steps: Step[] = [
            makeStep('start w - - 0 1', undefined, 'white'),
            makeStep('s1 b - - 0 1', 'e2e4', 'black', 'e4'),
            makeStep('s2 w - - 0 1', 'e7e5', 'white', 'e5'),
            makeStep('s3 b - - 0 1', 'g1f3', 'black', 'Nf3'),
            makeStep('s4 w - - 0 1', 'b8c6', 'white', 'Nc6'),
            makeStep('s5 b - - 0 1', 'f1b5', 'black', 'Bb5'),
            makeStep('s6 w - - 0 1', 'a7a6', 'white', 'a6'),
            makeStep('s7 b - - 0 1', 'b5a4', 'black', 'Ba4'),
        ];
        const tree = createAnalysisTree(steps);
        const white4Path = mainlinePathAtPly(tree, 5);
        addOrSelectChild(tree, white4Path, makeStep('v1 w - - 0 1', 'g8f6', 'white', 'Nf6'), false);
        addOrSelectChild(tree, white4Path, makeStep('v2 w - - 0 1', 'f8c5', 'white', 'Bc5'), false);
        addOrSelectChild(tree, white4Path, makeStep('v3 w - - 0 1', 'd7d6', 'white', 'd6'), false);

        const ctrl = {
            steps,
            status: -1,
            result: '*',
            ply: 7,
            plyVari: 0,
            vmovelist: document.getElementById('movelist'),
            variant: { name: 'chess' },
            fog: false,
            mycolor: 'white',
            spectator: true,
            analysisTree: tree,
            hasAnalysisTree: () => true,
            isTreeInlineNotation: () => false,
            isTreeDisclosureMode: () => true,
            getTreeActivePath: () =>
                tree.root.children[0].children[0].children[0].children[0].children[0].children[0].children[0].path,
            getTreeSelectedChildPath: () => undefined,
            activateTreePath: () => undefined,
            toggleTreeCollapsed: () => undefined,
        } as any;

        updateMovelist(ctrl, true, false, false);

        expect(document.querySelectorAll('#movelist button.disclosure')).toHaveLength(1);

        const disclosureMove = document.querySelector('#movelist > move button.disclosure')?.parentElement;
        expect(disclosureMove?.textContent).toContain('a6');
        expect(disclosureMove?.textContent).not.toContain('Ba4');
    });

    test('tree nodes expose selected-line state, SAN suffixes and persisted NAG glyphs', () => {
        document.body.innerHTML = '<div id="movelist"></div>';

        const steps: Step[] = [
            makeStep('start w - - 0 1', undefined, 'white'),
            makeStep('s1 b - - 0 1', 'e2e4', 'black', 'e4!'),
            makeStep('s2 w - - 0 1', 'e7e5', 'white', 'e5'),
            makeStep('s3 b - - 0 1', 'g1f3', 'black', 'Nf3'),
        ];
        const tree = createAnalysisTree(steps);
        const e4Path = mainlinePathAtPly(tree, 1);
        tree.root.children[0].children[0].annotations = { shapes: [], comments: [], nags: [3, 7] };
        addOrSelectChild(tree, e4Path, makeStep('v1 w - - 0 1', 'c7c5', 'white', 'c5?!'), false);

        const ctrl = {
            steps,
            status: 1,
            result: '*',
            ply: 3,
            plyVari: 0,
            vmovelist: document.getElementById('movelist'),
            variant: { name: 'chess' },
            fog: false,
            mycolor: 'white',
            spectator: true,
            recordedMainlinePly: 3,
            analysisTree: tree,
            hasAnalysisTree: () => true,
            isTreeInlineNotation: () => true,
            isTreeDisclosureMode: () => false,
            getTreeActivePath: () => tree.root.children[0].children[0].children[0].path,
            getTreeSelectedChildPath: () => tree.root.children[0].children[0].children[0].path,
            activateTreePath: () => undefined,
            toggleTreeCollapsed: () => undefined,
        } as any;

        updateMovelist(ctrl, true, false, false);

        const firstMove = document.querySelector('#movelist move[data-path="01"]') as HTMLElement | null;
        expect(firstMove?.classList.contains('recorded')).toBe(true);
        expect(firstMove?.classList.contains('currentline')).toBe(true);
        expect(firstMove?.querySelector('san')?.textContent).toBe('e4');
        expect(firstMove?.querySelector('glyph.good')?.textContent).toBe('!');

        const secondMove = document.querySelector('#movelist move[data-path="01.02"]') as HTMLElement | null;
        expect(secondMove?.querySelector('glyph.brilliant')?.textContent).toBe('!!');
        expect([...secondMove!.querySelectorAll('glyph')].some(glyph => glyph.textContent === '□')).toBe(true);

        const sidelineMove = document.querySelector('#movelist move[data-path="01.04"]') as HTMLElement | null;
        expect(sidelineMove?.classList.contains('sideline')).toBe(true);
        expect(sidelineMove?.querySelector('san')?.textContent).toBe('c5');
        expect(sidelineMove?.querySelector('glyph.inaccuracy')?.textContent).toBe('?!');
    });

    test('tree context menu renders lichess-style actions for the selected move', () => {
        document.body.innerHTML = '<div id="movelist"></div>';

        const steps: Step[] = [
            makeStep('start w - - 0 1', undefined, 'white'),
            makeStep('s1 b - - 0 1', 'e2e4', 'black', 'e4'),
            makeStep('s2 w - - 0 1', 'e7e5', 'white', 'e5'),
            makeStep('s3 b - - 0 1', 'g1f3', 'black', 'Nf3'),
            makeStep('s4 w - - 0 1', 'b8c6', 'white', 'Nc6'),
            makeStep('s5 b - - 0 1', 'f1b5', 'black', 'Bb5'),
            makeStep('s6 w - - 0 1', 'a7a6', 'white', 'a6'),
        ];
        const tree = createAnalysisTree(steps);
        const branchPath = mainlinePathAtPly(tree, 5);
        addOrSelectChild(tree, branchPath, makeStep('v1 w - - 0 1', 'g8f6', 'white', 'Nf6'), false);

        const ctrl = {
            steps,
            status: -1,
            result: '*',
            ply: 6,
            plyVari: 0,
            vmovelist: document.getElementById('movelist'),
            variant: { name: 'chess' },
            fog: false,
            mycolor: 'white',
            spectator: true,
            analysisTree: tree,
            hasAnalysisTree: () => true,
            isTreeInlineNotation: () => false,
            isTreeDisclosureMode: () => true,
            getTreeActivePath: () =>
                tree.root.children[0].children[0].children[0].children[0].children[0].children[0].path,
            getTreeSelectedChildPath: () => undefined,
            getTreeNodeAtPath: (path: string) =>
                path === branchPath ? tree.root.children[0].children[0].children[0].children[0].children[0] : undefined,
            pathIsTreeMainline: () => false,
            canPromoteTreeVariation: () => true,
            someTreeCollapsed: (collapsed: boolean) => !collapsed,
            getTreeContextMenu: () => ({ path: branchPath, x: 12, y: 18 }),
            activateTreePath: () => undefined,
            toggleTreeCollapsed: () => undefined,
            copyTreeLinePgn: () => undefined,
            promoteTreeVariation: () => undefined,
            collapseAllTree: () => undefined,
            expandAllTree: () => undefined,
            deleteTreeNode: () => undefined,
            closeTreeContextMenu: () => undefined,
        } as any;

        updateMovelist(ctrl, true, false, false);

        const menu = document.querySelector('#movelist .tree-context-menu') as HTMLElement | null;
        expect(menu).not.toBeNull();
        expect(menu?.textContent).toContain('Bb5');
        expect(menu?.textContent).toContain('Copy variation PGN');
        expect(menu?.textContent).toContain('Promote variation');
        expect(menu?.textContent).toContain('Make main line');
        expect(menu?.textContent).toContain('Collapse all');
        expect(menu?.textContent).toContain('Delete from here');
        expect(menu?.querySelectorAll('button i.icon').length).toBeGreaterThanOrEqual(5);
        expect(menu?.textContent).not.toContain('Copy full tree PGN');
        expect(menu?.textContent).not.toContain('Jump to branch point');
    });

    test('tree context menu keeps delete action on mainline nodes', () => {
        document.body.innerHTML = '<div id="movelist"></div>';

        const steps: Step[] = [
            makeStep('start w - - 0 1', undefined, 'white'),
            makeStep('s1 b - - 0 1', 'e2e4', 'black', 'e4'),
            makeStep('s2 w - - 0 1', 'e7e5', 'white', 'e5'),
            makeStep('s3 b - - 0 1', 'g1f3', 'black', 'Nf3'),
        ];
        const tree = createAnalysisTree(steps);
        const mainlinePath = mainlinePathAtPly(tree, 2);
        const mainlineNode = tree.root.children[0].children[0];

        const ctrl = {
            steps,
            status: -1,
            result: '*',
            ply: 3,
            plyVari: 0,
            vmovelist: document.getElementById('movelist'),
            variant: { name: 'chess' },
            fog: false,
            mycolor: 'white',
            spectator: true,
            analysisTree: tree,
            hasAnalysisTree: () => true,
            isTreeInlineNotation: () => false,
            isTreeDisclosureMode: () => false,
            getTreeActivePath: () => mainlinePath,
            getTreeSelectedChildPath: () => undefined,
            getTreeNodeAtPath: (path: string) => (path === mainlinePath ? mainlineNode : undefined),
            pathIsTreeMainline: () => true,
            pathIsTreeForcedVariation: () => false,
            canPromoteTreeVariation: () => false,
            someTreeCollapsed: () => false,
            getTreeContextMenu: () => ({ path: mainlinePath, x: 12, y: 18 }),
            activateTreePath: () => undefined,
            toggleTreeCollapsed: () => undefined,
            copyTreeLinePgn: () => undefined,
            promoteTreeVariation: () => undefined,
            forceTreeVariation: () => undefined,
            collapseAllTree: () => undefined,
            expandAllTree: () => undefined,
            deleteTreeNode: () => undefined,
            closeTreeContextMenu: () => undefined,
        } as any;

        updateMovelist(ctrl, true, false, false);

        const menu = document.querySelector('#movelist .tree-context-menu') as HTMLElement | null;
        expect(menu).not.toBeNull();
        expect(menu?.textContent).toContain('Convert to variation');
        expect(menu?.textContent).toContain('Copy main line PGN');
        expect(menu?.textContent).toContain('Delete from here');
    });
});

describe('Study conceal reader rendering', () => {
    test('hidden SAN, forks and annotations stay out of the rendered move tree until played', () => {
        document.body.innerHTML = '<div id="movelist"></div>';
        const steps = [
            makeStep('start w - - 0 1', undefined, 'white'),
            makeStep('s1 b - - 0 1', 'e2e4', 'black', 'e4'),
            makeStep('s2 w - - 0 1', 'e7e5', 'white', 'e5'),
            makeStep('s3 b - - 0 1', 'g1f3', 'black', 'Nf3'),
        ];
        const tree = createAnalysisTree(steps);
        const e4 = tree.root.children[0];
        const e5 = e4.children[0];
        e5.annotations = {
            shapes: [],
            nags: [1],
            comments: [{ id: 'secret', author: 'owner', text: 'Secret continuation' }],
        };
        addOrSelectChild(tree, e4.path, makeStep('sicilian w - - 0 1', 'c7c5', 'white', 'c5'), false);

        const host = { analysisTree: tree, analysisPath: e4.path };
        const conceal = new StudyConcealController(
            host,
            1,
            studySessionPolicy({
                mode: 'conceal',
                canWrite: false,
                computerAllowed: true,
                savedRecording: true,
                savedSynchronization: false,
                activeGame: false,
            }),
        );
        const ctrl = {
            steps,
            status: -1,
            result: '*',
            ply: 1,
            plyVari: 0,
            vmovelist: document.getElementById('movelist'),
            variant: { name: 'chess' },
            fog: false,
            mycolor: 'white',
            spectator: true,
            analysisTree: tree,
            analysisExtension: {
                isTreeNodeVisible: (node: any) => conceal.isTreeNodeVisible(node),
                areTreeNodeAnnotationsVisible: (node: any) => conceal.areTreeNodeAnnotationsVisible(node),
            },
            hasAnalysisTree: () => true,
            isTreeInlineNotation: () => false,
            isTreeDisclosureMode: () => false,
            getTreeActivePath: () => host.analysisPath,
            getTreeSelectedChildPath: () => undefined,
            activateTreePath: () => undefined,
        } as any;

        updateMovelist(ctrl, true, false, false);
        expect(document.getElementById('movelist')!.textContent).toContain('e4');
        expect(document.getElementById('movelist')!.textContent).not.toContain('e5');
        expect(document.getElementById('movelist')!.textContent).not.toContain('c5');

        host.analysisPath = e5.path;
        updateMovelist(ctrl, true, false, false);
        expect(document.getElementById('movelist')!.textContent).toContain('e5');
        expect(document.getElementById('movelist')!.textContent).not.toContain('Nf3');
        expect(document.getElementById('movelist')!.textContent).not.toContain('c5');
        expect(document.getElementById('movelist')!.textContent).not.toContain('Secret continuation');
        expect(document.querySelector('#movelist glyph')).toBeNull();
    });
});

describe('Study conceal mode shell', () => {
    function concealStudy(canWrite: boolean, isOwner: boolean): StudyPageModel {
        return {
            id: 'StUdY001',
            name: 'Concealed ideas',
            owner: 'owner',
            visibility: 'unlisted',
            isOwner,
            canWrite,
            canClone: true,
            canLike: true,
            liked: false,
            likes: 0,
            topics: [],
            maxTopics: 30,
            topicMinLength: 2,
            topicMaxLength: 50,
            members: { owner: 'write', ...(canWrite ? { tester: 'write' as const } : {}) },
            maxMembers: 30,
            sharedChapter: 'ChAp0001',
            sharedPath: '',
            roomSnapshotToken: 'room-snapshot',
            chapter: {
                id: 'ChAp0001',
                name: 'Hidden line',
                revision: 1,
                snapshotToken: 'chapter-snapshot',
                order: 1,
                orientation: 'white',
                mode: 'conceal',
                concealPly: 1,
                variant: 'chess',
                chess960: false,
                initialFen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
                variantIni: null,
                createdAt: '2026-09-14T12:00:00+00:00',
                description: '',
                tags: {},
                serverEval: null,
                tree: { nodes: [] },
            },
            chapters: [
                {
                    id: 'ChAp0001',
                    name: 'Hidden line',
                    order: 1,
                    orientation: 'white',
                    mode: 'conceal',
                    concealPly: 1,
                },
            ],
        };
    }

    test('reader shell keeps the ordinary Study chrome while the move tree conceals future moves', () => {
        const study = concealStudy(false, false);
        const root = renderNodes(studyView(makeModel({ gameId: '', status: 0, study })));
        const app = root.querySelector('.study-app')!;

        expect(app.classList.contains('study-conceal-playback')).toBe(true);
        expect(root.querySelector('.study-conceal-status')).toBeNull();
        expect(root.querySelector('.study-mode--write')).toBeNull();
        expect(root.querySelector<HTMLButtonElement>('#study-tab-serverEval')?.hidden).toBe(true);
        expect(root.querySelector('#study-tab-export')).not.toBeNull();
    });

    test('author shell relies on faded concealed moves instead of a separate reveal-status card', () => {
        const study = concealStudy(true, false);
        const root = renderNodes(studyView(makeModel({ gameId: '', status: 0, study })));
        const app = root.querySelector('.study-app')!;

        expect(app.classList.contains('study-conceal-playback')).toBe(false);
        expect(root.querySelector('.study-conceal-status')).toBeNull();
        expect(root.querySelector('.study-mode--write')).not.toBeNull();
        expect(root.querySelector('#study-tab-comments')).not.toBeNull();
        expect(root.querySelector('#study-tab-glyphs')).not.toBeNull();
    });
});
