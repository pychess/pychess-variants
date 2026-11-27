FROM node:24 AS frontend

WORKDIR /app

COPY package.json /app/
COPY cp2static.sh md2html.sh md2html.js esbuild.mjs tsconfig.json yarn.lock markdown.js markdown.d.ts /app/

RUN yarn install --ignore-scripts

COPY client /app/client/
COPY static /app/static/

RUN ./cp2static.sh
RUN yarn dev

COPY templates /app/templates/
RUN yarn md


FROM python:3.14

COPY README.md /app/
COPY pyproject.toml /app/

WORKDIR /app

RUN pip install .

COPY lang /app/lang/
COPY server /app/server/
COPY docs /app/docs/
COPY --from=frontend /app/client /app/client/
COPY --from=frontend /app/static /app/static/
COPY --from=frontend /app/templates /app/templates/
COPY variants.ini /app/

EXPOSE 8080

CMD ["python", "server/server.py", "-a"]
