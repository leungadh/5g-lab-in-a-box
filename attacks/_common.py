"""Shared helpers + safety guard for the lab attack scripts.

The guard exists so these scripts cannot be casually pointed at anything that
isn't the local lab. It is intentional friction, not a real security control —
the point is to make misuse a deliberate act, not an accident.
"""
from __future__ import annotations
import argparse
import ipaddress
import sys


def assert_lab_target(target: str, acknowledged: bool) -> None:
    """Refuse to proceed unless target is loopback/private AND the operator
    has explicitly acknowledged they own the lab."""
    try:
        ip = ipaddress.ip_address(target)
    except ValueError:
        print(f"[guard] '{target}' is not a bare IP. Use a lab IP (e.g. 127.0.0.1).", file=sys.stderr)
        sys.exit(2)

    if not (ip.is_loopback or ip.is_private):
        print(f"[guard] refusing: {target} is not loopback/RFC-1918. This tool is lab-only.", file=sys.stderr)
        sys.exit(2)

    if not acknowledged:
        print("[guard] refusing: pass --i-own-this-lab to confirm this is your own lab core.", file=sys.stderr)
        sys.exit(2)


def base_parser(description: str, default_port: int) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--target", default="127.0.0.1", help="lab core IP (default 127.0.0.1)")
    p.add_argument("--port", type=int, default=default_port)
    p.add_argument("--count", type=int, default=100, help="packets/sessions to send")
    p.add_argument("--rate", type=float, default=50.0, help="approx packets/sec")
    p.add_argument("--i-own-this-lab", action="store_true", dest="ack",
                   help="required acknowledgement that target is your own lab")
    return p
