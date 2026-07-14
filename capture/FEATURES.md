# Feature schema (interface to Idea 2)

`extract_features.py` emits one row per time window (default 1s). This schema is the contract the anomaly detector trains against — freeze it before large captures.

| Column | Type | Meaning |
|---|---|---|
| `window_start` | float | epoch seconds at window start |
| `n_pkts` | int | packets in window |
| `bytes_total` | int | total bytes in window |
| `pkt_rate` | int | packets/window (≈ pkt/s at 1s windows) |
| `n_gtpu` | int | GTP-U packets (N3) |
| `n_pfcp` | int | PFCP packets (N4) |
| `gtpu_malformed_frac` | float | fraction of GTP-U packets failing structural checks |
| `teid_unique` | int | distinct TEIDs seen |
| `teid_churn` | float | unique TEIDs / GTP-U packets (high = scanning/rotation) |
| `pfcp_est_req` | int | PFCP Session Establishment Requests (type 50) |
| `pfcp_assoc_req` | int | PFCP Association Setup Requests (type 5) |
| `pfcp_heartbeat` | int | PFCP Heartbeat messages (type 1) |
| `iat_mean` | float | mean inter-arrival time in window |
| `label` | str | `benign` or attack class, from pcap filename |

## Label set
`benign`, `gtpu_malformed`, `gtpu_flood`, `pfcp_session_flood`, `pfcp_assoc_abuse`, `signaling_storm`.

## Notes for modeling (Idea 2)
- Start with per-window tabular models (IsolationForest, then a small autoencoder) as a CPU sanity check.
- For signaling storms and session abuse, per-window loses temporal structure — a sequence model over consecutive windows (or a graph over TEID/session relationships) is where the DGX Spark earns its keep.
- Keep benign captures under varied realistic UE load so the model doesn't just learn "traffic = attack."
