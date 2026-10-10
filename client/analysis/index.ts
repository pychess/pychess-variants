import { h, VNode } from 'snabbdom';

import { _ } from '../i18n';
import { AnalysisController } from './analysisCtrl';
import { gameInfo } from '../gameInfo';
import { selectVariant, VARIANTS, validVariant } from '../variants';
import { renderTimeago } from '../datetime';
import { spinner, srHeading } from '../view';
import { PyChessModel } from '../types';
import { analysisContext, type AnalysisContext } from './analysisContext';
import { renderAnalysisPage } from './analysisPage';
import { studyTreeFromAnalysisTree } from '../study/studyTree';
import { chooseStudy } from '../study/addToStudy';
import { extractPgnTags } from '../pgn';

export { analysisTools, gauge, renderAnalysisPage } from './analysisPage';
export type { AnalysisPageParts } from './analysisPage';

function runGround(vnode: VNode, model: PyChessModel, onReady?: (ctrl: AnalysisController) => void) {
    const el = vnode.elm as HTMLElement;
    const ctrl = new AnalysisController(el, model);
    window['onFSFline'] = ctrl.onFSFline;
    onReady?.(ctrl);
}

function analysisSide(model: PyChessModel, context: AnalysisContext) {
    if (!context.analysisBoard) {
        return [gameInfo(model), srHeading('h2', _('Chat')), h('div#roundchat')];
    }

    const setVariant = (isInput: boolean) => {
        const e = document.getElementById('variant') as HTMLSelectElement;
        const variant = e.options[e.selectedIndex].value;
        if (isInput) window.location.assign('/analysis/' + validVariant(variant));
    };

    const vVariant = model.variant || 'chess';

    return h('div.container', [
        h('div', [
            h('label', { attrs: { for: 'variant' } }, _('Variant')),
            selectVariant(
                'variant',
                vVariant,
                () => setVariant(true),
                () => setVariant(false),
                [],
                model.gameCategory,
            ),
        ]),
    ]);
}

export function renderEmbedPage(
    model: PyChessModel,
    mountBoard: (vnode: VNode) => void,
    footer: VNode,
    overlay?: VNode,
): VNode[] {
    const variant = VARIANTS[model.variant];

    return [
        h('div.embed-app', [
            h(`selection#mainboard.${variant.boardFamily}.${variant.pieceFamily}.${variant.ui.boardMark}`, [
                h('div.cg-wrap.' + variant.board.cg, { hook: { insert: mountBoard } }),
            ]),

            h('div.pocket-top', [
                h('div.' + variant.pieceFamily + '.' + model['variant'], [
                    h('div.cg-wrap.pocket', [h('div#pocket0.pocketrow')]),
                ]),
            ]),

            h('div.analysis-tools', [
                h('div.movelist-block', [h('div#movelist')]),
                h('div#misc-info', [h('div#misc-infow'), h('div#misc-info-center'), h('div#misc-infob')]),
            ]),

            h('div#move-controls'),

            h('div.pocket-bot', [
                h('div.' + variant.pieceFamily + '.' + model['variant'], [
                    h('div.cg-wrap.pocket', [h('div#pocket1.pocketrow')]),
                ]),
            ]),

            ...(overlay ? [overlay] : []),
        ]),
        h('div.footer', [footer]),
    ];
}

export function embedView(model: PyChessModel): VNode[] {
    const variant = VARIANTS[model.variant];
    const chess960 = model.chess960 === 'True';
    return renderEmbedPage(
        model,
        vnode => runGround(vnode, model),
        h(
            'a.gamelink',
            { attrs: { rel: 'noopener', target: '_blank', href: '/' + model['gameId'] } },
            [variant.displayName(chess960), '•', model.wtitle, model.wplayer, 'vs', model.btitle, model.bplayer].join(
                ' ',
            ),
        ),
    );
}

