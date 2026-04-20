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

# Copy runtime files
COPY --chown=${APP_USER}:${APP_USER} docker/main.py .
COPY --chown=${APP_USER}:${APP_USER} docker/entrypoint.sh .
COPY --chown=${APP_USER}:${APP_USER} docker/test-network.sh docker/
COPY --chown=${APP_USER}:${APP_USER} config ./config/

# Create public directory for frontend assets
RUN mkdir -p public && \
    chown ${APP_USER}:${APP_USER} public && \
    chmod 755 public

# Download and install frontend assets during build
# This eliminates runtime download complexity and works with ReadOnly containers
ARG FRONTEND_VERSION=staging
RUN set -ex; \
    if [ -n "${FRONTEND_VERSION}" ]; then \
        echo "Downloading frontend version: ${FRONTEND_VERSION}"; \
        wget -O /tmp/frontend.tar.gz \
            "https://github.com/humlab-swedeb/swedeb_frontend/releases/download/${FRONTEND_VERSION}/frontend-${FRONTEND_VERSION}.tar.gz"; \
        tar -xzf /tmp/frontend.tar.gz -C /app/public; \
        rm /tmp/frontend.tar.gz; \
        echo "${FRONTEND_VERSION}" > /app/public/.frontend_version; \
        echo "Frontend assets installed: $(ls -1 /app/public | wc -l) files"; \
    else \
        echo "FRONTEND_VERSION not set, skipping frontend download"; \
    fi

# Set permissions
RUN set -ex; \
    chown -R ${APP_USER}:${APP_USER} /data; \
    chown -R ${APP_USER}:${APP_USER} /app/public; \
    chmod +x entrypoint.sh; \
    chmod +x docker/test-network.sh

USER ${APP_USER}

ENV SHELL=/bin/bash
ENV HOME=/app

ARG CORPUS_REGISTRY=/data/registry
ENV CORPUS_REGISTRY=${CORPUS_REGISTRY}

ARG SWEDEB_PORT=8092
ENV SWEDEB_PORT=${SWEDEB_PORT}

ARG CONFIG_FILE=config/config.yml
ENV CONFIG_FILE=${CONFIG_FILE}

# Frontend version is baked into image at build time
# No runtime environment variable needed - assets are already present

ENTRYPOINT ["./entrypoint.sh"]