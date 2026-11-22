import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

test('documentation table headers with quotes cannot inject attributes', () => {
    const fixtureDir = mkdtempSync(join(tmpdir(), 'pychess-md2html-'));
    try {
        writeFileSync(
            join(fixtureDir, 'table.md'),
            '| Name"/data-injected="yes | Col2 |\n| --- | --- |\n| Safe | Content |',
        );
        execFileSync(process.execPath, [resolve('md2html.js')], { cwd: fixtureDir });

        const root = document.createElement('div');
        root.innerHTML = readFileSync(join(fixtureDir, 'table.html'), 'utf8');
        expect(Array.from(root.querySelectorAll('th'), cell => cell.textContent)).toEqual([
            'Name"/data-injected="yes',
            'Col2',
        ]);
        expect(Array.from(root.querySelectorAll('td'), cell => cell.textContent)).toEqual(['Safe', 'Content']);
        expect(root.querySelector('th[id], [data-injected]')).toBeNull();
        expect(root.querySelector('th')?.attributes).toHaveLength(0);
    } finally {
        rmSync(fixtureDir, { recursive: true, force: true });
    }
});
