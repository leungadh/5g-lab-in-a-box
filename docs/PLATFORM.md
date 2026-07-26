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

# 7a. Create the env files (top-level + compose profile). `make env` does both.
make env
#   equivalently:
#   cp .env.example .env                              # IMSI, keys, PLMN, UE subnet
#   cp deploy/open5gs/.env.example deploy/open5gs/.env
nano .env                       # set/rotate KI and OPC before real use

# 7b. Populate the Open5GS NF configs from the image defaults. `make configs` does this.
make configs
#   This removes any directories Docker may have auto-created in place of the
#   config files, then extracts the real YAMLs from the image into
#   deploy/open5gs/configs/. (Manual equivalent is in deploy/open5gs/configs/README.md.)
```

> **Why `make configs` matters:** the compose file bind-mounts individual files like
> `configs/nrf.yaml`. If those files don't exist, Docker silently creates them as
> **directories**, and `make up` then fails with *"not a directory: are you trying to
> mount a directory onto a file"*. `make configs` prevents (and cleans up) that.

Then reconcile the data-plane values so the UE can attach. The extracted configs carry the image defaults; edit these to match your `.env`:

- **amf.yaml** — `plmn_id` (MCC/MNC), `tac`, `s_nssai` (SST/SD); NGAP bind `0.0.0.0`.
- **smf.yaml** — session subnet = `UE_SUBNET`; UPF peer.
- **upf.yaml** — GTP-U bind `0.0.0.0`; subnet matching the SMF pool.

Key values to keep consistent across `.env`, the Open5GS configs, and `deploy/ran/ueransim/{gnb,ue}.yaml`: **MCC/MNC, TAC, SST/SD, IMSI, KI, OPC, and the UE subnet.**

## 8. Bring the lab up

```bash
make bootstrap            # idempotent host prep (docker, gtp5g check, NAT)
make up                   # start the Open5GS core + WebUI (auto-creates .env if missing)
make webui-admin          # seed the WebUI admin account (only if login fails — see 8a)
make provision-subscriber # add the test IMSI from .env
make ran-up               # start gNB then UE  (UE should get an IP)
make smoke-test           # verify end-to-end data path (UE -> internet)
```

Success looks like: `docker compose -f deploy/open5gs/docker-compose.yml ps` all healthy, the WebUI reachable at `http://localhost:9999`, a `uesimtun0` interface with an IP in your UE subnet, and `smoke-test` passing a ping through N6.

### 8a. WebUI login

Open `http://localhost:9999` and log in with the Open5GS defaults:

- **Username:** `admin`
- **Password:** `1423`

**If login fails with "wrong password":** the WebUI only seeds that default account on
startup when it can reach Mongo *and* the accounts collection is empty — on a compose
cold start it often boots before Mongo is ready and skips seeding. Fix it with:

```bash
make webui-admin          # inserts a correct admin/1423 account into MongoDB
```

Verify (should return `1`):

```bash
docker compose -f deploy/open5gs/docker-compose.yml exec mongo \
  mongosh open5gs --quiet --eval 'db.accounts.countDocuments({})'
```

