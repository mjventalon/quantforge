"""Pairs trading on a z-scored spread with a rolling (past-only) hedge ratio.

Spread (log prices): ``s_t = ln y_t − β_t ln x_t`` with ``β_t`` estimated on the
previous ``window`` days; the z-score compares ``s_t`` with the mean and standard
deviation of the same spread (same β) over that past window. Rules, decided at each close:

* z > +entry → short the spread (short y, long β·x)
* z < −entry → long the spread
* |z| < exit → close

Daily P&L of one unit of spread ≈ ``r_y − β r_x``; gross exposure is
normalized to 1 so returns are comparable to a fully invested asset.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..portfolio.capm import performance_summary

__all__ = ["PairsResult", "pairs_backtest"]


@dataclass
class PairsResult:
    returns: pd.Series
    zscore: pd.Series
    position: pd.Series
    hedge_ratio: pd.Series
    spread: pd.Series
    metrics: pd.DataFrame


def pairs_backtest(y: pd.Series, x: pd.Series, window: int = 120, entry: float = 2.0,
                   exit: float = 0.5, cost_bps: float = 5.0,
                   risk_free_rate: float = 0.0) -> PairsResult:
    if exit >= entry:
        raise ValueError("exit threshold must be below entry threshold")
    df = pd.concat([y.rename("y"), x.rename("x")], axis=1, join="inner").dropna()
    ly, lx = np.log(df["y"]), np.log(df["x"])
    # All window statistics use data up to yesterday only.
    my, mx = ly.rolling(window).mean().shift(1), lx.rolling(window).mean().shift(1)
    vy, vx = ly.rolling(window).var().shift(1), lx.rolling(window).var().shift(1)
    cxy = ly.rolling(window).cov(lx).shift(1)
    beta = cxy / vx
    # Spread with today's hedge ratio applied consistently to the whole window
    spread = ly - beta * lx
    s_mean = my - beta * mx
    s_std = np.sqrt((vy + beta**2 * vx - 2 * beta * cxy).clip(lower=1e-12))
    z = ((spread - s_mean) / s_std).rename("z")

    pos = np.zeros(len(df))
    cur = 0.0
    zv = z.to_numpy()
    for i, val in enumerate(zv):
        if np.isnan(val):
            cur = 0.0
        elif cur == 0 and val > entry:
            cur = -1.0
        elif cur == 0 and val < -entry:
            cur = 1.0
        elif cur != 0 and abs(val) < exit:
            cur = 0.0
        pos[i] = cur
    position = pd.Series(pos, index=df.index, name="position")

    ry, rx = df["y"].pct_change(), df["x"].pct_change()
    b = beta.ffill()
    held = position.shift(1).fillna(0.0)
    held_beta = b.shift(1)
    pnl = held * (ry - held_beta * rx) / (1 + held_beta.abs())
    turnover = position.diff().abs().fillna(0.0)
    pnl = (pnl.fillna(0.0) - turnover * cost_bps / 1e4 * 2).rename("pairs")
    metrics = performance_summary(pnl.iloc[window + 1:].to_frame("Pairs strategy"),
                                  risk_free_rate)
    metrics.loc["Trades"] = float((turnover > 0).sum())
    metrics.loc["Time in market"] = float((held != 0).mean())
    return PairsResult(returns=pnl, zscore=z, position=position,
                       hedge_ratio=beta.rename("hedge_ratio"), spread=spread.rename("spread"),
                       metrics=metrics)
