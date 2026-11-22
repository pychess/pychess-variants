import { afterEach, expect, jest, test } from '@jest/globals';

import { boardSettings } from '../client/boardSettings';
import { ChessgroundController } from '../client/cgCtrl';
import type { PyChessModel } from '../client/types';
import { registerCataloguedVariant, unregisterCataloguedVariant, VARIANTS } from '../client/variants';

const name = 'testlateboardcss';
const originalResizeObserver = window.ResizeObserver;
let controller: ChessgroundController | undefined;

afterEach(() => {
    controller?.destroy();
    controller = undefined;
    unregisterCataloguedVariant(name);
    document.getElementById(`board-set-catalogued-${name}`)?.remove();
    delete boardSettings.settings[`${name}-board`];
    delete boardSettings.settings[`${name}-piece`];
    document.body.textContent = '';
    jest.restoreAllMocks();
    jest.useRealTimers();
    if (originalResizeObserver) window.ResizeObserver = originalResizeObserver;
    else Reflect.deleteProperty(window, 'ResizeObserver');
});

test('a main board remeasures after custom aspect-ratio CSS loads and releases its resize listener', () => {
    jest.useFakeTimers();
    // Modern browsers observe the content box, which does not change when only
    // the wrapper's aspect-ratio padding changes.
    Object.defineProperty(window, 'ResizeObserver', {
        configurable: true,
        writable: true,
        value: class {
            observe() {}
            disconnect() {}
        },
    });
    registerCataloguedVariant({
        name,
        displayName: 'Late board CSS',
        ini: `[${name}:shogi]\nmaxFile = 10\nmaxRank = 10`,
        baseVariant: 'shogi',
        width: 10,
        height: 10,
        startFen: '9k/10/10/10/10/10/10/10/10/K9[] w - - 0 1',
        pieces: ['k'],
        kingRoles: ['k'],
        hasBoard: true,
    });
    const variant = VARIANTS[name];
    document.body.innerHTML = `<div data-board-variant="${name}" class="${variant.boardFamily}"><div class="cg-wrap ${variant.board.cg}"></div></div>`;
    const wrap = document.querySelector('.cg-wrap') as HTMLElement;
    let height = 600;
    jest.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
        const container = this.closest('cg-container') as HTMLElement | null;
        return {
            x: 0,
            y: 0,
            top: 0,
            left: 0,
            right: 600,
            width: 600,
            height: container ? parseFloat(container.style.height) : height,
            bottom: height,
            toJSON: () => ({}),
        };
    });
    class Controller extends ChessgroundController {}
    controller = new Controller(
        wrap,
        {
            variant: name,
            home: '',
            assetURL: '/static',
            anon: 'True',
            ffish: {
                Notation: { SAN: 0 },
                Board: class {
                    delete() {}
                },
            },
        } as unknown as PyChessModel,
        variant.startFen,
        document.createElement('div'),
        document.createElement('div'),
    );
    jest.advanceTimersByTime(32);
    const container = wrap.querySelector('cg-container') as HTMLElement;
    expect(container.style.height).toBe('600px');

    // Loading an uploaded Shogi board changes only padding; ResizeObserver's
    // content box stays 600x0, so the stylesheet's load signal must resize it.
    height = (600 * 12) / 11;
    document.getElementById(`board-set-catalogued-${name}`)!.dispatchEvent(new Event('load'));
    jest.advanceTimersByTime(64);
    expect(parseFloat(container.style.height)).toBeCloseTo(height);
    const king = wrap.querySelector('piece.white') as HTMLElement;
    expect(parseFloat(king.style.transform.split(',')[1])).toBeCloseTo(height * 0.9);

    const measure = jest.spyOn(wrap, 'getBoundingClientRect');
    document.body.dispatchEvent(new Event('chessground.resize'));
    controller.destroy();
    controller = undefined;
    measure.mockClear();
    jest.advanceTimersByTime(64);
    document.body.dispatchEvent(new Event('chessground.resize'));
    jest.advanceTimersByTime(64);
    expect(measure).not.toHaveBeenCalled();
});
