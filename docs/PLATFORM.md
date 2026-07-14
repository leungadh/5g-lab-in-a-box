# Platform Guide — Preparing the Ubuntu Appliance & Running the Lab

This guide takes a bare Intel/AMD (x86-64) machine to a running 5G SA lab. It expands the automation in [`scripts/bootstrap.sh`](../scripts/bootstrap.sh) and [`infra/ansible/playbook.yml`](../infra/ansible/playbook.yml) so you understand each step.

> **The one hard constraint:** the Open5GS **UPF** needs the `gtp5g` Linux kernel module, which requires a real, modifiable Linux kernel (≥ 5.4). This is why the lab runs on native Ubuntu (or a full Linux VM) and **not** on Docker Desktop for Mac/Windows.

---

## 1. Hardware / host requirements

| Resource | Minimum | Comfortable | Notes |
|---|---|---|---|
| CPU | 2 cores (x86-64) | 4+ cores | Intel or AMD 64-bit. |
| RAM | 4 GB | 8–16 GB | Core + RAN + capture is light; more RAM helps when capturing. |
| Disk | 20 GB | 40 GB+ | Container images + pcaps. Captures grow fast — see cleanup. |
| Network | 1 NIC with internet | — | Needed for image pulls and UE N6 egress. |
| Virtualization | bare metal preferred | full VM OK | UTM/VMware/VirtualBox/Multipass fine; **Docker Desktop is not** (no kernel modules). |

A spare laptop, NUC, or mini-PC on bare metal is ideal. If you virtualize, use a **full Linux VM** (its own kernel), not a container runtime.

## 2. Operating system

Install **Ubuntu Server 22.04 LTS** or **24.04 LTS** (x86-64). Server or Desktop both work; Server is leaner.

After first boot, update and confirm the kernel:

```bash
sudo apt update && sudo apt -y upgrade
uname -r          # must be >= 5.4  (22.04/24.04 ship 5.15/6.x — fine)
uname -m          # must be x86_64
```

Install the tools the lab and the kernel-module build need:

```bash
sudo apt install -y git build-essential make curl \
     linux-headers-$(uname -r) tcpdump python3 python3-pip
```

`linux-headers-$(uname -r)` is required to compile `gtp5g` against your running kernel.

## 3. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"   # run docker without sudo
newgrp docker                      # apply group now (or log out/in)
docker run --rm hello-world        # verify
```

## 4. Build & load the gtp5g kernel module (the critical step)

The UPF's GTP-U datapath lives in this out-of-tree module.

```bash
git clone https://github.com/free5gc/gtp5g.git
cd gtp5g
make
sudo make install
sudo modprobe gtp5g
lsmod | grep gtp5g          # should print a line -> success
cd ..
```

If `modprobe` fails, you are almost always missing `linux-headers-$(uname -r)` (step 2) or the build errored — re-run `make` and read the output. After a **kernel upgrade** you must rebuild this module.

## 5. Host networking

Enable forwarding and the tun device (the `bootstrap` target also does this):

```bash
sudo sysctl -w net.ipv4.ip_forward=1
sudo modprobe tun
```

N6 egress NAT (so the UE can reach the internet through the UPF) is added automatically by `scripts/bootstrap.sh` using your default route interface.

## 6. Install UERANSIM (simulated RAN)

The gNB/UE simulator. Build once from source:

```bash
sudo apt install -y cmake libsctp-dev lksctp-tools iproute2
git clone https://github.com/aligungr/UERANSIM.git
cd UERANSIM && make       # produces build/nr-gnb, build/nr-ue
# put the binaries on PATH, e.g.:
sudo ln -s "$PWD/build/nr-gnb" /usr/local/bin/nr-gnb
sudo ln -s "$PWD/build/nr-ue"  /usr/local/bin/nr-ue
cd ..
```

## 7. Get the lab and configure it

```bash
git clone https://github.com/leungadh/5g-lab-in-a-box.git
cd 5g-lab-in-a-box

# top-level env: IMSI, keys, PLMN, UE subnet
cp .env.example .env
nano .env                       # set/rotate KI and OPC before real use

# Open5GS per-NF configs: pull upstream defaults, then edit
cp deploy/open5gs/.env.example deploy/open5gs/.env
docker run --rm gradiant/open5gs:2.7.5 \
  tar -C /opt/open5gs/etc/open5gs -c . | tar -x -C deploy/open5gs/configs
# then reconcile amf/smf/upf YAML with .env  (see deploy/open5gs/configs/README.md)
```

Key values to make consistent across `.env`, the Open5GS configs, and `deploy/ran/ueransim/{gnb,ue}.yaml`: **MCC/MNC, TAC, SST/SD, IMSI, KI, OPC, and the UE subnet.**

## 8. Bring the lab up

```bash
make bootstrap            # idempotent host prep (docker, gtp5g check, NAT)
make up                   # start the Open5GS core + WebUI
make provision-subscriber # add the test IMSI from .env
make ran-up               # start gNB then UE  (UE should get an IP)
make smoke-test           # verify end-to-end data path (UE -> internet)
```

Success looks like: `docker compose ps` all healthy, the WebUI reachable at `http://localhost:9999`, a `uesimtun0` interface with an IP in your UE subnet, and `smoke-test` passing a ping through N6.

Tear down with `make down`; stop just the RAN with `make ran-down`.

## 9. Run traffic & capture (once the lab is live)

```bash
pip3 install --break-system-packages scapy pandas pyarrow
make capture DURATION=120                                   # benign baseline
make attack ATTACK=gtpu/malformed_gtpu.py                   # (needs --i-own-this-lab; see attacks/README.md)
./capture/run_labeled_dataset.sh                            # benign + each attack, labeled
python3 capture/extract_features.py "capture/pcaps/*.pcap" -o capture/data/features.parquet
```

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| UPF container restarts / no data path | `gtp5g` not loaded | `lsmod \| grep gtp5g`; rebuild (step 4); rebuild after kernel upgrades |
| `modprobe gtp5g` fails to build | missing kernel headers | `sudo apt install linux-headers-$(uname -r)` then `make` again |
| UE has no IP / `uesimtun0` missing | gNB↔AMF (N2) or subscriber mismatch | check `/tmp/gnb.log`, `/tmp/ue.log`; verify IMSI/keys match `.env`; confirm AMF N2 reachable |
| UE gets IP but no internet | N6 NAT / forwarding | re-run `make bootstrap`; confirm `net.ipv4.ip_forward=1` |
| Everything fails on Mac/Windows | Docker Desktop can't load kernel modules | use native Ubuntu or a full Linux VM |
| Disk fills up | pcaps accumulating | `make clean`; captures are git-ignored |

## 11. Optional: reproduce the host with Ansible

Once you have one working host, [`infra/ansible/playbook.yml`](../infra/ansible/playbook.yml) reproduces steps 2–5 on any Ubuntu target:

```bash
cd infra/ansible
cp inventory.ini.example inventory.ini   # add your host
ansible-playbook -i inventory.ini playbook.yml
```

---

### At a glance

Native **x86-64 Ubuntu 22.04/24.04** → install headers + docker → **build `gtp5g`** → build UERANSIM → clone repo, fill `.env` + configs → `make bootstrap up provision-subscriber ran-up smoke-test`. The only step that genuinely bites is the `gtp5g` module; everything else is scripted.
