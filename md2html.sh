#!/bin/sh

# Learn docs
cd static/docs
node ../../md2html.js

TAGNAME=$(git tag -l -n1 --sort=-v:refname --format='%(refname:short)' | head -n 1)
echo "${TAGNAME}"

SRC='https://github.com/pychess/pychess-variants/blob/master';
# DST='https://cdn.jsdelivr.net/gh/pychess/pychess-variants\@'$TAGNAME;
DST='https://cdn.jsdelivr.net/gh/pychess/pychess-variants\@1.11.73';
echo "${DST}"
find . -type f -name "*.html" -exec perl -pi -e s,$SRC,$DST,g '{}' +

mkdir -p ../../templates/docs
mv *.html ../../templates/docs