Change the password after first login. The WebUI is only needed to view/manage
subscribers; `make provision-subscriber` adds the test IMSI without it.

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
| `make up`: cannot find env file `.env` | compose profile `.env` not created | `make env` (or `cp deploy/open5gs/.env.example deploy/open5gs/.env`) |
| `make up`: *not a directory... mount a directory onto a file* | NF config files missing; Docker auto-created them as directories | `make configs` (removes the bogus dirs and extracts real configs) |
| WebUI login "wrong password" | admin account never seeded (Mongo not ready at webui boot) | `make webui-admin`; verify `db.accounts.countDocuments({})` is `1` |
| NFs start but keep restarting / can't reach NRF | default configs use `127.0.0.x` loopback across containers | point each NF's `sbi` client at service names (`nrf`, `scp`); bind servers to `0.0.0.0` |
| UPF container: `ioctl(TUNSETIFF): Operation not permitted` | kernel won't let a container create a TUN device (even privileged) | run the UPF natively — **Path B** (§12); or boot a stock kernel (Outstanding Issue) |
| SMF crash loop: `getaddrinfo(upf) failed` | UPF not resolvable at SMF startup (container down, or Path B) | ensure UPF is up first (compose `depends_on: [scp, upf]`); Path B: `extra_hosts: ["upf:<HOST_IP>"]` |
| SMF crash: `smf_fd_init ... fd_conf_parse Invalid argument` | freeDiameter (Gx/Gy) enabled but not used in 5G SA | comment out `freeDiameter:` in `smf.yaml` (§12c) |
| SMF: `No Response / Retry association [ip]:8805` | SMF↔UPF PFCP path asymmetric (reply from a different IP) | make both sides use the host's real IP (§12); symmetric target/reply |
| gNB: `RLS/GTP Socket bind failed: Address already in use` | stale `nr-gnb`/`nr-ue` from a prior run holding ports | `sudo pkill -9 -f nr-gnb; sudo pkill -9 -f nr-ue` (now built into `ran.sh`) |
| UE has no IP / `uesimtun0` missing | gNB↔AMF (N2) or subscriber mismatch | check `/tmp/gnb.log`, `/tmp/ue.log`; verify IMSI/keys match `.env`; confirm AMF N2 reachable |
| UE `ue.log`: missing field (`integrityMaxRate`, `uacAic`, …) | UERANSIM `ue.yaml` incomplete for its version | use the complete `deploy/ran/ueransim/ue.yaml` in this repo |
| UE gets IP + PDU session but no internet | host forwarding/NAT — or the kernel forwarding block | `sudo ./scripts/host-forward.sh`; if `IpForwDatagrams` never moves, see Outstanding Issue |
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

## 12. Path B — run the UPF natively on the host

Use this when **a container cannot create a TUN device** on your host (see the Outstanding Issue below). The control plane stays in Docker; only the UPF runs natively, where TUN works. This was validated end to end (registration → PDU session → N3 traffic).

**12a. Install and configure the UPF on the host**

```bash
# install ONLY the UPF (not the full open5gs metapackage — it would start
# duplicate daemons that fight the containers for ports)
sudo add-apt-repository -y ppa:open5gs/latest
sudo apt update && sudo apt install -y open5gs-upf
```

Edit `/etc/open5gs/upf.yaml` so PFCP is reachable from the containers and GTP-U
sits on a loopback address that won't collide with the host gNB. Use your host's
primary IP for PFCP (so its node_id and reply source match what the SMF targets):

```yaml
upf:
  pfcp:
    server:
      - address: <HOST_IP>        # e.g. 192.168.50.13 — reachable from the SMF container
  gtpu:
    server:
      - address: 127.0.0.7        # host loopback; gNB (127.0.0.1) reaches it, no port clash
  session:
    - subnet: 10.45.0.1/16        # the interface address in CIDR (NOT 10.45.0.0/16 + gateway)
      dev: ogstun
```

```bash
sudo systemctl restart open5gs-upfd
ip addr show ogstun | grep inet     # must show: inet 10.45.0.1/16
sudo ss -ulnp | grep 8805           # pfcp on <HOST_IP>:8805
```

**12b. Point the Docker stack at the host UPF**

```bash
# remove the container UPF and stop it restarting
docker compose -f deploy/open5gs/docker-compose.yml rm -sf upf
sed -i '/command: open5gs-upfd/a\    profiles: ["native-on-host"]' deploy/open5gs/docker-compose.yml

# SMF: drop the upf container dependency; map the 'upf' hostname to the host IP
sed -i 's/depends_on: \[scp, upf\]/depends_on: [scp]/' deploy/open5gs/docker-compose.yml
sed -i '/command: open5gs-smfd/a\    extra_hosts: ["upf:<HOST_IP>"]' deploy/open5gs/docker-compose.yml
```

**12c. Disable Diameter in the SMF** (not used in 5G SA — policy is via PCF/SBI). The
default config enables freeDiameter (Gx/Gy) which fails to init and crashes the SMF:

```bash
sed -i 's|^\(\s*\)freeDiameter:|\1# freeDiameter:|' deploy/open5gs/configs/smf.yaml
```

**12d. Bring up and apply host networking**

```bash
make up
sudo ./scripts/host-forward.sh            # NAT + forwarding + rp_filter for the UE subnet
```

