# Remove the frontend container dependency
FROM ghcr.io/humlab/cwb-container:latest AS final

LABEL maintainer="Roger Mähler <roger dot mahler at umu dot se>"

ENV APP_USER=cwbuser
ENV APP_UID=1021
ENV APP_GID=1021
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

USER root

RUN mkdir -p /app /app/config /data/cwb/data /data/corpus/tagged_frames /data/corpus/dtm /data/corpus/metadata

WORKDIR /app

# Install the application from pre-built wheel
COPY wheels/*.whl /tmp/
RUN set -ex; \
    pip install --no-cache-dir /tmp/*.whl; \
    rm -rf /tmp/*.whl

# Copy runtime files including frontend download script
COPY --chown=${APP_USER}:${APP_USER} main.py .
COPY --chown=${APP_USER}:${APP_USER} entrypoint.sh .
COPY --chown=${APP_USER}:${APP_USER} download-frontend.sh .
# COPY --chown=${APP_USER}:${APP_USER} config ./config/

# Create public directory for frontend assets (will be populated at runtime)
RUN mkdir -p public

# Set permissions
RUN set -ex; \
    chown -R ${APP_USER}:${APP_USER} /data public; \
    chmod +x entrypoint.sh download-frontend.sh

USER ${APP_USER}

ENV SHELL=/bin/bash
ENV HOME=/app

ARG CORPUS_REGISTRY=/data/registry
ENV CORPUS_REGISTRY=${CORPUS_REGISTRY}

ARG SWEDEB_PORT=8092
ENV SWEDEB_PORT=${SWEDEB_PORT}

ARG CONFIG_FILE=config/config.yml
ENV CONFIG_FILE=${CONFIG_FILE}

# Make frontend version available at runtime
ARG FRONTEND_VERSION=latest
ENV FRONTEND_VERSION=${FRONTEND_VERSION}

ENTRYPOINT ["./entrypoint.sh"]