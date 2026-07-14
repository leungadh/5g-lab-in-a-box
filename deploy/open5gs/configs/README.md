# Open5GS NF configs

One YAML per network function, mounted read-only into each container by `docker-compose.yml`.

## How to populate

The fastest reliable path is to start from the upstream defaults and adjust:

```bash
# Pull the reference configs shipped in the image, then edit in place.
docker run --rm gradiant/open5gs:2.7.5 tar -C /opt/open5gs/etc/open5gs -c . | tar -x -C .
```

Then edit these keys to match `../../../.env`:

- **nrf.yaml / all NFs** — `sbi` addresses so NFs find the NRF on the `core` bridge (use service DNS names: `nrf`, `scp`, `amf`, ...).
- **amf.yaml** — `plmn_id` (MCC/MNC), `tac`, `s_nssai` (SST/SD), and the `ngap` bind address (`0.0.0.0` so the gNB can reach it).
- **smf.yaml** — `session` subnet = `UE_SUBNET`, DNS, and the PFCP peer (`upf`).
- **upf.yaml** — `pfcp` bind, `gtpu` bind (`0.0.0.0` for N3), and `subnet` matching the SMF session pool.

`nf.yaml` files not listed above (ausf, udm, udr, pcf, bsf, nssf, scp) usually only need their SBI/NRF addresses pointed at the `core` network service names.

## Files expected here
`nrf.yaml  scp.yaml  amf.yaml  ausf.yaml  udm.yaml  udr.yaml  pcf.yaml  bsf.yaml  nssf.yaml  smf.yaml  upf.yaml`

Placeholder `.yaml.example` files are provided as a checklist — replace them with real configs before `make up`.
