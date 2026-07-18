"""Interval join: map capture windows to ground-truth labels.

Given per-window timestamps (from capture/extract_features.py) and a run's
labels.jsonl, assign each window a class by timestamp overlap. Anomaly events
win over benign; if several anomalies overlap a window, the one with the largest
overlap wins. Windows covered by no event fall back to the default (benign).

This is what turns a single mixed-traffic capture into a supervised, multi-class
feature table — replacing the current filename-based labeling.
"""
from __future__ import annotations
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from schema import load_labels, BENIGN   # noqa: E402


def _overlap(a0, a1, b0, b1) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def label_for_window(w_start: float, w_end: float, events, default: str = BENIGN) -> str:
    best_cls, best_ov = default, 0.0
    for e in events:
        ov = _overlap(w_start, w_end, e.start_ts, e.end_ts)
        if ov <= 0:
            continue
        # prefer anomaly over benign; among anomalies prefer larger overlap
        is_better = (
            (e.cls != BENIGN and best_cls == default)
            or (e.cls != BENIGN and ov > best_ov)
        )
        if is_better:
            best_cls, best_ov = e.cls, ov
    return best_cls


def label_windows(window_starts, window_len, events, default: str = BENIGN):
    return [label_for_window(ws, ws + window_len, events, default) for ws in window_starts]


def relabel_dataframe(df, labels_path, window_col="window_start", window_len=1.0):
    """Overwrite df['label'] using the sidecar. df must have a window-start column."""
    events = load_labels(labels_path)
    df = df.copy()
    df["label"] = label_windows(df[window_col].tolist(), window_len, events)
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--features", required=True, help="features parquet/csv (needs window_start)")
    ap.add_argument("--labels", required=True, help="labels.jsonl from a scenario run")
    ap.add_argument("--window", type=float, default=1.0, help="window length seconds")
    ap.add_argument("--out", required=True, help="output labeled features path")
    args = ap.parse_args()

    import pandas as pd
    df = pd.read_parquet(args.features) if args.features.endswith(".parquet") else pd.read_csv(args.features)
    out = relabel_dataframe(df, args.labels, window_len=args.window)
    if args.out.endswith(".parquet"):
        out.to_parquet(args.out, index=False)
    else:
        out.to_csv(args.out, index=False)
    print(f"[join] labeled {len(out)} windows -> {args.out}")
    print(f"[join] class counts:\n{out['label'].value_counts().to_string()}")


if __name__ == "__main__":
    main()