Verify the join: `docker compose ... logs smf` and `journalctl -u open5gs-upfd` should
both show **PFCP associated**. Then `make ran-up` — the UE should register and establish
a PDU session against the native UPF.

**Why these specific addresses:** the SMF (a container on the `open5gs-core` bridge)
must reach the host UPF over a path where the request target and the reply source are
the same IP, or PFCP can't match the peer. Using the host's real IP for both the SMF's
`upf` mapping and the UPF's PFCP bind makes the association symmetric. GTP-U (N3) stays
on loopback because the gNB runs on the same host.

## Outstanding issue — internet egress blocked on kernel 7.0.0-28-generic

**Status:** 5G core fully working (registration, authentication, N4 PFCP, N3 GTP-U
uplink all verified). **Internet egress (N6) does not work on the original lab host.**

**Symptom:** a UE (`uesimtun0`, `10.45.0.x`) cannot ping the internet *or* even the UPF
gateway (`10.45.0.1`). Uplink packets reach the UPF's `ogstun` (confirmed with
`tcpdump -i ogstun`), but the kernel never forwards them: `IpForwDatagrams` (via
`nstat`) does not increment and nothing appears on the egress interface.

**What was verified correct (so these are NOT the cause):**

- `net.ipv4.ip_forward = 1`, `conf.all.forwarding = 1`, `conf.ogstun.forwarding = 1`.
- `rp_filter` set to `0` on all/ogstun/egress.
- `ogstun` is `UP`/`LOWER_UP` with `inet 10.45.0.1/16`.
- Valid default route: `ip route get 8.8.8.8` → `via <gw> dev wlp129s0`.
- NAT masquerade rule present for `10.45.0.0/16` out the egress interface.
- `FORWARD` accept rules present for `ogstun` (Docker sets FORWARD policy to DROP).
- All of the above are applied by [`scripts/host-forward.sh`](../scripts/host-forward.sh).

**Likely root cause:** the host runs a **non-standard `7.0.0-28-generic` kernel**
(Ubuntu 24.04 normally ships a 6.x kernel). The **same kernel already blocked a second
unrelated operation**: no container — privileged, host-network, or fully unconfined —
can create a TUN device (`ioctl(TUNSETIFF): Operation not permitted`), while the host
can. Two independent, correctly-configured kernel operations silently failing on the
same custom kernel strongly points to the kernel itself.

**Recommended solution — boot the stock kernel.** A `6.17.0-14-generic` kernel is
installed alongside the 7.0 one. Booting it may fix **both** problems at once, and if
container TUN works there, Path B is unnecessary — run the clean all-Docker setup
(privileged UPF container) instead.

```bash
# one-time boot of 6.17 (default stays 7.0)
sudo grub-reboot "Advanced options for Ubuntu>Ubuntu, with Linux 6.17.0-14-generic"
sudo reboot

# after reboot: does a container get TUN now?
uname -r    # 6.17.0-14-generic
docker run --rm --privileged --device /dev/net/tun --entrypoint sh gradiant/open5gs:2.7.5 \
  -c 'ip tuntap add name t0 mode tun && echo "TUN OK" || echo "TUN FAILED"'
```

- **TUN OK** → unpark the `upf` service (remove its `profiles:` line), revert the SMF
  `extra_hosts`/`depends_on` edits, `make up`, then `sudo ./scripts/host-forward.sh`.
  Host forwarding will very likely work on the stock kernel and internet egress with it.
- **TUN FAILED** → stay on Path B. The data plane works on loopback (UE ↔ core ↔ UPF);
  internet egress would then need deeper kernel debugging (`bpftrace`/`dropwatch`) or a
  wired uplink on a stock kernel.

**Does egress matter for this project?** No. The attack scripts target N3/N4 at
lab/loopback addresses and capture runs on those interfaces — none of it requires the UE
to reach the public internet. Egress is a convenience for the `smoke-test`, not a
prerequisite for the security work.

---

### At a glance

Native **x86-64 Ubuntu 22.04/24.04** → install headers + docker → build UERANSIM →
clone repo, fill `.env` + configs → `make env configs up webui-admin provision-subscriber ran-up`.
If a container can't create TUN on your kernel, use **Path B** (native UPF). The 5G core
comes up cleanly; the only environment-specific hurdle is kernel support for TUN /
forwarding — see the Outstanding Issue.
