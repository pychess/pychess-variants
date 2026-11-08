import { _, ngettext } from './i18n';

export function timeago(date: string) {
    const TZdate = new Date(date).getTime();
    const maxLength: { [key: string]: number } = {
        second: 60,
        minute: 60,
        hour: 24,
        day: 7,
        week: 4.35,
        month: 12,
        year: 10000,
    };
    let val, inTheFuture;
    if (Date.now() >= TZdate) {
        val = (Date.now() - TZdate) / 1000;
        inTheFuture = false;
    } else {
        val = (TZdate - Date.now()) / 1000;
        inTheFuture = true;
    }

    for (const unit in maxLength) {
        if (Math.floor(val / maxLength[unit]) === 0) {
            const result = Math.floor(val);
            switch (unit) {
                case 'year':
                    return inTheFuture
                        ? ngettext('in %1 year', 'in %1 years', result)
                        : ngettext('%1 year ago', '%1 years ago', result);
                case 'month':
                    return inTheFuture
                        ? ngettext('in %1 month', 'in %1 months', result)
                        : ngettext('%1 month ago', '%1 months ago', result);
                case 'week':
                    return inTheFuture
                        ? ngettext('in %1 week', 'in %1 weeks', result)
                        : ngettext('%1 week ago', '%1 weeks ago', result);
                case 'day':
                    return inTheFuture
                        ? ngettext('in %1 day', 'in %1 days', result)
                        : ngettext('%1 day ago', '%1 days ago', result);
                case 'hour':
                    return inTheFuture
                        ? ngettext('in %1 hour', 'in %1 hours', result)
                        : ngettext('%1 hour ago', '%1 hours ago', result);
                case 'minute':
                    return inTheFuture
                        ? ngettext('in %1 minute', 'in %1 minutes', result)
                        : ngettext('%1 minute ago', '%1 minutes ago', result);
                case 'second':
                    return inTheFuture
                        ? ngettext('in %1 second', 'in %1 seconds', result)
                        : ngettext('%1 second ago', '%1 seconds ago', result);
            }
        }
        val = val / maxLength[unit];
    }
    return '';
}

export function updateTimeago() {
    const els = document.getElementsByTagName('info-date');
    Array.from(els).forEach(el => {
        el.textContent = timeago(el.getAttribute('timestamp') ?? 'unknown when');
    });
}

export function renderTimeago() {
    updateTimeago();
    setTimeout(renderTimeago, 1200);
}
