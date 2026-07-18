"""Declarative scenario library.

A Scenario is an ordered list of Steps. Each Step either drives a benign
control-plane flow (via UERANSIM nr-cli) or injects an anomaly (via an attacks/
script). Steps carry the ground-truth class + interface so the runner can emit a
correct label event for the window of time each Step occupies.

This is a skeleton: two scenarios are wired (one benign, one mixed). Add more by
appending to SCENARIOS. Keep timings and seeds fixed for reproducibility.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from schema import BENIGN


@dataclass
class Step:
    name: str                 # e.g. "register", "gtpu_flood"
    cls: str                  # ground-truth class for this step's traffic
    interface: str            # N1/N2/N3/N4
    duration_s: float         # nominal wall-clock duration
    kind: str = "benign"      # "benign" | "anomaly"
    # How to execute (the runner turns these into subprocess calls; see runner.py):
    #   benign  -> nr-cli command string, run against the named UE/gNB
    #   anomaly -> path under attacks/ plus arg list
    nr_cli: str = ""
    attack: str = ""
    attack_args: list = field(default_factory=list)
    params: dict = field(default_factory=dict)


@dataclass
class Scenario:
    id: str
    description: str
    steps: list


# --- Benign building blocks (UERANSIM nr-cli) -------------------------------
def benign_session_cycle():
    return [
        Step("register",      BENIGN, "N1", 3.0, nr_cli="",                params={"note": "UE start = initial registration"}),
        Step("pdu_establish", BENIGN, "N3", 3.0, nr_cli="ps-establish IPv4 --sst 1 --dnn internet"),
        Step("data_idle",     BENIGN, "N3", 8.0, nr_cli="",                params={"note": "carry light user traffic"}),
        Step("pdu_release",   BENIGN, "N4", 2.0, nr_cli="ps-release-all"),
        Step("deregister",    BENIGN, "N1", 2.0, nr_cli="deregister normal"),
    ]


# --- Scenarios --------------------------------------------------------------
SCENARIOS = {
    "benign_baseline": Scenario(
        id="benign_baseline",
        description="Clean control-plane cycle: register -> PDU establish -> idle -> release -> deregister.",
        steps=benign_session_cycle(),
    ),

    "gtpu_malformed_mixed": Scenario(
        id="gtpu_malformed_mixed",
        description="Benign session with a malformed GTP-U burst injected mid-session on N3.",
        steps=[
            Step("register",      BENIGN, "N1", 3.0),
            Step("pdu_establish", BENIGN, "N3", 3.0, nr_cli="ps-establish IPv4 --sst 1 --dnn internet"),
            Step("data_idle",     BENIGN, "N3", 5.0),
            Step("gtpu_malformed", "gtpu_malformed", "N3", 6.0, kind="anomaly",
                 attack="gtpu/malformed_gtpu.py",
                 attack_args=["--target", "127.0.0.1", "--i-own-this-lab", "--count", "2000", "--rate", "60"]),
            Step("data_idle2",    BENIGN, "N3", 5.0),
            Step("pdu_release",   BENIGN, "N4", 2.0, nr_cli="ps-release-all"),
            Step("deregister",    BENIGN, "N1", 2.0, nr_cli="deregister normal"),
        ],
    ),
}


def get(scenario_id: str) -> Scenario:
    if scenario_id not in SCENARIOS:
        raise KeyError(f"unknown scenario '{scenario_id}' (have: {list(SCENARIOS)})")
    return SCENARIOS[scenario_id]
