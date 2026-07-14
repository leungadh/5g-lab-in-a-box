"""Evaluation for the baseline detector.

Primary metric is ROC-AUC (threshold-free) on the continuous anomaly score.
We also pick an operating threshold from the benign score distribution and
report precision / recall / F1 at that point, plus per-attack-class recall so
you can see which techniques the baseline catches and which it misses.
"""
from __future__ import annotations
import numpy as np
from sklearn.metrics import roc_auc_score, precision_recall_fscore_support


def choose_threshold(benign_scores: np.ndarray, quantile: float = 0.99) -> float:
    """Operating point: flag anything above the given quantile of benign scores."""
    return float(np.quantile(benign_scores, quantile))


def evaluate(scores, y_true, labels, threshold):
    y_pred = (scores >= threshold).astype(int)
    try:
        auc = roc_auc_score(y_true, scores)
    except ValueError:
        auc = float("nan")
    p, r, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )

    per_class = {}
    labels = np.asarray(labels)
    for cls in sorted(set(labels)):
        mask = labels == cls
        if cls == "benign":
            # for benign, "recall" of the negative class = specificity
            per_class[cls] = {
                "n": int(mask.sum()),
                "flagged_rate": float(y_pred[mask].mean()) if mask.any() else float("nan"),
            }
        else:
            per_class[cls] = {
                "n": int(mask.sum()),
                "recall": float(y_pred[mask].mean()) if mask.any() else float("nan"),
            }
    return {
        "roc_auc": auc,
        "threshold": threshold,
        "precision": p,
        "recall": r,
        "f1": f1,
        "per_class": per_class,
    }


def format_report(model_name: str, res: dict) -> str:
    lines = []
    lines.append(f"=== baseline detector: {model_name} ===")
    lines.append(f"ROC-AUC ............ {res['roc_auc']:.3f}   (1.0 = perfect, 0.5 = random)")
    lines.append(f"operating threshold  {res['threshold']:.4f}  (99th pct of benign score)")
    lines.append(f"precision .......... {res['precision']:.3f}")
    lines.append(f"recall (all attacks) {res['recall']:.3f}")
    lines.append(f"F1 ................. {res['f1']:.3f}")
    lines.append("")
    lines.append("per-class:")
    for cls, d in res["per_class"].items():
        if "recall" in d:
            lines.append(f"  {cls:<20} recall={d['recall']:.3f}  (n={d['n']})")
        else:
            lines.append(f"  {cls:<20} false-alarm={d['flagged_rate']:.3f}  (n={d['n']})")
    return "\n".join(lines)
