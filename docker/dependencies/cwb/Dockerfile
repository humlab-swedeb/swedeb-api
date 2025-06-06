
ARG PYTHON_VERSION="3.12"

FROM python:${PYTHON_VERSION}-slim AS cwb-builder

#####################################################################################
# CWB build phase (cwb-builder)
#####################################################################################

ARG CWB_VERSION="3.5.0"

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends \
        build-essential apt-utils pkg-config autoconf bison flex subversion tar wget \
        libpcre3-dev libglib2.0-dev libncurses-dev libncurses5-dev \
        libreadline-dev libc6-dev \
        && rm -rf /var/lib/apt/lists/*

# Compile CWB Core & CWB Perl

WORKDIR /src

# RUN wget -O cwb-dev.deb "https://sourceforge.net/projects/cwb/files/cwb/cwb-3.5/deb/cwb_3.5.0-1_amd64.deb/download" \
#     && dpkg -i cwb-dev.deb \
#     && rm cwb-dev.deb

RUN set -e && \
    wget -O cwb-${CWB_VERSION}-src.tar.gz https://sourceforge.net/projects/cwb/files/cwb/cwb-3.5/source/cwb-${CWB_VERSION}-src.tar.gz/download \
    && tar -xzvf cwb-${CWB_VERSION}-src.tar.gz \
    && rm cwb-${CWB_VERSION}-src.tar.gz \
    && cd /src/cwb-${CWB_VERSION}-src \
    && touch local_config.mk && echo "export PLATFORM=linux-native" >> local_config.mk \
    && ./install-scripts/install-linux \
    \
    && svn co --trust-server-cert --non-interactive --quiet https://svn.code.sf.net/p/cwb/code/perl/trunk cwb-perl \
    && cd cwb-perl/CWB \
    && perl Makefile.PL --config=/usr/local/bin/cwb-config \
    && make \
    && make test \
    && make install

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /wheels

# Create (compiled) cwb-ccc wheel, and association-measures wheel that requires build tools

RUN pip install --upgrade pip \
    && pip install setuptools wheel \
    \
    && pip wheel --no-cache-dir --no-deps --wheel-dir /wheels "association-measures" \
    && pip wheel --no-cache-dir --no-deps --wheel-dir /wheels cwb-ccc

#####################################################################################
# CWB install phase (cwb-image)
#####################################################################################

FROM python:${PYTHON_VERSION}-slim-bookworm AS cwb-image

ENV LANG C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive
ENV LD_LIBRARY_PATH=/usr/local/lib

RUN apt-get update \
    && apt-get install -y -qq --no-install-recommends \
        libpcre3 libglib2.0-0 libncurses5 libreadline8 readline-common \
        git less gzip bzip2 curl wget \
    && rm -rf /var/lib/apt/lists/*

COPY --from=cwb-builder /usr/local/bin/ /usr/local/bin/
COPY --from=cwb-builder /usr/local/lib/ /usr/local/lib/
COPY --from=cwb-builder /usr/local/include/ /usr/local/include/
COPY --from=cwb-builder /wheels /wheels

RUN set -e && \
    ldconfig && \
    mkdir -p /usr/local/share/cwb/ && \
    pip3 install /wheels/*.whl

LABEL maintainer="Roger Mähler <roger dot mahler at umu dot se>"

ARG CWB_UID="1021"
ARG CWB_GID="1021"
ARG CWB_USER="cwbuser"

RUN addgroup --gid $CWB_GID "${CWB_USER}" && \
    adduser $CWB_USER --home /home/${CWB_USER} --uid $CWB_UID --gid $CWB_GID --disabled-password --gecos '' --shell /bin/bash && \
    mkdir -p /data && \
    chown -R ${CWB_USER}:${CWB_USER} /data && \
    chown -R ${CWB_USER}:${CWB_USER} /usr/local/share/cwb/

WORKDIR /home/${CWB_USER}

USER ${CWB_USER}

ENV SHELL=/bin/bash
ENV HOME=/home/${CWB_USER}

# ENV CORPUS_REGISTRY=/data/registry

ENTRYPOINT [ "/bin/bash" ]

CMD [ "-c", "cqp -h" ]
