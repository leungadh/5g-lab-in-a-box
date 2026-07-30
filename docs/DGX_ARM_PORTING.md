# Porting the Lab to ARM64 / DGX Spark

The DGX Spark is **ARM64 (aarch64)**. This guide covers what moves over cleanly, what needs a rebuild, what can't move, and the exact steps + pre-flight checks — so you can bring the lab up on the DGX without re-discovering the gotchas we already hit on x86.

## What ports, and what doesn't

| Component | Ported by | On ARM64? |
|---|---|---|
| **UERANSIM** (gNB/UE) | recompile from source | ✅ yes — C++, builds natively |
| **Open5GS** (5G core) | recompile / build arm64 images / native install | ✅ yes — C, open source |
| **ML detector** (`detector/`) | Python + PyTorch (arm64 + CUDA) | ✅ yes — and this is what the DGX is *for* |
| `gradiant/open5gs` prebuilt images | — | ❌ amd64 only — **build your own arm64 images or install natively** |
| **cSRX firewall** | Juniper must ship an arm64 image | ⚠️ only if Juniper provides aarch64 cSRX (25.4R1+ added ARM support — check the portal). You **cannot** recompile it. |

**The principle:** open-source pieces (Open5GS, UERANSIM, the detector) recompile for ARM. Closed binaries (cSRX) need a vendor ARM build. Don't emulate the x86 cSRX under QEMU — a datapath firewall won't work well emulated.

---

## Step 0 — Pre-flight kernel checks (do these FIRST)

On x86 we hit two kernel walls: containers couldn't create TUN devices (forcing the native-UPF "Path B"), and IP forwarding for the UE traffic was blocked. DGX OS is a custom NVIDIA Ubuntu with its own kernel, so re-check these before building anything:

```bash
uname -a                                             # arch + kernel version
# 1. Can a CONTAINER create a TUN device? (decides all-Docker vs native UPF)
#    Use alpine + real iproute2 — busybox's built-in `ip` lacks `tuntap` and gives false negatives.
docker run --rm --privileged --device /dev/net/tun alpine \
  sh -c 'apk add -q iproute2; ip tuntap add name t0 mode tun; echo "exit=$?"'
# 2. Host TUN + forwarding  (CONFIG_TUN=y means TUN is built-in; lsmod will be empty — that's fine)
sudo ip tuntap add name testtun0 mode tun && echo "HOST TUN: OK" && sudo ip tuntap del name testtun0 mode tun
sysctl net.ipv4.ip_forward
grep CONFIG_TUN /boot/config-$(uname -r) 2>/dev/null
# 3. Kernel headers (needed only if you build the gtp5g module for a containerized UPF)
ls /lib/modules/$(uname -r)/build 2>/dev/null && echo "headers present" || echo "install linux-headers / DGX equivalent"
```

