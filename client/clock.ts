// https://stackoverflow.com/questions/20618355/the-simplest-possible-javascript-countdown-timer

import { h, VNode } from 'snabbdom';

import { sound } from './sound';
import { patch } from './document';

import { ngettext } from './i18n';

export type Minutes = number;
export type Seconds = number;
export type Millis = number;

const HURRY = 10000;

// Read as "05", ":", "23" with no owner; the board summary says the time in words instead.
const hiddenFromReaders = () => ({ attrs: { 'aria-hidden': 'true' } });

const prefixInteger = (num: number, length: number): string => (num / Math.pow(10, length)).toFixed(length).substr(2);

function formatClockTime(time: Millis) {
    const date = new Date(time),
        minutes = prefixInteger(date.getUTCMinutes(), 2),
        seconds = prefixInteger(date.getSeconds(), 2);
    let hours: number,
        str = '';
    if (time >= 86400 * 1000) {
        // days : hours
        const days = date.getUTCDate() - 1;
        hours = date.getUTCHours();
        str += ngettext('%1 day', '%1 days', days) + ' ';
        if (hours !== 0) str += ngettext('%1 hour', '%1 hours', hours);
    } else if (time >= 3600 * 1000) {
        // hours : minutes
        hours = date.getUTCHours();
        str += prefixInteger(hours, 2) + ':' + minutes;
    } else {
        // minutes : seconds
        str += minutes + ':' + seconds;
    }
    return str;
}

export class Clock {
    duration: Millis;
    increment: Millis;
    granularity: number;
    running: boolean;
    connecting: boolean;
    timeout: ReturnType<typeof setTimeout> | null;
    startTime: number;
    tickCallbacks: ((diff: number) => void)[];
    renderCallbacks: ((time: Millis) => void)[];
    flagCallback: (() => void) | null;
    byoyomiCallback: (() => void) | null;
    el: HTMLElement | VNode;
    id: string;
    overtime: boolean;
    byoyomi: boolean;
    initialByoyomiPeriod: number;
    byoyomiPeriod: number;
    hurry: boolean;
    ticks: boolean[];
    corr: boolean;

    // game baseTime (min) and increment (sec)
    constructor(
        baseTime: Minutes,
        increment: Seconds,
        byoyomiPeriod: number,
        el: HTMLElement | VNode,
        id: string,
        corr: boolean,
    ) {
        this.duration = baseTime * 1000 * 60;
        this.increment = increment * 1000;
        this.granularity = 500;
        this.running = false;
        this.connecting = false;
        this.timeout = null;
        this.startTime = 0;
        this.tickCallbacks = [];
        this.renderCallbacks = [];
        this.flagCallback = null;
        this.byoyomiCallback = null;
        this.el = el;
        this.id = id;
        this.overtime = false;
        this.byoyomi = byoyomiPeriod > 0;
        this.initialByoyomiPeriod = byoyomiPeriod;
        this.byoyomiPeriod = byoyomiPeriod;
        this.hurry = false;
        this.ticks = [false, false, false, false, false, false, false, false, false, false];
        this.corr = corr;
        if (this.corr) this.duration = this.duration * 24 * 60;

        this.renderTime(this.duration);
    }

    start(duration = 0) {
        if (this.running) return;
        if (duration !== 0) this.duration = duration;
        this.running = true;
        this.startTime = Date.now();

        const timer = () => {
            const diff = this.duration - (Date.now() - this.startTime);
            if (diff <= HURRY && !this.hurry && !this.byoyomi) {
                this.hurry = true;
                sound.lowTime();
            }

            if (this.byoyomi && this.byoyomiPeriod === 0) {
                for (let i = 0; i < 10; i++) {
                    if (diff <= 1000 * (i + 1) && !this.ticks[i]) {
                        this.ticks[i] = true;
                        sound.tick();
                        break;
                    }
                }
            }

            if (diff <= 0) {
                if (this.byoyomi && this.byoyomiPeriod > 0) {
                    sound.lowTime();
                    this.overtime = true;
                    this.byoyomiPeriod -= 1;
                    this.ticks = [false, false, false, false, false, false, false, false, false, false];
                    if (this.granularity === 100 && this.increment > HURRY) this.granularity = 500;
                    this.duration = this.increment;
                    this.startTime = Date.now();
                    if (this.byoyomiCallback !== null) this.byoyomiCallback();
                } else {
                    if (this.flagCallback !== null) this.flagCallback();
                    this.pause(false);
                    return;
                }
            }
            this.timeout = setTimeout(timer, this.granularity);
            this.tickCallbacks.forEach(function (callback) {
                callback.call(this, diff);
            }, this);
        };

        timer();
    }

