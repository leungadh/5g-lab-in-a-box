# free5GC alternate profile

The lab defaults to Open5GS. This profile lets you run the same attack/capture tooling against **free5GC**, which is closer to the 3GPP SBA reference and carries weight in research/academic contexts — a useful second data point for advisory work and for showing the tooling is core-agnostic.

## How to enable

free5GC ships an official compose repo. Vendor it here and drive it with the same `make CORE=free5gc` switch:

```bash
git clone https://github.com/free5gc/free5gc-compose.git vendor
# copy/symlink its docker-compose.yaml to ./docker-compose.yml and add a .env
```

The Makefile already parameterizes on `CORE`, so once `deploy/free5gc/docker-compose.yml` and `.env` exist:

```bash
make CORE=free5gc up
make CORE=free5gc ran-up      # same UERANSIM configs, retargeted to free5GC's AMF
```

## What stays the same
- `attacks/` — speak GTP-U/PFCP, not core internals.
- `capture/` — binds to the compose bridge; set the bridge/network name to match free5GC's.
- `deploy/ran/ueransim/` — same gNB/UE configs, point `amfConfigs.address` at free5GC's AMF.

## What changes
- Subscriber provisioning: free5GC uses its own WebConsole / Mongo schema — add a `scripts/provision_subscriber.sh` branch for `CORE=free5gc`.
- Network/bridge name in `capture/capture.sh`.
