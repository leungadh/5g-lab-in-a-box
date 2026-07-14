#!/usr/bin/env python3
"""Baseline GTP/PFCP anomaly detector — Phase 5 (Idea 2 handoff).

Semi-supervised: train on benign windows, score every window, flag anomalies.
Runs on the labeled features from ../capture/extract_features.py, or on a
synthetic set (--synth) so you can validate the pipeline before real captures.

Examples:
    # generate synthetic data and evaluate IsolationForest
    python3 baseline.py --synth --model isoforest

    # run on real captured features
    python3 baseline.py --data ../capture/data/features.parquet --model isoforest

    # both models (autoencoder needs torch)
    python3 baseline.py --synth --model both
"""
from __future__ import annotations
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import data as D          # noqa: E402
import models as M        # noqa: E402
import metrics as MET     # noqa: E402


def split_benign_train(df, test_frac=0.4, seed=7):
    """Train on a benign-only slice; test on a held-out mix of benign + attacks."""
    from sklearn.model_selection import train_test_split
    benign = df[df["label"] == D.BENIGN]
    attacks = df[df["label"] != D.BENIGN]
    b_train, b_test = train_test_split(benign, test_size=test_frac, random_state=seed)
    test = __import__("pandas").concat([b_test, attacks], ignore_index=True)
    return b_train, test


def run_model(name, b_train, test, contamination, out_dir=None):
    det = M.get_detector(name, contamination=contamination)
    Xtr, _, _ = D.make_xy(b_train)
    det.fit(Xtr)

    Xte, yte, labte = D.make_xy(test)
    scores = det.score(Xte)

    benign_scores = scores[labte == D.BENIGN]
    thr = MET.choose_threshold(benign_scores, quantile=1 - contamination)
    res = MET.evaluate(scores, yte, labte, thr)
    report = MET.format_report(name, res)
    print(report + "\n")

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        import pandas as pd
        scored = test.copy()
        scored["anomaly_score"] = scores
        scored["flagged"] = (scores >= thr).astype(int)
        scored.to_csv(os.path.join(out_dir, f"scored_{name}.csv"), index=False)
        with open(os.path.join(out_dir, f"report_{name}.txt"), "w") as f:
            f.write(report + "\n")
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--data", help="path to features.parquet/.csv")
    src.add_argument("--synth", action="store_true", help="use synthetic data")
    ap.add_argument("--model", default="isoforest",
                    choices=["isoforest", "autoencoder", "both"])
    ap.add_argument("--contamination", type=float, default=0.05,
                    help="expected anomaly fraction / benign quantile for threshold")
    ap.add_argument("--out", default=os.path.join(HERE, "out"),
                    help="dir for scored rows + report (set '' to skip)")
    ap.add_argument("--synth-n", type=int, default=400, help="rows per class for --synth")
    args = ap.parse_args()

    if args.synth:
        synth_path = os.path.join(HERE, "out", "synthetic_features.parquet")
        path, df = D.write_synth(synth_path, n_per_class=args.synth_n)
        print(f"[synth] wrote {len(df)} rows -> {path}")
    else:
        df = D.load_features(args.data)
        print(f"[data] loaded {len(df)} rows from {args.data}")

    labels = sorted(df["label"].unique())
    print(f"[data] labels: {labels}")
    if D.BENIGN not in labels:
        sys.exit("need benign windows to train a semi-supervised baseline.")

    b_train, test = split_benign_train(df)
    print(f"[split] train(benign)={len(b_train)}  test={len(test)}\n")

    out_dir = args.out or None
    models = ["isoforest", "autoencoder"] if args.model == "both" else [args.model]
    results = {}
    for name in models:
        if name == "autoencoder" and not M.AutoencoderDetector.available():
            print("[skip] autoencoder: PyTorch not installed (pip install torch)\n")
            continue
        results[name] = run_model(name, b_train, test, args.contamination, out_dir)

    # exit non-zero if the best model didn't clearly beat random — useful in CI
    if results:
        best_auc = max(r["roc_auc"] for r in results.values())
        print(f"[done] best ROC-AUC = {best_auc:.3f}")
        if best_auc < 0.75:
            sys.exit(f"baseline underperformed (ROC-AUC {best_auc:.3f} < 0.75)")


if __name__ == "__main__":
    main()
