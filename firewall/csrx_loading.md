# Loading the cSRX Image and License

How to get the Juniper cSRX container image (a `.tgz` you downloaded) into Docker and licensed, so the firewall testbed (`setup.sh`) can use it.

> Run everything **on the host where Docker and the lab run** (your Ubuntu box), not on a separate machine. The `.tgz` is a Docker *image archive* — you **load** it into Docker; you don't place it in a folder for something to read.

## 1. Put the file somewhere (optional, for tidiness)

The location doesn't matter to Docker once loaded, but a tidy spot inside the project is `firewall/images/` — it's **gitignored**, so the large, licensed binary can never be committed by accident.

```bash
mkdir -p firewall/images
mv /path/to/cSRX*.tgz firewall/images/
```

## 2. Load the image into Docker

`docker load` reads the archive (it handles the gzip in a `.tgz` or `.tar.gz`):

```bash
docker load -i firewall/images/cSRX*.tgz
```

## 3. Find the image name:tag it loaded as

```bash
docker images | grep -i csrx
```

You'll see a line like:

```
REPOSITORY   TAG          IMAGE ID       CREATED       SIZE
csrx         24.2R1.x     abc123def456   ...           ~500MB
```

Note the **REPOSITORY:TAG** (e.g. `csrx:24.2R1.x`).

## 4. Point the scaffold at it

```bash
export CSRX_IMAGE="csrx:24.2R1.x"     # whatever tag step 3 reported
```

`firewall/setup.sh` reads `CSRX_IMAGE`, so from here the testbed can launch the container.

## 5. Apply the license (separate step)

Loading the image gives you the firewall **binary**; features stay limited until you apply the **60-day evaluation license**. Do this after the container is up, in the Junos CLI:

```bash
docker exec -it csrx cli
> request system license add terminal      # paste the license key, then Ctrl-D
# (or the exact method in your Juniper eval email)
> show system license                      # verify it's installed and valid
```

## Quick reference

```bash
# one-time, on the Ubuntu host:
mkdir -p firewall/images && mv /path/to/cSRX*.tgz firewall/images/
docker load -i firewall/images/cSRX*.tgz
docker images | grep -i csrx               # note REPOSITORY:TAG
export CSRX_IMAGE="csrx:<tag>"
# then:
./firewall/setup.sh                        # launch attacker -> cSRX -> target
# load config + license (see firewall/README.md and step 5 above)
```

## Notes

- **Never commit the image archive or the license** — both are covered by `.gitignore` (`firewall/images/`, `*csrx*.tgz`, `*csrx*.tar`). They're large and licensed to you.
- The eval license **expires after 60 days**.
- If `docker load` errors on a `.tgz`, decompress first: `gunzip -k cSRX*.tgz` then `docker load -i cSRX*.tar`.
- Full run-through of the testbed is in [`README.md`](README.md); the design and attack→mitigation mapping are in [`../docs/FIREWALL.md`](../docs/FIREWALL.md).
