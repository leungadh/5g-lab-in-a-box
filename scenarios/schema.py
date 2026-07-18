"""Ground-truth label schema for the traffic-scenario generator.

Two artifacts per run (the "sidecar"):
  - labels.jsonl  : one LabelEvent per line — a timestamp range tagged with a class.
  - manifest.json : run-level provenance (core, seed, versions, git SHA, scenario).

Because the generator knows exactly what it ran and when, the emitted dataset is
supervised by construction. Downstream, join.py maps packet-capture windows to
these events by timestamp overlap.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
import json
import os
import subprocess
import time

# Ground-truth classes. "benign" is the default when no anomaly interval covers a window.
BENIGN = "benign"
CLASSES = [
    BENIGN,
    "gtpu_malformed", "gtpu_flood",
    "pfcp_session_flood", "pfcp_assoc_abuse",
    "signaling_storm",
]


@dataclass
class LabelEvent:
    start_ts: float          # epoch seconds (inclusive)
    end_ts: float            # epoch seconds (exclusive)
    cls: str                 # ground-truth class (see CLASSES)
    event: str               # human name, e.g. "pdu_establish", "gtpu_flood"
    interface: str           # N1/N2/N3/N4
    scenario_id: str
    params: dict = field(default_factory=dict)

    def validate(self) -> None:
        if self.cls not in CLASSES:
            raise ValueError(f"unknown class '{self.cls}' (allowed: {CLASSES})")
        if self.end_ts < self.start_ts:
            raise ValueError(f"event '{self.event}' has end_ts < start_ts")


@dataclass
class RunManifest:
    run_id: str
    created: str
    core: str                # open5gs | free5gc
    seed: int
    git_sha: str
    scenario: str
    n_events: int
    label_file: str
    tool_versions: dict = field(default_factory=dict)


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def write_labels(path: str, events: list) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        for e in events:
            e.validate()
            f.write(json.dumps(asdict(e)) + "\n")


def load_labels(path: str) -> list:
    events = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(LabelEvent(**json.loads(line)))
    return events


def write_manifest(path: str, manifest: RunManifest) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(asdict(manifest), f, indent=2)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