export function analysisUnderboard(
    model: PyChessModel,
    context: AnalysisContext,
    isOngoingGame: boolean,
    addToStudy?: () => void,
): VNode[] {
    const tabindexCt = context.analysisBoard ? '-1' : '0';
    let tabindexPgn = context.analysisBoard ? '0' : '-1';

    const onClickFullfen = () => {
        const el = document.getElementById('fullfen') as HTMLInputElement;
        el.focus();
        el.select();
    };

    const tabs: VNode[] = [];
    if (!isOngoingGame) {
        tabs.push(
            h(
                'button.site-tab',
                {
                    attrs: {
                        role: 'tab',
                        'aria-selected': false,
                        'aria-controls': 'panel-1',
                        id: 'tab-1',
                        type: 'button',
                    },
                },
                _('Computer analysis'),
            ),
        );
        if (model.rated === '1') {
            tabs.push(
                h(
                    'button.site-tab',
                    {
                        attrs: {
                            role: 'tab',
                            'aria-selected': false,
                            'aria-controls': 'panel-2',
                            id: 'tab-2',
                            type: 'button',
                        },
                    },
                    _('Move times'),
                ),
            );
        }
        if (model.ct) {
            tabs.push(
                h(
                    'button.site-tab',
                    {
                        attrs: {
                            role: 'tab',
                            'aria-selected': false,
                            'aria-controls': 'panel-3',
                            id: 'tab-3',
                            type: 'button',
                            'data-initial': String(tabindexCt === '0'),
                        },
                    },
                    _('Crosstable'),
                ),
            );
        } else {
            tabindexPgn = '0';
        }
        tabs.push(
            h(
                'button.site-tab',
                {
                    attrs: {
                        role: 'tab',
                        'aria-selected': false,
                        'aria-controls': 'panel-4',
                        id: 'tab-4',
                        type: 'button',
                        'data-initial': String(tabindexPgn === '0'),
                    },
                },
                _('FEN & PGN'),
            ),
        );
    }

    return [
        h('div.analysis-tabs', { attrs: { role: 'tablist', 'aria-label': _('Analysis') } }, tabs),
        h(
            'div.chart-container',
            { attrs: { id: 'panel-1', role: 'tabpanel', tabindex: '-1', 'aria-labelledby': 'tab-1' } },
            [h('div#request-analysis'), h('div#chart-analysis'), h('div#loader-wrapper', [spinner()])],
        ),
        h(
            'div.chart-container',
            { attrs: { id: 'panel-2', role: 'tabpanel', tabindex: '-1', 'aria-labelledby': 'tab-2' } },
            [h('div#chart-movetime')],
        ),
        h('div.ctable-container', {
            attrs: { id: 'panel-3', role: 'tabpanel', tabindex: tabindexCt, 'aria-labelledby': 'tab-3' },
        }),
        h(
            'div.pgn-container',
            { attrs: { id: 'panel-4', role: 'tabpanel', tabindex: tabindexPgn, 'aria-labelledby': 'tab-4' } },
            [
                h('div#fentext', [
                    h('strong', 'FEN'),
                    h('input#fullfen', {
                        attrs: { readonly: true, spellcheck: false },
                        on: { click: onClickFullfen },
                    }),
                ]),
                h('div.pgn-toolbar', [
                    h('div#copyfen'),
                    addToStudy && !isOngoingGame && model.anon !== 'True'
                        ? h(
                              'button.i-pgn.analysis-add-to-study',
                              {
                                  attrs: { type: 'button', title: _('Add to Study') },
                                  on: { click: addToStudy },
                              },
                              [h('i.icon.icon-plus-square', { attrs: { 'aria-hidden': 'true' } }), _('Add to Study')],
                          )
                        : '',
                ]),
                h('div#pgntext'),
            ],
        ),
    ];
}

function studyTagsFromAnalysis(model: PyChessModel, ctrl: AnalysisController): Record<string, string> {
    if (!model.gameId || ctrl.pgn) return extractPgnTags(ctrl.isAnalysisBoard ? ctrl.getPgn() : ctrl.pgn);

    const date = model.date ? model.date.slice(0, 10).replace(/-/g, '.') : '';
    const tags: Record<string, string> = {
        Event: `PyChess ${model.rated === '1' ? 'rated' : 'casual'} game`,
        Site: `${model.home}/${model.gameId}`,
        White: model.wplayer || '?',
        Black: model.bplayer || '?',
        Result: model.result || '*',
        WhiteElo: model.wrating || '?',
        BlackElo: model.brating || '?',
    };
    if (model.wtitle) tags.WhiteTitle = model.wtitle;
    if (model.btitle) tags.BlackTitle = model.btitle;
    if (date) tags.Date = date;
    return tags;
}

export function analysisView(model: PyChessModel): VNode[] {
    const context = analysisContext(model);
    const isOngoingGame = model.status == -1;
    let ctrl: AnalysisController | undefined;
    renderTimeago();

    const addToStudy = async () => {
        const tree = ctrl?.analysisTree;
        if (!ctrl || !tree) return;
        try {
            const defaultChapterName =
                model.gameId && model.wplayer && model.bplayer ? `${model.wplayer} - ${model.bplayer}` : _('Analysis');
            const destination = await chooseStudy(defaultChapterName);
            if (!destination) return;
            const tags = studyTagsFromAnalysis(model, ctrl);
            const response = await fetch('/study/from-analysis', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    variant: model.variant || 'chess',
                    chess960: model.chess960 === 'True',
                    initialFen: tree.root.step.fen,
                    gameId: model.gameId || undefined,
                    studyId: destination.studyId,
                    studyName: destination.studyName,
                    chapterName: destination.chapterName,
                    orientation: ctrl.chessground.state.orientation,
                    tags,
                    tree: studyTreeFromAnalysisTree(tree),
                }),
            });
            const payload = (await response.json()) as { ok?: boolean; url?: string; error?: string };
            if (!response.ok || !payload.ok || !payload.url) {
                window.alert(payload.error || _('Could not add analysis to Study.'));
                return;
            }
            window.location.assign(payload.url);
        } catch {
            window.alert(_('Could not add analysis to Study.'));
        }
    };

    return renderAnalysisPage(model, {
        side: analysisSide(model, context),
        underboard: analysisUnderboard(model, context, isOngoingGame, addToStudy),
        mountBoard: vnode => runGround(vnode, model, mounted => (ctrl = mounted)),
        ongoing: isOngoingGame,
    });
}
