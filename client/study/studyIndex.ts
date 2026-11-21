import ffishAliceModule from 'ffish-alice-es6';
import ffishModule from 'ffish-es6';

import { patch } from '../document';
import { studyChapterCreateForm, studyEnabledModesFromJson } from './studyChapterForm';
import { studyFlairPicker } from './studyFlair';
import {
    parseStudyPgnDocumentForImportWithEngines,
    postNewStudyPgnImport,
    studyPgnGameUsesAlice,
    type StudyPgnEngine,
    type StudyPgnImportProgressCallback,
    type StudyPgnImportResponse,
    type StudyPgnNewStudySettings,
} from './studyPgnImport';
import { pgnParser as studyPgnParser } from '../pgnParser';

const STUDY_SETTING_FIELDS = ['name', 'flair', 'visibility', 'computer', 'explorer', 'cloneable', 'shareable'] as const;
const studyPgnModules = new Map<boolean, Promise<StudyPgnEngine>>();

type StudyIndexPgnImport = (
    pgn: string,
    settings: StudyPgnNewStudySettings,
    onProgress?: StudyPgnImportProgressCallback,
) => Promise<StudyPgnImportResponse>;

export interface StudyIndexOptions {
    pgnImport?: StudyIndexPgnImport;
    navigate?: (url: string) => void;
}

function focusAndSelect(input: HTMLInputElement | null): void {
    input?.focus();
    input?.select();
}

function studySettings(form: HTMLFormElement): StudyPgnNewStudySettings {
    const data = new FormData(form);
    const value = (name: (typeof STUDY_SETTING_FIELDS)[number]): string => {
        const raw = data.get(name);
        return typeof raw === 'string' ? raw : '';
    };
    const nameInput = form.querySelector<HTMLInputElement>('input[name="name"]');
    const name = value('name');
    const flair = value('flair');
    return {
        // Leave the generated default empty for PGN imports so an exported
        // StudyName can restore the original study title. An explicitly edited
        // name always wins, and the server supplies the normal default when the
        // PGN has no StudyName metadata.
        name: nameInput && name === nameInput.defaultValue ? '' : name,
        ...(flair ? { flair } : {}),
        visibility: value('visibility'),
        computer: value('computer'),
        explorer: value('explorer'),
        cloneable: value('cloneable'),
        shareable: value('shareable'),
    };
}

function loadStudyPgnModule(alice: boolean): Promise<StudyPgnEngine> {
    const cached = studyPgnModules.get(alice);
    if (cached) return cached;

    const script = document.querySelector<HTMLScriptElement>('script[src*="/static/pychess-variants.js"]');
    const version = script ? new URL(script.src, window.location.href).search : '';
    const factory = alice ? ffishAliceModule : ffishModule;
    const loading = factory({
        locateFile: (path: string, prefix: string) =>
            path.endsWith('.wasm') ? `/static/${path}${version}` : prefix + path,
    })
        .then(module => module as StudyPgnEngine)
        .catch((error: unknown) => {
            studyPgnModules.delete(alice);
            throw error;
        });
    studyPgnModules.set(alice, loading);
    return loading;
}

async function importNewStudyPgn(
    pgn: string,
    settings: StudyPgnNewStudySettings,
    onProgress?: StudyPgnImportProgressCallback,
): Promise<StudyPgnImportResponse> {
    const imported = await parseStudyPgnDocumentForImportWithEngines(
        studyPgnParser,
        game => loadStudyPgnModule(studyPgnGameUsesAlice(game)),
        pgn,
        onProgress,
    );
    onProgress?.({ phase: 'saving', completed: 0, total: 1 });
    const result = await postNewStudyPgnImport(
        settings.name || !imported.studyName ? settings : { ...settings, name: imported.studyName },
        imported.chapters,
    );
    onProgress?.({ phase: 'saving', completed: 1, total: 1 });
    return result;
}

export function initStudyIndex(options: StudyIndexOptions = {}): void {
    const dialog = document.querySelector<HTMLDialogElement>('#study-new-dialog');
    const chapterDialog = document.querySelector<HTMLDialogElement>('#study-first-chapter-dialog');
    const chapterFormMount = document.querySelector<HTMLElement>('#study-first-chapter-form-mount');
    const openButton = document.querySelector<HTMLButtonElement>('[data-study-new-open]');
    const settingsForm = document.querySelector<HTMLFormElement>('#study-create-form');
    const enabledModes = studyEnabledModesFromJson(document.body.getAttribute('data-study-enabled-modes'));
    if (!dialog || !chapterDialog || !chapterFormMount || !openButton || !settingsForm) return;

    const flairMount = settingsForm.querySelector('#study-flair-mount');
    if (flairMount) patch(flairMount, studyFlairPicker());

    const pgnImport = options.pgnImport ?? importNewStudyPgn;
    const navigate = options.navigate ?? ((url: string) => window.location.assign(url));
    const chapterForm = patch(
        chapterFormMount,
        studyChapterCreateForm('/study', 'chess', {
            id: 'study-first-chapter-form',
            chapterName: 'Chapter 1',
            enabledModes,
            pgnImport: async (pgn, onProgress) => {
                const result = await pgnImport(pgn, studySettings(settingsForm), onProgress);
                if (!result.url) throw new Error('Study PGN import did not return a destination.');
                navigate(result.url);
            },
        }),
    ).elm as HTMLFormElement;
    const nameInput = dialog.querySelector<HTMLInputElement>('input[name="name"]');
    const chapterNameInput = chapterForm.querySelector<HTMLInputElement>('input[name="chapterName"]');

    const closeDialog = (modal: HTMLDialogElement): void => {
        if (modal.open) modal.close();
    };

    const copyStudySettings = (): void => {
        chapterForm.querySelectorAll<HTMLInputElement>('input[data-study-setting]').forEach(input => input.remove());
        const formData = new FormData(settingsForm);
        for (const field of STUDY_SETTING_FIELDS) {
            const value = formData.get(field);
            if (typeof value !== 'string') continue;
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = field;
            input.value = value;
            input.dataset.studySetting = '';
            chapterForm.append(input);
        }
    };

    openButton.addEventListener('click', () => {
        if (!dialog.open) dialog.showModal();
        focusAndSelect(nameInput);
    });

    settingsForm.addEventListener('submit', event => {
        event.preventDefault();
        if (!settingsForm.reportValidity()) return;
        copyStudySettings();
        closeDialog(dialog);
        if (!chapterDialog.open) chapterDialog.showModal();
        focusAndSelect(chapterNameInput);
    });

    dialog.querySelectorAll<HTMLButtonElement>('[data-study-new-close]').forEach(button => {
        button.addEventListener('click', () => closeDialog(dialog));
    });
    chapterDialog.querySelectorAll<HTMLButtonElement>('[data-study-first-chapter-close]').forEach(button => {
        button.addEventListener('click', () => closeDialog(chapterDialog));
    });

    for (const modal of [dialog, chapterDialog]) {
        modal.addEventListener('click', event => {
            if (event.target === modal) closeDialog(modal);
        });
        modal.addEventListener('close', () => openButton.focus());
    }
}
