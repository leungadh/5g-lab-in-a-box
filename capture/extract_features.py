#!/usr/bin/env python3
"""Turn N3/N4 pcaps into windowed feature rows — the interface to Idea 2.

Reads one or more pcaps, slices each into fixed time windows, and computes a
row of features per window. If the filename encodes a label
(e.g. `gtpu_flood_20260714-120000.pcap`), that label is attached — so a folder
of captures becomes a labeled dataset directly.

Usage:
    python3 extract_features.py pcaps/*.pcap -o data/features.parquet --window 1.0

Deps: pip3 install --break-system-packages scapy pandas pyarrow
Feature schema is documented in FEATURES.md.
"""
from __future__ import annotations
import argparse, glob, os, struct, sys
from collections import defaultdict

try:
    from scapy.all import PcapReader, IP, UDP
except Exception as e:  # pragma: no cover
    print(f"scapy required: {e}", file=sys.stderr); sys.exit(1)

GTPU_PORT, PFCP_PORT = 2152, 8805


def label_from_name(path: str) -> str:
    base = os.path.basename(path)
    # label is everything before the trailing _YYYYMMDD-HHMMSS timestamp
    stem = base.rsplit(".", 1)[0]
    parts = stem.split("_")
    if len(parts) >= 2 and "-" in parts[-1]:
        return "_".join(parts[:-1])
    return stem


def parse_gtpu(payload: bytes) -> dict:
    """Return quick structural facts about a GTP-U header."""
    out = {"gtpu": 1, "gtpu_malformed": 0, "teid": None, "mtype": None}
    if len(payload) < 8:
        out["gtpu_malformed"] = 1
        return out
    flags, mtype, length, teid = struct.unpack("!BBHI", payload[:8])
    out["mtype"], out["teid"] = mtype, teid
    version = (flags >> 5) & 0x7
    # crude validity checks: version must be 1; length must not exceed remainder wildly
    if version != 1 or length > len(payload):
        out["gtpu_malformed"] = 1
    if mtype not in (1, 2, 26, 31, 254, 255):  # common GTP-U types
        out["gtpu_malformed"] = 1
    return out


def parse_pfcp(payload: bytes) -> dict:
    out = {"pfcp": 1, "pfcp_mtype": None}
    if len(payload) >= 2:
        out["pfcp_mtype"] = payload[1]
    return out


def window_features(pkts: list, label: str, wstart: float) -> dict:
    n = len(pkts)
    gtpu = [p for p in pkts if p["kind"] == "gtpu"]
    pfcp = [p for p in pkts if p["kind"] == "pfcp"]
    teids = {p["teid"] for p in gtpu if p.get("teid") is not None}
    bytes_total = sum(p["len"] for p in pkts)
    iats = [pkts[i]["t"] - pkts[i-1]["t"] for i in range(1, n)]
    return {
        "window_start": round(wstart, 3),
        "n_pkts": n,
        "bytes_total": bytes_total,
        "pkt_rate": n,                         # per 1s window ~= rate
        "n_gtpu": len(gtpu),
        "n_pfcp": len(pfcp),
        "gtpu_malformed_frac": (sum(p.get("gtpu_malformed", 0) for p in gtpu) / len(gtpu)) if gtpu else 0.0,
        "teid_unique": len(teids),
        "teid_churn": len(teids) / len(gtpu) if gtpu else 0.0,
        "pfcp_est_req": sum(1 for p in pfcp if p.get("pfcp_mtype") == 50),
        "pfcp_assoc_req": sum(1 for p in pfcp if p.get("pfcp_mtype") == 5),
        "pfcp_heartbeat": sum(1 for p in pfcp if p.get("pfcp_mtype") == 1),
        "iat_mean": (sum(iats) / len(iats)) if iats else 0.0,
        "label": label,
    }


def process(paths: list, window: float) -> list:
    rows = []
    for path in paths:
        label = label_from_name(path)
        buckets: dict = defaultdict(list)
        t0 = None
        for pkt in PcapReader(path):
            if UDP not in pkt or IP not in pkt:
                continue
            udp, ip = pkt[UDP], pkt[IP]
            t = float(pkt.time)
            t0 = t if t0 is None else t0
            raw = bytes(udp.payload)
            if udp.dport == GTPU_PORT or udp.sport == GTPU_PORT:
                info = parse_gtpu(raw); info["kind"] = "gtpu"
            elif udp.dport == PFCP_PORT or udp.sport == PFCP_PORT:
                info = parse_pfcp(raw); info["kind"] = "pfcp"
            else:
                continue
            info["t"] = t; info["len"] = len(pkt)
            buckets[int((t - t0) // window)].append(info)
        for widx, pkts in sorted(buckets.items()):
            rows.append(window_features(pkts, label, t0 + widx * window))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pcaps", nargs="+", help="pcap files (globs ok)")
    ap.add_argument("-o", "--out", default="data/features.parquet")
    ap.add_argument("--window", type=float, default=1.0, help="window seconds")
    args = ap.parse_args()

    paths = []
    for p in args.pcaps:
        paths.extend(glob.glob(p))
    if not paths:
        print("no pcaps matched", file=sys.stderr); sys.exit(1)

    rows = process(paths, args.window)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    try:
        import pandas as pd
        df = pd.DataFrame(rows)
        if args.out.endswith(".parquet"):
            df.to_parquet(args.out, index=False)
        else:
            df.to_csv(args.out, index=False)
    except ImportError:
        import csv
        out = args.out.replace(".parquet", ".csv")
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
        args.out = out
    print(f"[features] {len(rows)} windows -> {args.out}")
    print(f"[features] labels: {sorted({r['label'] for r in rows})}")


if __name__ == "__main__":
    main()
