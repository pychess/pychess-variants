import { beforeEach, describe, expect, jest, test } from '@jest/globals';
import { initStudyIndex } from '../client/study/studyIndex';

describe('Study index creation dialogs', () => {
    beforeEach(() => {
        document.body.removeAttribute('data-study-enabled-modes');
        document.body.innerHTML = `
            <button type="button" data-study-new-open>New study</button>
            <dialog id="study-new-dialog">
                <form id="study-create-form">
                    <div id="study-flair-mount"></div>
                    <input name="name" value="owner's Study">
                    <select name="visibility"><option value="private" selected>Private</option></select>
                    <select name="computer"><option value="everyone" selected>Everyone</option></select>
                    <input type="hidden" name="explorer" value="everyone">
                    <select name="cloneable"><option value="everyone" selected>Everyone</option></select>
                    <select name="shareable"><option value="everyone" selected>Everyone</option></select>
                    <button type="submit">Start</button>
                </form>
                <button type="button" data-study-new-close>Cancel</button>
            </dialog>
            <dialog id="study-first-chapter-dialog">
                <div id="study-first-chapter-form-mount"></div>
                <button type="button" data-study-first-chapter-close>Close</button>
            </dialog>
        `;
    });

    function mockDialog(dialog: HTMLDialogElement) {
        const showModal = jest.fn(() => dialog.setAttribute('open', ''));
        const close = jest.fn(() => {
            dialog.removeAttribute('open');
            dialog.dispatchEvent(new Event('close'));
        });
        dialog.showModal = showModal;
        dialog.close = close;
        return { showModal, close };
    }

    test('opens the Study settings dialog and closes it from its controls', () => {
        const dialog = document.querySelector<HTMLDialogElement>('#study-new-dialog')!;
        const chapterDialog = document.querySelector<HTMLDialogElement>('#study-first-chapter-dialog')!;
        const openButton = document.querySelector<HTMLButtonElement>('[data-study-new-open]')!;
        const nameInput = dialog.querySelector<HTMLInputElement>('input[name="name"]')!;
        const closeButton = dialog.querySelector<HTMLButtonElement>('[data-study-new-close]')!;
        const { showModal, close } = mockDialog(dialog);
        mockDialog(chapterDialog);

        initStudyIndex();
        openButton.click();

        expect(showModal).toHaveBeenCalledTimes(1);
        expect(document.activeElement).toBe(nameInput);

        closeButton.click();
        expect(close).toHaveBeenCalledTimes(1);
        expect(document.activeElement).toBe(openButton);
    });

    test('deployment mode bootstrap limits first-chapter entry options', () => {
        document.body.setAttribute('data-study-enabled-modes', '["normal","conceal"]');
        initStudyIndex();

        const mode = document.querySelector<HTMLSelectElement>('#study-first-chapter-form select[name="mode"]')!;
        expect([...mode.options].map(option => option.value)).toEqual(['normal', 'conceal']);
    });

    test('keeps the variant flair category selected when emoji finish loading', async () => {
        const originalFetch = globalThis.fetch;
        let finishFetch!: (response: Response) => void;
        const fetchResponse = new Promise<Response>(resolve => (finishFetch = resolve));
        globalThis.fetch = jest.fn(() => fetchResponse);
        try {
            initStudyIndex();
            const picker = document.querySelector<HTMLDetailsElement>('.study-flair-picker')!;
            picker.open = true;
            picker.dispatchEvent(new Event('toggle'));
            const category = picker.querySelector('select')!;
            category.value = 'variants';
            category.dispatchEvent(new Event('change'));
            finishFetch({
                ok: true,
                json: async () => ({ groups: { 'Smileys & Emotion': [['😀', 'grinning face']] } }),
            } as Response);
            await new Promise(resolve => setTimeout(resolve, 0));

            expect(category.value).toBe('variants');
            picker.querySelector<HTMLButtonElement>('button[aria-label="SHOGI"]')!.click();
            expect(document.querySelector<HTMLInputElement>('input[name="flair"]')?.value).toBe('variant:shogi');
            expect(picker.open).toBe(false);
        } finally {
            globalThis.fetch = originalFetch;
        }
    });

    test('Start opens the first-chapter dialog without submitting the Study settings form', () => {
        const dialog = document.querySelector<HTMLDialogElement>('#study-new-dialog')!;
        const chapterDialog = document.querySelector<HTMLDialogElement>('#study-first-chapter-dialog')!;
        const settingsForm = document.querySelector<HTMLFormElement>('#study-create-form')!;
        const { close } = mockDialog(dialog);
        const { showModal } = mockDialog(chapterDialog);
        const openButton = document.querySelector<HTMLButtonElement>('[data-study-new-open]')!;
        settingsForm.reportValidity = jest.fn(() => true);

        initStudyIndex();
        const chapterForm = document.querySelector<HTMLFormElement>('#study-first-chapter-form')!;
        settingsForm.querySelector<HTMLInputElement>('input[name="flair"]')!.value = 'variant:shogi';
        const chapterName = chapterDialog.querySelector<HTMLInputElement>('input[name="chapterName"]')!;
        openButton.click();
        settingsForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

        expect(close).toHaveBeenCalledTimes(1);
        expect(showModal).toHaveBeenCalledTimes(1);
        expect(document.activeElement).toBe(chapterName);
        expect(chapterName.value).toBe('Chapter 1');
        expect(chapterForm.querySelector<HTMLSelectElement>('select[name="variant"]')?.value).toBe('chess');
        expect(chapterForm.querySelector<HTMLSelectElement>('select[name="orientation"]')?.value).toBe('white');
        const mode = chapterForm.querySelector<HTMLSelectElement>('select[name="mode"]')!;
        expect(mode.value).toBe('normal');
        expect([...mode.options].map(option => option.value)).toEqual(['normal', 'practice', 'gamebook']);
        expect(chapterForm.querySelector<HTMLInputElement>('input[name="name"]')?.value).toBe("owner's Study");
        expect(chapterForm.querySelector<HTMLInputElement>('input[name="flair"]')?.value).toBe('variant:shogi');
        expect(chapterForm.querySelector<HTMLInputElement>('input[name="visibility"]')?.value).toBe('private');
        expect(chapterForm.querySelector<HTMLInputElement>('input[name="computer"]')?.value).toBe('everyone');
        expect(chapterForm.querySelector<HTMLInputElement>('input[name="cloneable"]')?.value).toBe('everyone');
        expect(chapterForm.querySelector<HTMLInputElement>('input[name="shareable"]')?.value).toBe('everyone');
        expect(chapterForm.querySelector('.study-dialog__actions--submit-only .button')?.textContent).toBe(
            'Create chapter',
        );
    });
    test('PGN can create the first chapter and the Study in one import', async () => {
        const dialog = document.querySelector<HTMLDialogElement>('#study-new-dialog')!;
        const chapterDialog = document.querySelector<HTMLDialogElement>('#study-first-chapter-dialog')!;
        mockDialog(dialog);
        mockDialog(chapterDialog);
        const pgnImport = jest.fn(async () => ({
            ok: true,
            imported: 2,
            studyId: 'Study001',
            chapterId: 'Chap0002',
            url: '/study/Study001/Chap0002',
        }));
        const navigate = jest.fn();

        initStudyIndex({ pgnImport, navigate });
        const settingsForm = document.querySelector<HTMLFormElement>('#study-create-form')!;
        settingsForm.reportValidity = jest.fn(() => true);
        settingsForm.querySelector<HTMLInputElement>('input[name="name"]')!.value = 'Imported Study';
        settingsForm.querySelector<HTMLInputElement>('input[name="flair"]')!.value = 'emoji:👽';
        settingsForm.querySelector<HTMLSelectElement>('select[name="visibility"]')!.innerHTML =
            '<option value="unlisted" selected>Unlisted</option>';
        settingsForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

        const chapterForm = document.querySelector<HTMLFormElement>('#study-first-chapter-form')!;
        chapterForm.reportValidity = jest.fn(() => true);
        chapterForm.querySelector<HTMLButtonElement>('[data-study-chapter-source="pgn"]')!.click();
        const pgn = '[Event "One"]\n\n1. e4 e5 *\n\n[Event "Two"]\n\n1. d4 d5 *';
        chapterForm.querySelector<HTMLTextAreaElement>('textarea[name="pgn"]')!.value = pgn;
        chapterForm.dispatchEvent(new SubmitEvent('submit', { bubbles: true, cancelable: true }));
        await new Promise(resolve => setTimeout(resolve, 0));

        expect(pgnImport).toHaveBeenCalledWith(
            pgn,
            {
                name: 'Imported Study',
                flair: 'emoji:👽',
                visibility: 'unlisted',
                computer: 'everyone',
                explorer: 'everyone',
                cloneable: 'everyone',
                shareable: 'everyone',
            },
            expect.any(Function),
        );
        expect(navigate).toHaveBeenCalledWith('/study/Study001/Chap0002');
    });

    test('PGN import leaves the generated default Study name available for StudyName metadata', async () => {
        const dialog = document.querySelector<HTMLDialogElement>('#study-new-dialog')!;
        const chapterDialog = document.querySelector<HTMLDialogElement>('#study-first-chapter-dialog')!;
        mockDialog(dialog);
        mockDialog(chapterDialog);
        const pgnImport = jest.fn(async () => ({
            ok: true,
            imported: 1,
            studyId: 'Study001',
            chapterId: 'Chap0001',
            url: '/study/Study001/Chap0001',
        }));

        initStudyIndex({ pgnImport, navigate: jest.fn() });
        const settingsForm = document.querySelector<HTMLFormElement>('#study-create-form')!;
        settingsForm.reportValidity = jest.fn(() => true);
        settingsForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));

        const chapterForm = document.querySelector<HTMLFormElement>('#study-first-chapter-form')!;
        chapterForm.reportValidity = jest.fn(() => true);
        chapterForm.querySelector<HTMLButtonElement>('[data-study-chapter-source="pgn"]')!.click();
        const pgn = '[StudyName "Original Study"]\n[ChapterName "Intro"]\n\n*';
        chapterForm.querySelector<HTMLTextAreaElement>('textarea[name="pgn"]')!.value = pgn;
        chapterForm.dispatchEvent(new SubmitEvent('submit', { bubbles: true, cancelable: true }));
        await new Promise(resolve => setTimeout(resolve, 0));

        expect(pgnImport).toHaveBeenCalledWith(
            pgn,
            {
                name: '',
                visibility: 'private',
                computer: 'everyone',
                explorer: 'everyone',
                cloneable: 'everyone',
                shareable: 'everyone',
            },
            expect.any(Function),
        );
    });

});
