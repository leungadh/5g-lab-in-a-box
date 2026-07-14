#!/usr/bin/env python3
"""N3 malformed GTP-U generator (label: gtpu_malformed).

Emits GTP-U packets that violate TS 29.281 in ways a decoder/firewall should
catch: unknown message types, reserved/version bits set wrong, TEIDs that map
to no session, and truncated/oversized extension-header chains.

Lab-only. See ../_common.py.
"""
import os, sys, time, random, struct, socket
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _common import base_parser, assert_lab_target  # noqa: E402

GTPU_PORT = 2152


def craft_malformed(kind: int) -> bytes:
    """Return raw bytes of a deliberately malformed GTP-U header + payload.

    GTP-U header (TS 29.281): flags(1) type(1) length(2) TEID(4) [seq/ext...].
    """
    teid = random.randint(0, 0xFFFFFFFF)
    if kind == 0:
        # Unknown/invalid message type (0xF7 is not a defined GTP-U type)
        flags = 0x30  # version=1, PT=1
        mtype = 0xF7
        payload = b"\x00" * 8
        return struct.pack("!BBHI", flags, mtype, len(payload), teid) + payload
    if kind == 1:
        # Reserved/version bits wrong (version=0 is GTPv0, illegal on N3)
        flags = 0x00
        mtype = 0xFF  # G-PDU is 0xFF but with bad flags it's malformed
        payload = b"\xde\xad\xbe\xef"
        return struct.pack("!BBHI", flags, mtype, len(payload), teid) + payload
    if kind == 2:
        # Extension-header flag set but chain truncated (claims ext, none follows)
        flags = 0x34  # E-bit set
        mtype = 0xFF
        payload = b""  # missing seq(2)+npdu(1)+ext(1) that E-bit promises
        return struct.pack("!BBHI", flags, mtype, 4, teid) + payload
    # kind == 3: length field lies (claims huge length, short body)
    flags = 0x30
    mtype = 0xFF
    payload = b"\x41" * 4
    return struct.pack("!BBHI", flags, mtype, 0xFFFF, teid) + payload


def main() -> None:
    args = base_parser(__doc__, GTPU_PORT).parse_args()
    assert_lab_target(args.target, args.ack)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    interval = 1.0 / args.rate if args.rate > 0 else 0
    print(f"[gtpu_malformed] -> {args.target}:{args.port}  count={args.count} rate={args.rate}/s")
    for i in range(args.count):
        pkt = craft_malformed(i % 4)
        sock.sendto(pkt, (args.target, args.port))
        if interval:
            time.sleep(interval)
    print(f"[gtpu_malformed] sent {args.count} packets.")


if __name__ == "__main__":
    main()
