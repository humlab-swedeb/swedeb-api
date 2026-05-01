# Dockerfile.standalone
#
# Self-contained image: builds CWB from source, clones both backend and frontend
# from GitHub, and assembles the final runtime — no external base image or
# pre-built wheel required.  Branch/tag for each repo is independently
# configurable via build args.
#
# Build:
#   docker build -f docker/Dockerfile.standalone \
#     [--build-arg BACKEND_REPO=...] \
#     [--build-arg FRONTEND_REPO=...] \
#     -t swedeb-api:standalone .
#
# Optional build args:
#   PYTHON_VERSION – Python version (default: 3.13)
#   CWB_VERSION    – CWB source version to compile (default: 3.5.0)
#   BACKEND_REPO    – full clone URL (default: https://github.com/humlab-swedeb/swedeb-api.git)
#   FRONTEND_REPO   – full clone URL (default: https://github.com/humlab-swedeb/swedeb_frontend.git)
#   BACKEND_BRANCH  – branch or tag for the backend repo (default: staging)
#   FRONTEND_BRANCH – branch or tag for the frontend repo (default: staging)
#   SWEDEB_PORT    – port the API listens on (default: 8092)
#   CORPUS_REGISTRY
#   CONFIG_FILE

ARG PYTHON_VERSION="3.13"
ARG CWB_VERSION="3.5.0"

# ---------------------------------------------------------------------------
# Stage 1: build CWB from source and create Python wheels
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS cwb-builder

ARG CWB_VERSION

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_PROGRESS_BAR=off
ENV PIP_ROOT_USER_ACTION=ignore

RUN set -e; \
    apt_log=/tmp/apt-step.log; \
    { \
      apt-get update -qq; \
      apt-get install -y -qq --no-install-recommends \
        build-essential apt-utils pkg-config autoconf bison flex subversion tar wget \
        libpcre3-dev libglib2.0-dev libncurses-dev libncurses5-dev \
        libreadline-dev libc6-dev; \
    } >"$apt_log" 2>&1 || { cat "$apt_log"; exit 1; }; \
    rm -f "$apt_log"; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /src

RUN set -e && \
    quiet() { "$@" >/tmp/build-step.log 2>&1 || { cat /tmp/build-step.log; exit 1; }; rm -f /tmp/build-step.log; } && \
    CWB_SERIES="${CWB_VERSION%.*}" && \
    wget -q -O cwb-${CWB_VERSION}-src.tar.gz https://sourceforge.net/projects/cwb/files/cwb/cwb-${CWB_SERIES}/source/cwb-${CWB_VERSION}-src.tar.gz/download \
    && tar -xzf cwb-${CWB_VERSION}-src.tar.gz \
    && rm cwb-${CWB_VERSION}-src.tar.gz \
    && cd /src/cwb-${CWB_VERSION}-src \
    && touch local_config.mk && echo "export PLATFORM=linux-native" >> local_config.mk \
    && quiet ./install-scripts/install-linux \
    \
    && svn co --trust-server-cert --non-interactive --quiet https://svn.code.sf.net/p/cwb/code/perl/trunk cwb-perl \
    && cd cwb-perl/CWB \
    && quiet perl Makefile.PL --config=/usr/local/bin/cwb-config \
    && quiet make -s \
    && quiet make -s test \
    && quiet make -s install

WORKDIR /wheels

RUN pip install -q --upgrade pip \
    && pip install -q setuptools wheel \
    \
    && pip wheel -q --no-deps --wheel-dir /wheels "association-measures" \
    && pip wheel -q --no-deps --wheel-dir /wheels cwb-ccc

# ---------------------------------------------------------------------------
# Stage 2: build the backend Python wheel
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS backend-builder

ARG BACKEND_REPO=https://github.com/humlab-swedeb/swedeb-api.git
ARG BACKEND_BRANCH=staging

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_PROGRESS_BAR=off
ENV PIP_ROOT_USER_ACTION=ignore

RUN set -e; \
    apt_log=/tmp/apt-step.log; \
    { \
      apt-get update -qq; \
      apt-get install -qq -y --no-install-recommends ca-certificates git; \
      update-ca-certificates; \
    } >"$apt_log" 2>&1 || { cat "$apt_log"; exit 1; }; \
    rm -f "$apt_log"; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build/backend

RUN git clone --quiet --depth 1 --branch "${BACKEND_BRANCH}" "${BACKEND_REPO}" .

# Install uv and build the wheel
RUN pip install -q uv \
    && uv build --quiet --no-build-logs --wheel --out-dir /dist/wheels

# ---------------------------------------------------------------------------
# Stage 3: build the frontend SPA tarball
# ---------------------------------------------------------------------------
FROM node:22-slim AS frontend-builder

ARG FRONTEND_REPO=https://github.com/humlab-swedeb/swedeb_frontend.git
ARG FRONTEND_BRANCH=staging

