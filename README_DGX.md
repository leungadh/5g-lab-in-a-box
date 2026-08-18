# Running the Lab on the DGX Spark

DGX-specific quick start. **The one thing that trips people up: activate the conda environment
first.** PyTorch (the GB10 CUDA build), scapy, scikit-learn, and pandas all live in the conda
`base` environment — **not** the system `python3`. If you skip this step you'll see
`PyTorch not installed` or `No module named 'scapy'`, even though everything is installed.

---

## 0. Activate the conda environment (every new shell)

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate base
```

Your prompt should now start with **`(base)`**. Verify the GPU PyTorch is visible:

```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
# expect:  2.11.0+cu128 True
```

**Golden rule:** if your prompt does **not** show `(base)`, you're on the wrong Python — activate
conda before doing anything else. That one glance prevents the "it worked yesterday" confusion.

### Make it automatic (one-time)

```bash
~/miniconda3/bin/conda init bash
```

Open a new terminal (or `source ~/.bashrc`). From then on `conda` is recognized and `base`
auto-activates, so your prompt shows `(base)` from the start.

---

## 1. Bring up the lab

```bash
cd ~/Projects/5g-lab-in-a-box
make lab-dgx-up
```

This starts the core (12 NFs, **skips the amd64-only WebUI**), starts the containerized
gNB + UE on the `open5gs-core` network, and pings `8.8.8.8` through the UE tunnel. A reply = the
lab is fully up.

> Do **not** use plain `make up` on the DGX — it tries to pull the amd64 WebUI image and fails.
> Use `make up-dgx` (core only) or `make lab-dgx-up` (core + RAN + check).

## 2. Run the attack + detection pipeline

```bash
make clean                                     # clear old pcaps/features (optional, tidy)
sudo -v                                        # cache sudo so capture doesn't prompt mid-run
capture/run_labeled_dataset_docker.sh          # ~6-7 min: benign + 4 attack classes
python capture/extract_features.py capture/pcaps/*.pcap -o capture/data/features.parquet --window 1.0
python detector/baseline.py --data capture/data/features.parquet --model both
```

Expect `[autoencoder] training on GPU: NVIDIA GB10`, ROC-AUC ≈ 1.000 (autoencoder) / 0.989
(Isolation Forest), 100% recall across the four attack classes.

## 3. Shut down

```bash
make lab-dgx-down          # stops the containerized RAN, then the core
```

Data (subscriber, pcaps, features) persists between runs — no re-provisioning needed next time.

---

## Detector dependencies

They already live in the `base` env. If you ever genuinely need to reinstall them **(inside
`base`)**:

```bash
pip install scapy pandas pyarrow scikit-learn
```

Do **not** reinstall `torch` — the working GB10 CUDA build is already in `base`, and installing it
into the system Python could pull a CPU-only or mismatched build.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `PyTorch not installed` / `No module named 'scapy' / 'sklearn'` | not in the `base` env | `source ~/miniconda3/etc/profile.d/conda.sh && conda activate base` |
| prompt doesn't show `(base)` | conda not activated | same as above; run `conda init bash` to make it permanent |
| `conda: command not found` | conda not on PATH | `source ~/miniconda3/etc/profile.d/conda.sh` (then `conda init bash` once) |
| `make up` fails: `no matching manifest for linux/arm64` | amd64 WebUI image | use `make up-dgx` / `make lab-dgx-up` instead |
| UE ping `8.8.8.8` fails after restart | RAN not attached | `CORE_NET=open5gs-core deploy/ran/ueransim/run-containers.sh up` |
| PFCP looks unstable right after `up` | cold-start timing | wait ~10s, re-check `docker compose -f deploy/open5gs/docker-compose.yml ps` / `logs smf upf` |

---

*See [`docs/DGX_ARM_PORTING.md`](docs/DGX_ARM_PORTING.md) for the full arm64 build/bring-up, and
the root [`README.md`](README.md) for the project overview.*
