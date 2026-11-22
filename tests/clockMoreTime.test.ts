import { afterEach, beforeEach, describe, expect, jest, test } from '@jest/globals';

import { Clock } from '../client/clock';

describe('giving extra time', () => {
    beforeEach(() => jest.useFakeTimers());
    afterEach(() => jest.useRealTimers());

    test('renders the remaining time without flashing the turn-start time', () => {
        const clock = new Clock(5, 0, 0, document.createElement('div'), 'clock0', false);
        const render = jest.spyOn(clock, 'renderTime');
        clock.onTick(clock.renderTime);
        clock.start();
        jest.advanceTimersByTime(5000);
        render.mockClear();

        clock.addTime(15000);

        expect(render).toHaveBeenLastCalledWith(310000);
        jest.advanceTimersByTime(500);
        expect(render).toHaveBeenLastCalledWith(309500);
        clock.pause(false);
        expect(clock.duration).toBe(309500);
    });

    test('accumulates gifts on a stopped clock without adding increment', () => {
        const clock = new Clock(5, 3, 0, document.createElement('div'), 'clock0', false);
        const render = jest.spyOn(clock, 'renderTime');
        clock.addTime(15000);
        clock.addTime(15000);

        expect(clock.duration).toBe(330000);
        expect(render).toHaveBeenLastCalledWith(330000);
        expect(clock.running).toBe(false);
    });
});
