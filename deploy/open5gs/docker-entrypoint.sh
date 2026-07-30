#!/bin/sh
# Entrypoint for the from-source Open5GS image.
#
# For the UPF only, set up the ogstun data interface + egress NAT before starting the
# daemon. A source build (unlike the gradiant image) does NOT auto-assign ogstun's
# gateway IP or add the MASQUERADE rule, so without this the UE gets an IP but the N6
# data path / internet egress is dead. Every other NF just execs its daemon unchanged.
#
# Requires the UPF container to have NET_ADMIN (privileged in this repo's compose).
# OGSTUN_ADDR / UE_SUBNET can be overridden via env; defaults match .env (UE_SUBNET).
set -e
case "$1" in
  open5gs-upfd|*/open5gs-upfd)
    OGSTUN_ADDR="${OGSTUN_ADDR:-10.45.0.1/16}"
    UE_SUBNET="${UE_SUBNET:-10.45.0.0/16}"
    ip tuntap add name ogstun mode tun 2>/dev/null || true
    ip addr add "$OGSTUN_ADDR" dev ogstun 2>/dev/null || true
    ip link set ogstun up 2>/dev/null || true
    sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
    iptables -t nat -C POSTROUTING -s "$UE_SUBNET" ! -o ogstun -j MASQUERADE 2>/dev/null \
      || iptables -t nat -A POSTROUTING -s "$UE_SUBNET" ! -o ogstun -j MASQUERADE 2>/dev/null || true
    echo "[entrypoint] ogstun configured ($OGSTUN_ADDR) + NAT for $UE_SUBNET"
    ;;
esac
exec "$@"
