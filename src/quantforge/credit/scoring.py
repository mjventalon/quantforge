"""Credit scorecard tooling: discrimination metrics, WoE/IV binning, points scaling."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

__all__ = [
    "ClassificationReport",
    "roc_curve",
    "auc_score",
    "ks_statistic",
    "classification_report",
    "woe_iv",
    "scorecard_points",
    "calibration_table",
]


def roc_curve(y_true: np.ndarray, scores: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """False-positive rate, true-positive rate and thresholds (descending score)."""
    y = np.asarray(y_true, dtype=float)
    s = np.asarray(scores, dtype=float)
    order = np.argsort(-s, kind="mergesort")
    y, s = y[order], s[order]
    distinct = np.r_[np.where(np.diff(s))[0], y.size - 1]
    tps = np.cumsum(y)[distinct]
    fps = (distinct + 1) - tps
    tpr = np.r_[0, tps / max(y.sum(), 1)]
    fpr = np.r_[0, fps / max((1 - y).sum(), 1)]
    return fpr, tpr, np.r_[np.inf, s[distinct]]


def auc_score(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Area under the ROC curve (Mann-Whitney, handles ties)."""
    y = np.asarray(y_true, dtype=int)
    ranks = stats.rankdata(scores)
    n1, n0 = y.sum(), (1 - y).sum()
    if n1 == 0 or n0 == 0:
        raise ValueError("need both classes")
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def ks_statistic(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Kolmogorov-Smirnov separation between the score distributions of the two classes."""
    fpr, tpr, _ = roc_curve(y_true, scores)
    return float(np.max(tpr - fpr))


@dataclass(frozen=True)
class ClassificationReport:
    auc: float
    gini: float
    ks: float
    brier: float
    log_loss: float
    accuracy: float
    precision: float
    recall: float
    f1: float
    threshold: float
    confusion: pd.DataFrame


def classification_report(y_true: np.ndarray, proba: np.ndarray,
                          threshold: float = 0.5) -> ClassificationReport:
    y = np.asarray(y_true, dtype=int)
    p = np.clip(np.asarray(proba, dtype=float), 1e-15, 1 - 1e-15)
    pred = (p >= threshold).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    auc = auc_score(y, p)
    return ClassificationReport(
        auc=auc, gini=2 * auc - 1, ks=ks_statistic(y, p),
        brier=float(np.mean((p - y) ** 2)),
        log_loss=float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))),
        accuracy=(tp + tn) / y.size, precision=prec, recall=rec,
        f1=2 * prec * rec / (prec + rec) if prec + rec else 0.0, threshold=threshold,
        confusion=pd.DataFrame([[tn, fp], [fn, tp]], index=["actual 0", "actual 1"],
                               columns=["pred 0", "pred 1"]),
    )


def woe_iv(feature: pd.Series, target: pd.Series, bins: int = 10) -> tuple[pd.DataFrame, float]:
    """Weight of Evidence table and Information Value for one predictor.

    Numeric features are cut into quantile bins; categoricals are used as is.
    WoE = ln(%good / %bad), with 0.5 added to empty cells.
    IV rule of thumb: <0.02 useless, 0.02-0.1 weak, 0.1-0.3 medium, >0.3 strong.
    """
    df = pd.DataFrame({"x": feature, "y": target}).dropna()
    if pd.api.types.is_numeric_dtype(df["x"]) and df["x"].nunique() > bins:
        df["bin"] = pd.qcut(df["x"], bins, duplicates="drop")
    else:
        df["bin"] = df["x"].astype(str)
    g = df.groupby("bin", observed=True)["y"].agg(["count", "sum"])
    g.columns = ["n", "bad"]
    g["good"] = g["n"] - g["bad"]
    tot_good, tot_bad = g["good"].sum(), g["bad"].sum()
    dist_good = (g["good"] + 0.5) / (tot_good + 0.5 * len(g))
    dist_bad = (g["bad"] + 0.5) / (tot_bad + 0.5 * len(g))
    g["bad_rate"] = g["bad"] / g["n"]
    g["woe"] = np.log(dist_good / dist_bad)
    g["iv"] = (dist_good - dist_bad) * g["woe"]
    return g, float(g["iv"].sum())


def scorecard_points(log_odds_good: np.ndarray, base_score: float = 600, base_odds: float = 50,
                     pdo: float = 20) -> np.ndarray:
    """Convert log-odds of being *good* into scorecard points.

    ``base_score`` points correspond to good:bad odds of ``base_odds``; every
    ``pdo`` points doubles the odds (industry-standard scaling).
    """
    factor = pdo / np.log(2)
    offset = base_score - factor * np.log(base_odds)
    return offset + factor * np.asarray(log_odds_good, dtype=float)


def calibration_table(y_true: np.ndarray, proba: np.ndarray, n_bins: int = 10) -> pd.DataFrame:
    """Predicted vs observed default rate by PD decile, with a binomial test per bucket."""
    df = pd.DataFrame({"y": np.asarray(y_true), "p": np.asarray(proba)})
    df["bucket"] = pd.qcut(df["p"].rank(method="first"), n_bins, labels=False) + 1
    g = df.groupby("bucket").agg(n=("y", "size"), defaults=("y", "sum"),
                                 predicted_pd=("p", "mean"))
    g["observed_dr"] = g["defaults"] / g["n"]
    g["binom_pvalue"] = [
        float(stats.binomtest(int(d), int(n), float(p)).pvalue)
        for d, n, p in zip(g["defaults"], g["n"], g["predicted_pd"])
    ]
    return g
