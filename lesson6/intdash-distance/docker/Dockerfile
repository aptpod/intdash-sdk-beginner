# -------------------------------------------------------------------
# ベースイメージ: Ubuntu 24.04 LTS
# -------------------------------------------------------------------
FROM ubuntu:24.04

# -------------------------------------------------------------------
# 基本ツールインストール
# - curl
# -------------------------------------------------------------------
RUN apt-get update && apt-get install -y \
    software-properties-common \
    curl \
    ca-certificates
RUN add-apt-repository ppa:deadsnakes/ppa
WORKDIR /root

# -------------------------------------------------------------------
# OpenAPIインストール準備
# - Javaインストール
# - npmインストール
# - OpenAPI Generatorインストール
# -------------------------------------------------------------------
RUN apt-get update && apt-get install -y \
    default-jre
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y \
    nodejs
RUN npm install @openapitools/openapi-generator-cli
RUN npx @openapitools/openapi-generator-cli version  

# -------------------------------------------------------------------
# intdash SDK for Python生成
# -------------------------------------------------------------------
ENV VERSION=v2.7.0
ENV SRC_DIR="."
RUN ./node_modules/.bin/openapi-generator-cli version-manager set 6.1.0 \
    && rm -rf "$SRC_DIR/intdash" \
    && ./node_modules/.bin/openapi-generator-cli generate \
        -g python -i https://docs.intdash.jp/api/intdash-api/${VERSION}/openapi_public.yaml \
        --package-name=intdash \
        --additional-properties=generateSourceCodeOnly=true \
        --global-property=modelTests=false,apiTests=false,modelDocs=false,apiDocs=false \
        --http-user-agent=SDK-Sample-Python-Client/Gen-By-OASGenerator \
        -o "$SRC_DIR"
RUN ls -l intdash
    
# -------------------------------------------------------------------
# Buf CLIのインストール
# - Protocol Buffers（Protobuf）を扱うツール
# -------------------------------------------------------------------
RUN BIN="/usr/local/bin" \
    && VERSION="1.45.0" \
    && curl -sSL "https://github.com/bufbuild/buf/releases/download/v${VERSION}/buf-$(uname -s)-$(uname -m)" -o "${BIN}/buf" \
    && chmod +x "${BIN}/buf"

# -------------------------------------------------------------------
# Protocol Buffersエンコーダー
# - iSCPプロトコルエンコードのためのツール
# -------------------------------------------------------------------
ENV HOME=/root
ENV PROTO_DIR=/root/proto/intdash/v1/
RUN mkdir -p ${PROTO_DIR}
COPY protocol.proto ${PROTO_DIR}
RUN sed -i -e "s/package pb;/package intdash.v1;/g" ${PROTO_DIR}/protocol.proto

RUN echo "version: v1\n\
breaking:\n\
  use:\n\
    - FILE\n\
lint:\n\
  use:\n\
    - DEFAULT" > ${HOME}/proto/buf.yaml

RUN echo "version: v1 \n\
managed: \n\
  enabled: true \n\
plugins: \n\
  - plugin: buf.build/protocolbuffers/python:v23.4 \n\
    out: gen" > ${HOME}/buf.gen.yaml

WORKDIR /root
RUN buf generate proto
RUN ls -l gen

# -------------------------------------------------------------------
# Pythonインストール
# -------------------------------------------------------------------
RUN apt-get update && apt-get install -y \
    python3.12 \
    python3.12-dev \
    python3.12-venv \
    && python3.12 -m venv ${HOME}/venv
RUN ${HOME}/venv/bin/python -m pip install --upgrade pip

# -------------------------------------------------------------------
# 依存パッケージインストール
# -------------------------------------------------------------------
RUN ${HOME}/venv/bin/python -m pip install pydantic python-dateutil urllib3
RUN ${HOME}/venv/bin/python -m pip install protobuf

# -------------------------------------------------------------------
# ZIPインストール
# -------------------------------------------------------------------
RUN apt-get update && apt-get install -y \
    zip

# -------------------------------------------------------------------
# Lambdaレイヤー用ZIPファイル生成
# -------------------------------------------------------------------
RUN mkdir -p /layer/python/lib/python3.12/site-packages
RUN cp -r intdash gen ${HOME}/venv/lib/python3.12/site-packages/* /layer/python/lib/python3.12/site-packages
RUN ls -l /layer/python/lib/python3.12/site-packages
RUN cd /layer \
    && find /layer -name "*.pyc" -delete \
    && find /layer -name "__pycache__" -type d -exec rm -r {} + \
    && zip -r /intdash_sdk.zip .
RUN ls -l /intdash_sdk.zip

# -------------------------------------------------------------------
# クリーン
# -------------------------------------------------------------------
RUN rm -rf /var/lib/apt/lists/* \
    && apt-get clean

