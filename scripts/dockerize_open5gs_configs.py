#!/usr/bin/env python3
"""Rewrite source-built Open5GS sample configs for the per-container Docker network.

The sample configs (from a source build / `make configs` against a from-source image)
use 127.0.0.x loopback addressing meant for an all-in-one host install — which breaks
across separate containers (each container's 127.0.0.x is its own). This rewrites them:

  - SBI/PFCP/GTPU/NGAP servers   -> bind 0.0.0.0
  - SBI servers                  -> advertise the NF's service name (so NF discovery works)
  - SBI clients (nrf / scp)      -> point at the 'nrf' / 'scp' service names
  - PFCP clients (upf / smf)     -> point at the 'upf' / 'smf' service names

Service names must match the docker-compose service names (nrf, scp, amf, smf, upf, ...),
which they do in this repo. Needs: pip install pyyaml.

Usage:  python3 scripts/dockerize_open5gs_configs.py deploy/open5gs/configs
"""
import sys, glob, os, yaml

cfgdir = sys.argv[1] if len(sys.argv) > 1 else "deploy/open5gs/configs"

def fix_server(sect, advertise=None):
    srv = sect.get("server")
    if isinstance(srv, list):
        for e in srv:
            if isinstance(e, dict) and "address" in e:
                e["address"] = "0.0.0.0"
                if advertise:
                    e["advertise"] = advertise

def fix_client(sect, key, host):
    cl = sect.get("client")
    if isinstance(cl, dict) and isinstance(cl.get(key), list):
        for e in cl[key]:
            if isinstance(e, dict):
                if "uri" in e:
                    e["uri"] = f"http://{host}:7777"
                if "address" in e:
                    e["address"] = host

for path in sorted(glob.glob(os.path.join(cfgdir, "*.yaml"))):
    nf = os.path.basename(path).rsplit(".", 1)[0]        # nrf, amf, smf, upf, scp ...
    try:
        with open(path) as f:
            doc = yaml.safe_load(f)
    except Exception as e:
        print("skip", path, e)
        continue
    if not isinstance(doc, dict):
        continue
    touched = False
    for _, body in doc.items():
        if not isinstance(body, dict):
            continue
        if isinstance(body.get("sbi"), dict):
            fix_server(body["sbi"], advertise=nf)
            fix_client(body["sbi"], "nrf", "nrf")
            fix_client(body["sbi"], "scp", "scp")
            touched = True
        if isinstance(body.get("pfcp"), dict):
            fix_server(body["pfcp"])
            fix_client(body["pfcp"], "upf", "upf")
            fix_client(body["pfcp"], "smf", "smf")
            touched = True
        if isinstance(body.get("gtpu"), dict):
            fix_server(body["gtpu"])
            touched = True
        if isinstance(body.get("ngap"), dict):
            fix_server(body["ngap"])
            touched = True
        if isinstance(body.get("metrics"), dict):
            fix_server(body["metrics"])
    if touched:
        with open(path, "w") as f:
            yaml.safe_dump(doc, f, default_flow_style=False, sort_keys=False)
        print("dockerized", os.path.basename(path))
