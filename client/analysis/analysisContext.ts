import type { PyChessModel } from '../types';

export type AnalysisMode = 'standalone' | 'game' | 'puzzle' | 'embed' | 'study';

export type AnalysisCapabilities = {
    resizableCharts: boolean;
    localAnalysisAllowed: boolean;
    editableTree: boolean;
    gamePanels: boolean;
    roundChat: boolean;
    engineTools: boolean;
    analysisTabs: boolean;
    usesRoundSocket: boolean;
    positionMetadata: boolean;
    evalCharts: boolean;
    positionEvaluation: boolean;
    serverAnalysisRequest: boolean;
    moveTimeChart: boolean;
};

export type AnalysisContext = {
    mode: AnalysisMode;
    analysisBoard: boolean;
    embed: boolean;
    puzzle: boolean;
    ongoing: boolean;
    capabilities: AnalysisCapabilities;
};

export function analysisContext(model: PyChessModel): AnalysisContext {
    const embed = model.embed;
    const puzzle = model.puzzle !== '';
    const study = model.study != null;
    const studyComputerAllowed = model.study?.features?.computer ?? true;
    const practiceLearner = model.study?.practice != null;
    const analysisBoard = model.gameId === '' && !puzzle;
    const ongoing = model.status <= -1;

    const mode: AnalysisMode = study
        ? 'study'
        : puzzle
          ? 'puzzle'
          : embed
            ? 'embed'
            : analysisBoard
              ? 'standalone'
              : 'game';

    return {
        mode,
        analysisBoard,
        embed,
        puzzle,
        ongoing,
        capabilities: {
            // These capability values intentionally mirror the legacy boolean gates in
            // AnalysisController. Phase 0B centralizes the answers without changing
            // behavior; later modes such as Study can extend this vocabulary cleanly.
            resizableCharts: !embed && !practiceLearner,
            localAnalysisAllowed: !ongoing && studyComputerAllowed,
            editableTree: !ongoing && !embed,
            gamePanels: !analysisBoard && !embed && !ongoing,
            roundChat: !analysisBoard && !embed && !puzzle && !ongoing,
            engineTools: !embed && !ongoing,
            analysisTabs: !puzzle && !ongoing && !embed && !practiceLearner,
            usesRoundSocket: !puzzle && !ongoing && model.gameId !== '',
            // Learn -> Practice deliberately omits the normal analysis FEN/PGN panel.
            // Keep ordinary Study metadata available while preventing the shared
            // AnalysisController from writing into DOM nodes that Practice does not render.
            positionMetadata: !puzzle && !ongoing && !practiceLearner,
            evalCharts: !puzzle && !ongoing && !practiceLearner,
            positionEvaluation: !ongoing,
            // Whether this page mode may ask the server for analysis. Variant/worker
            // support is intentionally decided server-side and is independent of WASM.
            serverAnalysisRequest: !analysisBoard && !embed,
            moveTimeChart: !embed && !practiceLearner,
        },
    };
}