    onTick(callback: (diff: number) => void) {
        if (typeof callback === 'function') {
            this.tickCallbacks.push(callback);
        }
        return this;
    }

    // Every repaint, ticking or not (pause, resync, flip), with the time shown.
    onRender(callback: (time: Millis) => void) {
        this.renderCallbacks.push(callback);
        return this;
    }

    onFlag(callback: () => void) {
        if (typeof callback === 'function') {
            this.pause(false);
            this.flagCallback = callback;
        }
        return this;
    }

    onByoyomi(callback: () => void) {
        if (typeof callback === 'function') {
            this.byoyomiCallback = callback;
        }
        return this;
    }

    pause(withIncrement: boolean) {
        if (!this.running) return;

        this.running = false;
        if (this.timeout) clearTimeout(this.timeout);
        this.timeout = null;

        this.duration = Math.max(0, this.duration - (Date.now() - this.startTime));
        if (withIncrement && this.increment) {
            if (this.byoyomi) {
                if (this.overtime) {
                    this.duration = this.increment;
                    this.ticks = [false, false, false, false, false, false, false, false, false, false];
                }
            } else {
                this.duration += this.increment;
                this.hurry = this.duration < HURRY;
            }
        }
        this.renderTime(this.duration);
    }

    setTime(millis: number) {
        this.duration = Math.max(0, millis);
        this.renderTime(this.duration);
    }

    syncByoyomiPeriod(period: number) {
        // Server period counts are authoritative after reconnects and takebacks.
        // Fewer periods than the initial allocation means main time has expired.
        this.byoyomiPeriod = period;
        this.overtime = period < this.initialByoyomiPeriod;
        this.ticks = [false, false, false, false, false, false, false, false, false, false];
    }

    printTime(millis: number) {
        let minutes = Math.floor(millis / 60000);
        let seconds = (millis % 60000) / 1000;
        let secs, mins;
        if (Math.floor(seconds) === 60) {
            minutes++;
            seconds = 0;
        }
        minutes = Math.max(0, minutes);
        seconds = Math.max(0, seconds);
        if (millis < HURRY && this.byoyomiPeriod === 0) secs = seconds.toFixed(1);
        else secs = Math.floor(seconds).toString();
        mins = (minutes < 10 ? '0' : '') + minutes;
        secs = (seconds < 10 && secs.length < 4 ? '0' : '') + secs;
        return {
            minutes: mins,
            seconds: secs,
        };
    }

    view(time: number) {
        if (this.corr) {
            return h('div#' + this.id, hiddenFromReaders(), [
                h(
                    'div.clock.corr-clock',
                    {
                        class: {
                            running: this.running,
                            hurry: time < HURRY && this.byoyomiPeriod === 0,
                            connecting: this.connecting,
                            overtime: this.overtime,
                        },
                    },
                    formatClockTime(time),
                ),
            ]);
        }

        const printed = this.printTime(time);
        const millis = new Date(time).getUTCMilliseconds();
        return h('div#' + this.id, hiddenFromReaders(), [
            h(
                'div.clock',
                {
                    class: {
                        running: this.running,
                        hurry: time < HURRY && this.byoyomiPeriod === 0,
                        connecting: this.connecting,
                        overtime: this.overtime,
                    },
                },
                [
                    h('div.clock-time.min', printed.minutes),
                    h('div.clock-sep', { class: { low: millis < 500 } }, ':'),
                    h('div.clock-time.sec', printed.seconds),
                    h(
                        'div.clock-time.byo',
                        { class: { byoyomi: this.byoyomiPeriod > 0 && this.increment > 0 } },
                        `+${this.increment / 1000}s` + (this.byoyomiPeriod > 1 ? ` (x${this.byoyomiPeriod})` : ''),
                    ),
                ],
            ),
        ]);
    }

    renderTime(time: number) {
        if (!isNaN(time)) {
            if (this.granularity > 100 && time < HURRY) this.granularity = 100;
            this.el = patch(this.el, this.view(time));
            this.renderCallbacks.forEach(callback => callback(time));
        }
    }
}
