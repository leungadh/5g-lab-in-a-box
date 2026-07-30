#!/usr/bin/env bash
# UERANSIM container entrypoint. Resolves the container's own IP and its peer
# (AMF for the gNB, gNB for the UE) at start, templates the config, then runs.
#   docker run ... ueransim:arm64 gnb     -> nr-gnb
#   docker run ... ueransim:arm64 ue      -> nr-ue
set -e
ROLE="${1:-gnb}"
SELF_IP="$(hostname -i | awk '{print $1}')"

case "$ROLE" in
  gnb)
    AMF_IP="$(getent hosts "${AMF_HOST:-amf}" | awk '{print $1}')"
    [ -n "$AMF_IP" ] || { echo "cannot resolve AMF_HOST=${AMF_HOST:-amf} on this network"; exit 1; }
    export SELF_IP AMF_IP
    envsubst '${SELF_IP} ${AMF_IP}' < /config/gnb.container.yaml.tmpl > /tmp/gnb.yaml
    echo "[gnb] SELF_IP=$SELF_IP  AMF_IP=$AMF_IP"
    exec nr-gnb -c /tmp/gnb.yaml
    ;;
  ue)
    GNB_IP="$(getent hosts "${GNB_HOST:-gnb}" | awk '{print $1}')"
    [ -n "$GNB_IP" ] || { echo "cannot resolve GNB_HOST=${GNB_HOST:-gnb} on this network"; exit 1; }
    export GNB_IP
    envsubst '${GNB_IP}' < /config/ue.container.yaml.tmpl > /tmp/ue.yaml
    echo "[ue] GNB_IP=$GNB_IP"
    exec nr-ue -c /tmp/ue.yaml
    ;;
  *)
    echo "usage: entrypoint.sh [gnb|ue]"; exit 1 ;;
esac