- **`exit=0`** (container TUN works) → run the clean **all-Docker design** (containerized UPF, the repo's default Path A compose). *This is the case on the DGX Spark.*
- **`ioctl(TUNSETIFF): Operation not permitted` / `exit≠0`** → container TUN is blocked → use **Path B (native UPF)** as on x86; see [`PLATFORM.md`](PLATFORM.md) §12.

## Step 1 — UERANSIM on ARM (unchanged)

Identical to x86 — the compiler emits ARM64 automatically:

```bash
sudo apt install -y make gcc g++ cmake libsctp-dev lksctp-tools iproute2 git
git clone https://github.com/aligungr/UERANSIM.git && cd UERANSIM && make
sudo ln -sf "$PWD/build/nr-gnb" /usr/local/bin/nr-gnb
sudo ln -sf "$PWD/build/nr-ue"  /usr/local/bin/nr-ue
sudo ln -sf "$PWD/build/nr-cli" /usr/local/bin/nr-cli
```

## Step 2 — Open5GS on ARM (pick ONE)

**First, try pulling — the image may already be multi-arch:**

```bash
docker pull gradiant/open5gs:2.7.5      # if it pulls, Docker grabbed the arm64 variant — use as-is
```
If that succeeds, you're done: the repo's `deploy/open5gs/docker-compose.yml` works unchanged (with container TUN available, keep the default all-Docker/Path A compose). If it errors with `no matching manifest for linux/arm64`, the image is amd64-only — use one of the two options below.

Two ways to get an arm64 Open5GS:

**Option A — build arm64 Docker images yourself** (keeps the `deploy/open5gs/docker-compose.yml` flow). On the ARM DGX, a native `docker build` produces arm64 images:

```bash
# from an Open5GS Dockerfile (Open5GS repo, or a community/gradiant Dockerfile):
git clone https://github.com/open5gs/open5gs.git
cd open5gs
docker build -t open5gs:arm64 .          # native build on the DGX = arm64 image
# then point deploy/open5gs/docker-compose.yml + .env at open5gs:arm64
#   (set OPEN5GS_IMAGE=open5gs:arm64 in deploy/open5gs/.env)
```
Adjust the `command:` per-NF entries if the image's entrypoint differs from gradiant's, and re-extract the default configs from *your* image with `make configs` (it reads `$OPEN5GS_IMAGE`).

**Option B — install Open5GS natively on the host** (pairs naturally with Path B / native UPF):

```bash
# build from source (reliable on arm64):
sudo apt install -y python3-pip python3-setuptools python3-wheel ninja-build \
  build-essential flex bison git cmake libsctp-dev libgnutls28-dev libgcrypt-dev \
  libssl-dev libidn11-dev libmongoc-dev libbson-dev libyaml-dev libnghttp2-dev \
  libmicrohttpd-dev libcurl4-gnutls-dev libtins-dev libtalloc-dev meson mongodb-org
git clone https://github.com/open5gs/open5gs.git && cd open5gs
meson build --prefix=`pwd`/install && ninja -C build && cd build && ninja install
# (Open5GS also ships apt packages via its repo — check for arm64 availability first)
```
Then run the NFs as host services (systemd or the daemons directly) instead of containers, and keep the UPF native (Path B) as you already do.

> **Recommendation:** if Step 0 showed container-TUN **fails** on the DGX too, go **Option B** (everything native) — it's the least friction and matches your working x86 setup. If container-TUN **works**, **Option A** (arm64 images) keeps the clean compose flow.

## Step 3 — Bring up the core (same as x86)

Once you have arm64 Open5GS + UERANSIM, the rest is unchanged:

```bash
make env
make configs                 # re-extract configs from YOUR arm64 image (Option A)
make up                      # or start native daemons (Option B)
make webui-admin             # if the WebUI account isn't seeded
make provision-subscriber
make ran-up
```

Reconcile PLMN/keys/subnet across `.env`, the NF configs, and `ue.yaml` exactly as on x86. For capture, `capture/capture.sh` already defaults to `-i any`, which works regardless of layout.

## Step 4 — Capture + detector on the DGX (the payoff)

This is what the DGX is actually for. The feature pipeline and detector are pure Python:

```bash
pip3 install --break-system-packages scapy pandas pyarrow scikit-learn
# PyTorch with CUDA for the DGX GPU (arm64 + CUDA build):
pip3 install --break-system-packages torch --index-url https://download.pytorch.org/whl/cu124   # match your CUDA
```
Then the usual: `run_labeled_dataset.sh` → `extract_features.py` → `make detector-train`. The autoencoder and the heavier sequence/graph models (Roadmap Phase 5) run on the GPU here.

## cSRX firewall on ARM

- **First:** check the Juniper download portal for an **aarch64/arm64 cSRX 26.2R1.7** image (ARM support landed in 25.4R1). If it exists, `docker load` it and run the `firewall/` testbed unchanged.
- **If not:** keep cSRX on your **x86 Intel box** and don't emulate it. See the split below.

## Recommended architecture

Two sensible layouts — choose by goal:

| Goal | Layout |
|---|---|
| **DGX for ML, least effort** | 5G core + cSRX firewall on the **x86 box** (already working); DGX Spark runs only the **detector training** (GPU). Nothing to port except pointing the detector at captured data. |
| **Consolidate on the DGX** | Port the 5G core to arm64 (Steps 1–3) + run the detector on the GPU. Firewall works only if the arm64 cSRX image exists; otherwise leave cSRX on x86 and route to it. |

The split is less work and plays to each machine's strength — but the core **is** portable if you want everything on one box.

## Checklist

- [ ] Step 0 kernel checks (container-TUN? forwarding? headers?)
- [ ] UERANSIM built on the DGX
- [ ] Open5GS arm64 (Option A images **or** Option B native)
- [ ] `.env` / configs / `ue.yaml` reconciled; core comes up; UE attaches
- [ ] detector deps + PyTorch(CUDA) installed; training runs on the GPU
- [ ] cSRX: arm64 image obtained **or** firewall kept on x86

---

**Bottom line:** the open-source 5G core (Open5GS + UERANSIM) and the ML detector **port to the DGX Spark** — it's a build effort, not a wall. The only true blocker is cSRX, which needs a Juniper arm64 image (likely available in 26.2R1.7 — verify) since you can't recompile it yourself.
