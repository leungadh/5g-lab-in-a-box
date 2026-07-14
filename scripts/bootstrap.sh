#!/usr/bin/env bash
# One-time host preparation for the Open5GS lab.
# Idempotent-ish: safe to re-run. Ubuntu 22.04+ assumed.
set -euo pipefail

echo "[bootstrap] checking docker..."
if ! command -v docker >/dev/null 2>&1; then
  echo "[bootstrap] installing docker..."
  curl -fsSL https://get.docker.com | sh
fi

echo "[bootstrap] enabling IP forwarding + tun..."
sudo sysctl -w net.ipv4.ip_forward=1
sudo modprobe tun || true

# The Open5GS UPF needs the gtp5g kernel module for the GTP-U datapath.
echo "[bootstrap] checking gtp5g kernel module..."
if ! lsmod | grep -q '^gtp5g'; then
  echo "[bootstrap] gtp5g not loaded. Build/install it:"
  echo "    git clone https://github.com/free5gc/gtp5g.git"
  echo "    cd gtp5g && make && sudo make install && sudo modprobe gtp5g"
  echo "[bootstrap] (continuing — UPF will fail until gtp5g is present)"
else
  echo "[bootstrap] gtp5g present."
fi

# N6 egress NAT so UE traffic can reach the internet through the UPF tun device.
N6_IFACE="${N6_IFACE:-$(ip route | awk '/default/ {print $5; exit}')}"
UE_SUBNET="${UE_SUBNET:-10.45.0.0/16}"
echo "[bootstrap] adding NAT for ${UE_SUBNET} out ${N6_IFACE}..."
sudo iptables -t nat -C POSTROUTING -s "${UE_SUBNET}" -o "${N6_IFACE}" -j MASQUERADE 2>/dev/null \
  || sudo iptables -t nat -A POSTROUTING -s "${UE_SUBNET}" -o "${N6_IFACE}" -j MASQUERADE

echo "[bootstrap] done. Next: make up"
