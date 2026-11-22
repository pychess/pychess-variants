import Highcharts from 'highcharts';

import { h, VNode } from 'snabbdom';

import { pageHeading } from './accessibility/headings';

function createPeriods() {
    const periodList: string[] = [];
    const date = new Date(2019, 6, 1, 0, 0, 0); // (2019-07-01) the month is 0-indexed
    const endDate = new Date();
    const months = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'];

    while (date <= endDate) {
        const year = date.getFullYear().toString();
        const month = months[date.getMonth()];
        periodList.push(year + '-' + month);
        date.setMonth(date.getMonth() + 1);
    }
    return periodList;
}

function buildChart() {
    const axisTypeEl = document.getElementById('linear') as HTMLInputElement;
    const humanGamesEl = document.getElementById('humans') as HTMLInputElement;

    const xmlhttp = new XMLHttpRequest();
    const url = humanGamesEl.checked ? '/api/stats/humans' : '/api/stats';

    xmlhttp.onreadystatechange = function () {
        if (this.readyState === 4 && this.status === 200) {
            const response = JSON.parse(this.responseText);

            if (!response.length) {
                return;
            }
            Highcharts.chart('stats-chart', {
                chart: { type: 'line' },
                credits: { enabled: false },
                title: { text: undefined },
                legend: {
                    layout: 'vertical',
                    align: 'right',
                    verticalAlign: 'top',
                },
                xAxis: {
                    categories: createPeriods(),
                },
                yAxis: {
                    type: axisTypeEl.checked ? 'linear' : 'logarithmic',
                },
                responsive: {
                    rules: [
                        {
                            condition: {
                                maxWidth: 1200,
                            },
                            chartOptions: {
                                legend: {
                                    align: 'center',
                                    verticalAlign: 'bottom',
                                    layout: 'horizontal',
                                },
                            },
                        },
                    ],
                },
                series: response,
            });
        }
    };
    xmlhttp.open('GET', url, true);
    xmlhttp.send();
}

export function statsView(): VNode[] {
    return [
        pageHeading(),
        h('div#stats-chart', { hook: { insert: () => buildChart() } }),
        h('input#linear', { props: { type: 'checkbox' }, on: { change: () => buildChart() } }),
        h('label', { attrs: { for: 'linear' } }, 'Linear scale'),
        h('input#humans', { props: { type: 'checkbox' }, on: { change: () => buildChart() } }),
        h('label', { attrs: { for: 'humans' } }, 'Human games'),
    ];
}
