FROM python:3.11-slim as builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends \
        build-essential apt-utils pkg-config autoconf bison flex subversion tar wget \
        libpcre3-dev libglib2.0-dev libncurses-dev libncurses5-dev \
        libreadline-dev libc6-dev \
        && rm -rf /var/lib/apt/lists/*


#####################################################################################
# Compile CWB Core & CWB Perl
#####################################################################################

ARG CWB_VERSION="3.5.0"

WORKDIR /src

# ADD https://svn.code.sf.net/p/cwb/code/cwb/trunk cwb.revision
# RUN svn co -r HEAD --trust-server-cert --non-interactive --quiet https://svn.code.sf.net/p/cwb/code/cwb/trunk/ cwb
# - install .deb instead? https://sourceforge.net/projects/cwb/files/cwb/cwb-3.5/deb/cwb-dev_3.5.0-1_amd64.deb/download

RUN wget -O cwb-${CWB_VERSION}-src.tar.gz https://sourceforge.net/projects/cwb/files/cwb/cwb-3.5/source/cwb-${CWB_VERSION}-src.tar.gz/download \
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
    && make install \
    \
    && cd /usr/local/bin && tar -cf /tmp/cwb.bin.install.tar cqp* cwb* \
    && cd /usr/local/include && tar -cf /tmp/cwb.include.install.tar cwb \
    && cd /usr/local/lib && tar -cf /tmp/cwb.lib.install.tar libcl*

#####################################################################################
# Create (compiled) cwb-ccc wheel
#####################################################################################

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /wheels
RUN pip install --upgrade pip \
    && pip install setuptools wheel \
    \
    && pip wheel --no-cache-dir --no-deps --wheel-dir /wheels "association-measures==0.3.0" \
    && pip wheel --no-cache-dir --no-deps --wheel-dir /wheels cwb-ccc

#####################################################################################
# Final stage
#####################################################################################

FROM python:3.11-slim-bookworm as final

LABEL maintainer="Roger Mähler <roger dot mahler at umu dot se>"

ARG SWEDEB_UID="1021"
ARG SWEDEB_GID="1021"
ARG SWEDEB_USER="swedeb"

ENV LANG C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive
ENV LD_LIBRARY_PATH=/usr/local/lib

RUN apt-get update && apt upgrade -y -qq > /dev/null \
    && apt-get install -y -qq --no-install-recommends \
        libpcre3 libglib2.0-0 libncurses5 libreadline8 readline-common \
        sudo git less gzip bzip2 curl wget \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --gid $SWEDEB_GID "${SWEDEB_USER}"  \
    && adduser $SWEDEB_USER --uid $SWEDEB_UID --gid $SWEDEB_GID --disabled-password --gecos '' --shell /bin/bash \
    && adduser $SWEDEB_USER sudo \
    && echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# If enable compilation of e.g. Python packages
# RUN apt-get update && apt upgrade -y -qq > /dev/null \
#     apt-get install -y -qq --no-install-recommends \
#         build-essential autoconf libtool pkg-config software-properties-common apt-utils \
#         libglib2.0-dev libncurses5-dev libpcre3-dev \
#         perl bison flex make  \
#     && rm -rf /var/lib/apt/lists/*

# COPY --from=builder /usr/local/bin /usr/local/bin
# COPY --from=builder /usr/local/lib /usr/local/lib
COPY --from=builder /tmp/cwb.bin.install.tar /tmp/cwb.bin.install.tar
COPY --from=builder /tmp/cwb.lib.install.tar /tmp/cwb.lib.install.tar
COPY --from=builder /tmp/cwb.include.install.tar /tmp/cwb.include.install.tar
COPY --from=builder /wheels /wheels

RUN tar xf /tmp/cwb.bin.install.tar -C /usr/local/bin \
    && tar xf /tmp/cwb.lib.install.tar -C /usr/local/lib \
    && tar xf /tmp/cwb.include.install.tar -C /usr/local/include \
    && rm -f /tmp/cwb.*.install.tar \
    \
    && ldconfig \
    && mkdir -p /data/cwb/data \
    && mkdir -p /data/corpus/tagged_frames \
    && mkdir -p /data/corpus/dtm \
    && mkdir -p /data/corpus/metadata \
    && mkdir -p /usr/local/share/cwb/

WORKDIR /app

COPY dist /backend-wheels
RUN pip3.11 install /wheels/*.whl \
    && pip3.11 install /backend-wheels/api_swedeb-0.1.1-py3-none-any.whl \
    && rm -rf /backend-wheels

COPY cwb/registry /data/cwb/registry
COPY public /app/public
COPY main.py /app/main.py
COPY entrypoint.sh entrypoint.sh
COPY config /app/config

RUN ln -s /data/cwb/registry /usr/local/share/cwb/registry \
    && chmod +x entrypoint.sh

RUN chown -R ${SWEDEB_USER}:${SWEDEB_USER} /app /data

# USER ${SWEDEB_USER}

ENV SHELL=/bin/bash
ENV HOME=/app
ENV CORPUS_REGISTRY=/data/registry

# RUN python3.11 -m venv ${HOME}/.venv \
#     && . ${HOME}/.venv/bin/activate \
#     && pip install /wheels/*.whl \
#     && pip install /backend-wheels/api_swedeb-0.1.0-py3-none-any.whl \
#     && rm -rf /dist

ENV SWEDEB_PORT=${SWEDEB_PORT:-8092}

# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", ${SWEDEB_PORT}]

ENTRYPOINT ["./entrypoint.sh"]
