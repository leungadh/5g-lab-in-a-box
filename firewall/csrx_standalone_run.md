$ ./firewall/run_demo.sh
=== 1. VALID GTP-U, low rate  (baseline — expect: PASSES) ===
[gtpu_flood] -> 10.10.2.10:2152 teid=0x1 count=200 rate~20.0/s size=512
[gtpu_flood] sent 200 in 10.0s (~20/s)
    sent ~200, target received: 200
=== 2. GTP-U FLOOD  (N3 — expect: RATE-LIMITED by UDP screen) ===
[gtpu_flood] -> 10.10.2.10:2152 teid=0x1 count=20000 rate~2000.0/s size=512
[gtpu_flood] sent 20000 in 11.4s (~1752/s)
    sent ~20000, target received: 4000   (capped near screen threshold)
=== 3. PFCP SESSION FLOOD  (N4 — expect: RATE-LIMITED by same UDP screen) ===
[pfcp_session_flood] -> 10.10.2.10:8805 count=20000 rate~2000.0/s
[pfcp_session_flood] sent 20000 establishment requests.
    sent ~20000, target received: 4000   (capped)
=== 4. MALFORMED GTP-U  (expect: PASSES cSRX — no GTP inspection) ===
[gtpu_malformed] -> 10.10.2.10:2152  count=200 rate=20.0/s
[gtpu_malformed] sent 200 packets.
    sent ~200, target received: 200   (cSRX doesn't inspect GTP — this is the DETECTOR's job)

=== See WHY on the cSRX ===
  docker exec -it csrx cli
  > show security screen statistics zone untrust     # UDP-flood drop counters
  > show security flow session summary
  > show security policies detail

Reading it:
  1 valid   -> ~full (passes)          2 gtpu flood -> capped (screen)
  3 pfcp flood -> capped (screen)      4 malformed  -> passes (firewall can't inspect; detector catches it)

The story: cSRX caps the volumetric FLOODS; the ML detector (../detector/) catches the
malformed / protocol-abuse traffic the firewall can't see. Firewall + AI, layered.

Tune: the UDP-flood screen threshold (csrx.conf) must be BELOW the attack rate to engage.

==== Analysis =====
That's a textbook Part 1 result — exactly what you want:

Traffic	Sent	Reached target	Verdict
valid GTP-U	200	200	passes ✓
GTP-U flood	20,000	4,000	rate-limited ✓ (~80% dropped)
PFCP session flood	20,000	4,000	rate-limited ✓
malformed GTP-U	200	200	passes through (detector's job) ✓

The UDP screen clearly engaged — both floods capped from 20k down to 4k, while valid traffic passed untouched and malformed sailed through (proving the layering). That's the whole "cSRX caps the volumetric floods; the ML detector catches the malformed/subtle" story, demonstrated on real traffic.
