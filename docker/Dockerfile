ARG FRONTEND_VERSION=latest

FROM ghcr.io/humlab-swedeb/swedeb_frontend:${FRONTEND_VERSION} AS frontend-dist
FROM ghcr.io/humlab/cwb-container:latest AS final

LABEL maintainer="Roger Mähler <roger dot mahler at umu dot se>"

ENV APP_USER=cwbuser
ENV APP_UID=1021
ENV APP_GID=1021
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

USER root

RUN mkdir -p /app /data/cwb/data /data/corpus/tagged_frames /data/corpus/dtm /data/corpus/metadata

WORKDIR /app

COPY --chown=${APP_USER}:${APP_USER} main.py .
COPY --chown=${APP_USER}:${APP_USER} entrypoint.sh .
COPY --chown=${APP_USER}:${APP_USER} config ./config/
COPY --chown=${APP_USER}:${APP_USER} --from=frontend-dist /app/public ./public

RUN set -ex; \
    chown -R ${APP_USER}:${APP_USER} /data; \
    chmod +x entrypoint.sh; \
    rm -rf /dist /wheels

USER ${APP_USER}

ENV SHELL=/bin/bash
ENV HOME=/app
ENV CORPUS_REGISTRY=/data/registry
ENV SWEDEB_PORT=${SWEDEB_PORT:-8092}

ENTRYPOINT ["./entrypoint.sh"]