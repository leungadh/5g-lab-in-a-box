# Build UERANSIM (gNB + UE) — native-arch image (arm64 on the DGX Spark).
# Runs as a container ON the Open5GS core docker network, so N2 (to 'amf') and
# N3 (to 'upf') use container addressing — no host<->container GTP-U port conflict.
#
# Build:  docker build -t ueransim:arm64 deploy/ran/ueransim
FROM ubuntu:24.04 AS build
ARG UERANSIM_VERSION=v3.3.0
RUN apt-get update && apt-get install -y --no-install-recommends \
      git make g++ cmake libsctp-dev lksctp-tools iproute2 ca-certificates \
 && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch ${UERANSIM_VERSION} https://github.com/aligungr/UERANSIM /ueransim \
 && cd /ueransim && make

FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends \
      libsctp1 iproute2 iputils-ping gettext-base ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /ueransim/build/nr-gnb /ueransim/build/nr-ue /ueransim/build/nr-cli /usr/local/bin/
COPY entrypoint.sh /entrypoint.sh
COPY gnb.container.yaml.tmpl ue.container.yaml.tmpl /config/
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