RUN set -e; \
    apt_log=/tmp/apt-step.log; \
    { \
      apt-get update -qq; \
      apt-get install -qq -y --no-install-recommends ca-certificates git; \
      update-ca-certificates; \
    } >"$apt_log" 2>&1 || { cat "$apt_log"; exit 1; }; \
    rm -f "$apt_log"; \
    rm -rf /var/lib/apt/lists/*

# Install pnpm
RUN npm install -g --silent pnpm

WORKDIR /build/frontend

RUN git clone --quiet --depth 1 --branch "${FRONTEND_BRANCH}" "${FRONTEND_REPO}" .

RUN pnpm --reporter=silent install --frozen-lockfile
RUN pnpm --reporter=silent build

# Pack the built SPA into a tarball
RUN mkdir -p /dist && tar -czf /dist/frontend.tar.gz -C dist/spa .

# ---------------------------------------------------------------------------
# Stage 4: final runtime image
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS final

LABEL maintainer="Roger Mähler <roger dot mahler at umu dot se>"

ARG APP_UID=1021
ARG APP_GID=1021
ARG BACKEND_BRANCH=staging
ARG FRONTEND_BRANCH=staging

RUN printf 'Build refs: BACKEND_BRANCH=%s FRONTEND_BRANCH=%s\n' "${BACKEND_BRANCH}" "${FRONTEND_BRANCH}"

ENV APP_USER=cwbuser
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LANG=C.UTF-8
ENV LD_LIBRARY_PATH=/usr/local/lib
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_PROGRESS_BAR=off
ENV PIP_ROOT_USER_ACTION=ignore

# Install CWB runtime dependencies
RUN set -e; \
    apt_log=/tmp/apt-step.log; \
    { \
      DEBIAN_FRONTEND=noninteractive apt-get update -qq; \
      DEBIAN_FRONTEND=noninteractive apt-get install -qq -y --no-install-recommends \
        libpcre3 libglib2.0-0 libncurses5 libreadline8 readline-common \
        git less gzip bzip2 curl wget; \
    } >"$apt_log" 2>&1 || { cat "$apt_log"; exit 1; }; \
    rm -f "$apt_log"; \
    rm -rf /var/lib/apt/lists/*

# Copy CWB binaries, libraries, and Python wheels from the cwb-builder stage
COPY --from=cwb-builder /usr/local/bin/ /usr/local/bin/
COPY --from=cwb-builder /usr/local/lib/ /usr/local/lib/
COPY --from=cwb-builder /usr/local/include/ /usr/local/include/
COPY --from=cwb-builder /wheels /wheels

RUN ldconfig && pip3 install -q /wheels/*.whl && rm -rf /wheels

# Create the runtime user
RUN addgroup --quiet --gid ${APP_GID} "${APP_USER}" && \
    adduser --quiet ${APP_USER} --home /app --uid ${APP_UID} --gid ${APP_GID} --disabled-password --gecos '' --shell /bin/bash && \
    mkdir -p /usr/local/share/cwb/ && \
    chown -R ${APP_USER}:${APP_USER} /usr/local/share/cwb/

RUN mkdir -p /app /app/config /data/cwb/data /data/corpus/tagged_frames /data/corpus/dtm /data/corpus/metadata /data/registry

WORKDIR /app

# Install the wheel built in the backend-builder stage
COPY --from=backend-builder /dist/wheels/*.whl /tmp/
RUN set -e; \
    pip install -q /tmp/*.whl; \
    rm -rf /tmp/*.whl

# Copy runtime files from the cloned repo (backend-builder stage)
COPY --from=backend-builder /build/backend/docker/main.py .
COPY --from=backend-builder /build/backend/docker/entrypoint.sh .
COPY --from=backend-builder /build/backend/docker/test-network.sh .

# Install frontend assets built in the frontend-builder stage
RUN mkdir -p public && chown ${APP_USER}:${APP_USER} public && chmod 755 public

COPY --from=frontend-builder /dist/frontend.tar.gz /tmp/frontend.tar.gz
RUN set -e; \
    tar -xzf /tmp/frontend.tar.gz -C /app/public; \
    rm /tmp/frontend.tar.gz; \
    echo "${FRONTEND_BRANCH}" > /app/public/.frontend_version

# Set permissions
RUN set -e; \
    chown -R ${APP_USER}:${APP_USER} /data; \
    chown -R ${APP_USER}:${APP_USER} /app/public; \
    chmod +x entrypoint.sh; \
    chmod +x test-network.sh

USER ${APP_USER}

ENV SHELL=/bin/bash
ENV HOME=/app

ARG CORPUS_REGISTRY=/data/registry
ENV CORPUS_REGISTRY=${CORPUS_REGISTRY}

ARG SWEDEB_PORT=8092
ENV SWEDEB_PORT=${SWEDEB_PORT}

ARG CONFIG_FILE=config/config.yml
ENV CONFIG_FILE=${CONFIG_FILE}

EXPOSE ${SWEDEB_PORT}

ENTRYPOINT ["./entrypoint.sh"]
