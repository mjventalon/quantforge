r"""Long-horizon wealth projection by block bootstrap of *real historical* returns.

Instead of assuming normal returns, each simulated future is stitched together
from randomly chosen blocks of consecutive historical months. Blocks keep the
fat tails, crashes and autocorrelation that actually happened.

References
----------
Politis, D. & Romano, J. (1994). The Stationary Bootstrap. *JASA*, 89(428).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = ["WealthSimulation", "simulate_wealth", "monthly_portfolio_returns"]


@dataclass
class WealthSimulation:
    paths: np.ndarray              # (n_sims, n_months + 1) wealth
    contributions: np.ndarray      # cumulative money put in, per month
    percentiles: pd.DataFrame      # by month: p5, p25, p50, p75, p95
    final: np.ndarray
    max_drawdowns: np.ndarray
    goal: float | None
    real: bool

    @property
    def prob_goal(self) -> float | None:
        return None if self.goal is None else float((self.final >= self.goal).mean())

    def summary(self) -> dict[str, float]:
        f = self.final
        out = {"median_final": float(np.median(f)), "p5_final": float(np.percentile(f, 5)),
               "p95_final": float(np.percentile(f, 95)), "mean_final": float(f.mean()),
               "total_contributed": float(self.contributions[-1]),
               "prob_loss_vs_contributed": float((f < self.contributions[-1]).mean()),
               "median_max_drawdown": float(np.median(self.max_drawdowns))}
        if self.goal is not None:
            out["prob_goal"] = self.prob_goal
        return out


def monthly_portfolio_returns(prices: pd.DataFrame, weights: pd.Series | dict) -> pd.Series:
    """Monthly returns of a portfolio rebalanced to ``weights`` every month."""
    w = pd.Series(weights, dtype=float)
    w = w / w.sum()
    m = prices[w.index].resample("ME").last().pct_change().dropna()
    return (m @ w).rename("portfolio")


def simulate_wealth(
    monthly_returns: pd.Series | np.ndarray,
    initial: float = 10_000.0,
    monthly_contribution: float = 0.0,
    years: int = 20,
    n_sims: int = 10_000,
    block_months: int = 12,
    annual_inflation: float | None = None,
    annual_fee: float = 0.0,
    goal: float | None = None,
    seed: int | None = None,
) -> WealthSimulation:
    """Project wealth with contributions, fees and optional inflation adjustment.

    Parameters
    ----------
    monthly_returns
        Historical monthly portfolio returns (real data, e.g. from
        :func:`monthly_portfolio_returns`).
    block_months
        Length of the resampled blocks (12 keeps one-year regimes together).
    annual_inflation
        If given, results are in today's money (real terms).
    annual_fee
        Yearly fee (expense ratio / advisory), deducted monthly.
    """
    r = np.asarray(monthly_returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size < max(24, block_months * 2):
        raise ValueError("need at least 24 months of history (and two blocks)")
    rng = np.random.default_rng(seed)
    n_months = int(years * 12)
    n_blocks = int(np.ceil(n_months / block_months))
    starts = rng.integers(0, r.size - block_months + 1, size=(n_sims, n_blocks))
    idx = (starts[:, :, None] + np.arange(block_months)).reshape(n_sims, -1)[:, :n_months]
    sim_r = r[idx] - annual_fee / 12
    if annual_inflation is not None:
        sim_r = (1 + sim_r) / (1 + annual_inflation) ** (1 / 12) - 1
    wealth = np.empty((n_sims, n_months + 1))
    wealth[:, 0] = initial
    for t in range(n_months):
        wealth[:, t + 1] = wealth[:, t] * (1 + sim_r[:, t]) + monthly_contribution
    contrib = initial + monthly_contribution * np.arange(n_months + 1)
    pct = np.percentile(wealth, [5, 25, 50, 75, 95], axis=0)
    # drawdown of the investment performance itself (contributions excluded)
    growth = np.cumprod(1 + sim_r, axis=1)
    dd = (growth / np.maximum.accumulate(growth, axis=1) - 1).min(axis=1)
    return WealthSimulation(
        paths=wealth, contributions=contrib,
        percentiles=pd.DataFrame(pct.T, columns=["p5", "p25", "p50", "p75", "p95"],
                                 index=pd.RangeIndex(n_months + 1, name="month")),
        final=wealth[:, -1], max_drawdowns=dd, goal=goal, real=annual_inflation is not None,
    )
