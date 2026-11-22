const { readdir, readFile, realpathSync, stat, writeFile } = require('fs');
const { createMarkdownRenderer } = require('./markdown');

const converter = createMarkdownRenderer({ headingIds: true });

const basePath = realpathSync('./');
console.log('--- md2html.js ---', basePath);

function md2Html(inFile, outFile) {
    if (!inFile.endsWith('.md')) return;
    readFile(inFile, 'utf8', (fsReadError, fileContent) => {
        if (!fsReadError) {
            console.log(inFile);
            const htmlContent = converter.render(fileContent);
            writeFile(outFile, htmlContent, err => err && console.error(err));
        } else {
            return console.error(inFile, fsReadError);
        }
    });
}

readdir(basePath, 'utf8', (fsDirError, fileNameList) => {
    if (!fsDirError) {
        fileNameList.forEach(file => {
            const fileName = `${basePath}/${file}`;
            stat(fileName, (err, stats) => {
                if (stats.isDirectory()) {
                    readdir(fileName, 'utf8', (fsDirError, subFileNameList) => {
                        if (!fsDirError) {
                            subFileNameList.forEach(subFile => {
                                const subFileName = `${fileName}/${subFile}`;
                                const outFile = `${basePath}/${subFile.replace('.md', '')}.${file}.html`;
                                md2Html(subFileName, outFile);
                            });
                        } else {
                            return console.error(fsDirError);
                        }
                    });
                } else {
                    md2Html(fileName, fileName.replace('.md', '.html'));
                }
            });
        });
    } else {
        return console.error(fsDirError);
    }
});
