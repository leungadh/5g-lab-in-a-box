# Build Open5GS from source — produces a NATIVE-arch image (arm64 on the DGX Spark,
# amd64 on x86). Use this when no prebuilt image exists for your architecture
# (gradiant/open5gs is amd64-only).
#
# Layout matches what deploy/open5gs/docker-compose.yml expects (same as the gradiant image):
#   - the per-NF binaries (open5gs-nrfd, open5gs-amfd, ...) are on PATH  -> the compose `command:` works
#   - default configs live in /opt/open5gs/etc/open5gs/                  -> `make configs` extracts from there
#
# Build (on the DGX, a native docker build = arm64):
#   docker build -t open5gs:arm64 deploy/open5gs
# Then point the compose at it:
#   echo 'OPEN5GS_IMAGE=open5gs:arm64' >> deploy/open5gs/.env
#   make configs && make up
#
# Deps below track the Open5GS "Building from Sources" guide; if a package name has
# changed on your Ubuntu base, adjust it (the build step will name the missing one).

FROM ubuntu:24.04
ARG OPEN5GS_VERSION=v2.7.5
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      git ca-certificates meson ninja-build cmake \
      python3-pip python3-setuptools python3-wheel build-essential flex bison \
      libsctp-dev libgnutls28-dev libgcrypt-dev libssl-dev libidn11-dev \
      libmongoc-dev libbson-dev libyaml-dev libnghttp2-dev libmicrohttpd-dev \
      libcurl4-gnutls-dev libtins-dev libtalloc-dev iproute2 iptables \
 && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch ${OPEN5GS_VERSION} https://github.com/open5gs/open5gs.git /src \
 && cd /src \
 && meson setup build --prefix=/opt/open5gs \
 && ninja -C build \
 && ninja -C build install \
 && rm -rf /src

ENV PATH="/opt/open5gs/bin:${PATH}"
