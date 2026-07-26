#!/usr/bin/env bash
# Host networking for the user-plane data path (Path B: native UPF on the host).
#
# Applies (idempotently) everything the UE traffic needs to be forwarded from the
# UPF's ogstun device out to the internet: IP forwarding, per-interface forwarding,
# relaxed reverse-path filtering, N6 egress NAT, and FORWARD accepts for ogstun.
#
# These settings are NOT persistent across reboots — re-run this after a reboot,
# or add the sysctls to /etc/sysctl.d/ and use iptables-persistent for the rules.
#
# Usage: sudo ./scripts/host-forward.sh
#
# NOTE: on the lab's original host (kernel 7.0.0-28-generic) the kernel refused to
# forward these packets even with everything below correct — see the "Outstanding
# issue" section of docs/PLATFORM.md. This script is still the right setup; on a
# stock kernel it is sufficient for internet egress.
set -euo pipefail

UE_SUBNET="${UE_SUBNET:-10.45.0.0/16}"
TUN="${TUN:-ogstun}"
EGRESS="${EGRESS:-$(ip route | awk '/default/ {print $5; exit}')}"

echo "[host-forward] UE_SUBNET=$UE_SUBNET  tun=$TUN  egress=$EGRESS"

echo "[host-forward] enabling IP forwarding..."
sysctl -w net.ipv4.ip_forward=1 >/dev/null
sysctl -w net.ipv4.conf.all.forwarding=1 >/dev/null
sysctl -w "net.ipv4.conf.${TUN}.forwarding=1" 2>/dev/null || true
sysctl -w "net.ipv4.conf.${EGRESS}.forwarding=1" 2>/dev/null || true

echo "[host-forward] relaxing reverse-path filtering..."
sysctl -w net.ipv4.conf.all.rp_filter=2 >/dev/null
sysctl -w "net.ipv4.conf.${TUN}.rp_filter=2" 2>/dev/null || true
sysctl -w "net.ipv4.conf.${EGRESS}.rp_filter=2" 2>/dev/null || true

echo "[host-forward] N6 egress NAT (masquerade)..."
iptables -t nat -C POSTROUTING -s "$UE_SUBNET" -o "$EGRESS" -j MASQUERADE 2>/dev/null \
  || iptables -t nat -A POSTROUTING -s "$UE_SUBNET" -o "$EGRESS" -j MASQUERADE

echo "[host-forward] FORWARD accepts for $TUN (Docker sets FORWARD policy to DROP)..."
iptables -C FORWARD -i "$TUN" -j ACCEPT 2>/dev/null || iptables -I FORWARD -i "$TUN" -j ACCEPT
iptables -C FORWARD -o "$TUN" -j ACCEPT 2>/dev/null || iptables -I FORWARD -o "$TUN" -j ACCEPT

echo "[host-forward] done. Verify a UE data path with: ping -I uesimtun0 8.8.8.8"
