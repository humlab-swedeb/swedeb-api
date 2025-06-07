
FROM ghcr.io/humlab-swedeb/swedeb_frontend:latest AS frontend-dist

#####################################################################################
# Final stage (final)
#####################################################################################

FROM ghcr.io/humlab-swedeb/swedeb/cwb:3.5.0 as final

LABEL maintainer="Roger Mähler <roger dot mahler at umu dot se>"

ENV APP_USER=cwbuser
ENV APP_UID=1021
ENV APP_GID=1021

USER root

RUN mkdir -p /data/cwb/data /data/corpus/tagged_frames /data/corpus/dtm /data/corpus/metadata

WORKDIR /app

ARG SWEDEB_BACKEND_SOURCE="pypi"

# Copying entire context to /context (note that dist might be missing)
COPY . /context
COPY --from=frontend-dist /app/public ./public

RUN set -e && \
    if [ -d /context/dist ]; then \
        mv /context/dist /backend-wheels/ ; \
    fi && \
    mv /context/main.py /app/main.py && \
    mv /context/entrypoint.sh /app/entrypoint.sh && \
    mv /context/config /app/config && \
    pip3 install /wheels/*.whl; \
    if [ "${SWEDEB_BACKEND_SOURCE}" == "pypi" ]; then \
        pip3 install "api_swedeb==${SWEDEB_BACKEND_TAG}"; \
    elif [ "${SWEDEB_BACKEND_SOURCE}" == "whl" ]; then \
        pip3 install /backend-wheels/api_swedeb-"${SWEDEB_BACKEND_TAG}"-py3-none-any.whl && \
        rm -rf /backend-wheels; \
    fi && \
    chown -R ${APP_USER}:${APP_USER} /app /data && \
    chmod +x entrypoint.sh && \
    rm -rf /context /wheels /backend-wheels /tmp/*

USER ${APP_USER}

ENV SHELL=/bin/bash
ENV HOME=/app
ENV CORPUS_REGISTRY=/data/registry
ENV SWEDEB_PORT=${SWEDEB_PORT:-8092}

ENTRYPOINT ["./entrypoint.sh"]
