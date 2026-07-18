#!/usr/bin/env python3
"""Scenario runner / timeline orchestrator.

Plays a scenario's Steps in order, records the exact [start, end) wall-clock
window each Step occupies, and writes the sidecar (labels.jsonl + manifest.json).
Run capture in parallel on the same host so packet timestamps share this clock;
join.py then maps capture windows to these labels.

Modes:
  --dry-run   don't touch the core — simulate timing and emit the sidecar only.
              Use this to validate the label pipeline before the lab is live.
  (default)   execute each Step: benign -> nr-cli command; anomaly -> attacks/ script.

Examples:
  python3 runner.py --list
  python3 runner.py --scenario benign_baseline --dry-run
  python3 runner.py --scenario gtpu_malformed_mixed --core open5gs
"""
from __future__ import annotations
import argparse
import os
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import schema as S       # noqa: E402
import library as L      # noqa: E402


def tool_versions() -> dict:
    def ver(cmd):
        try:
            return subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().splitlines()[0].strip()
        except Exception:
            return "n/a"
    return {
        "python": sys.version.split()[0],
        "docker": ver(["docker", "--version"]),
    }


def execute_step(step: "L.Step", ue: str, dry_run: bool) -> None:
    """Perform the step's side effect (or simulate it in dry-run)."""
    if dry_run:
        # keep the timeline quick but proportional-ish for testing
        time.sleep(min(step.duration_s, 0.05))
        return

    if step.kind == "anomaly" and step.attack:
        cmd = ["python3", os.path.join(ROOT, "attacks", step.attack), *step.attack_args]
        subprocess.run(cmd, check=False)
    elif step.nr_cli:
        # drive UERANSIM UE; nr-cli target is the UE's IMSI node name
        cmd = ["nr-cli", ue, "--exec", step.nr_cli]
        subprocess.run(cmd, check=False)
        time.sleep(step.duration_s)
    else:
        # passive benign window (e.g. UE just registered, or carrying idle traffic)
        time.sleep(step.duration_s)


def run(scenario_id: str, core: str, ue: str, seed: int, out_dir: str, dry_run: bool):
    scenario = L.get(scenario_id)
    run_id = f"{scenario_id}-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    run_out = os.path.join(out_dir, run_id)

    events = []
    print(f"[run] scenario={scenario_id} core={core} dry_run={dry_run}")
    print(f"[run] {scenario.description}")
    for step in scenario.steps:
        start = time.time()
        print(f"  → {step.name:<16} [{step.cls}/{step.interface}] ~{step.duration_s}s")
        execute_step(step, ue, dry_run)
        end = time.time()
        events.append(S.LabelEvent(
            start_ts=round(start, 3), end_ts=round(end, 3),
            cls=step.cls, event=step.name, interface=step.interface,
            scenario_id=scenario_id, params=step.params,
        ))

    labels_path = os.path.join(run_out, "labels.jsonl")
    S.write_labels(labels_path, events)
    manifest = S.RunManifest(
        run_id=run_id, created=S.now_iso(), core=core, seed=seed,
        git_sha=S.git_sha(), scenario=scenario_id, n_events=len(events),
        label_file="labels.jsonl", tool_versions=tool_versions(),
    )
    S.write_manifest(os.path.join(run_out, "manifest.json"), manifest)

    n_anom = sum(1 for e in events if e.cls != S.BENIGN)
    print(f"[run] wrote {len(events)} events ({n_anom} anomaly) -> {run_out}")
    return run_out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", help="scenario id (see --list)")
    ap.add_argument("--list", action="store_true", help="list scenarios and exit")
    ap.add_argument("--core", default="open5gs", choices=["open5gs", "free5gc"])
    ap.add_argument("--ue", default="imsi-999700000000001", help="UERANSIM UE node for nr-cli")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--dry-run", action="store_true", help="emit sidecar without touching the core")
    args = ap.parse_args()

    if args.list:
        for sid, sc in L.SCENARIOS.items():
            kinds = {s.kind for s in sc.steps}
            print(f"  {sid:<24} {sc.description}  [{'+'.join(sorted(kinds))}]")
        return
    if not args.scenario:
        ap.error("need --scenario (or --list)")

    run(args.scenario, args.core, args.ue, args.seed, args.out, args.dry_run)


if __name__ == "__main__":
    main()
