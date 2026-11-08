r"""Strategy Lab: many strategies, one book.

The edge of a systematic portfolio comes less from one great strategy than from
combining several *genuinely different* ones. This module

* runs any number of (strategy, ticker, parameters) specifications on real prices,
* measures how independent their daily return streams really are
  (:func:`diversity_report` — correlation of P&L, not of names or tickers),
* greedily assembles a portfolio that maximizes diversity or risk-adjusted return
  (:func:`greedy_portfolio`),
* checks robustness with chronological folds (:func:`fold_analysis`) and a Monte-Carlo
  resampling of the realized trades (:func:`trade_monte_carlo`),
* and exports any specification as a standalone Python script
  (:func:`export_strategy_code`).

Pair classes used in the heatmap: ρ ≤ −0.10 **diversifying**, −0.10 < ρ < 0.50
**unrelated**, ρ ≥ 0.50 **redundant**. Diversity score = 100 × (1 − mean
off-diagonal ρ), clipped to [0, 100].
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..portfolio.capm import max_drawdown, performance_summary
from .engine import run_backtest
from .strategies import STRATEGIES

__all__ = ["StrategySpec", "LabRun", "run_lab", "trade_returns", "diversity_report",
           "greedy_portfolio", "combine", "fold_analysis", "trade_monte_carlo",
           "export_strategy_code", "grade"]


@dataclass(frozen=True)
class StrategySpec:
    strategy: str                 # key of STRATEGIES
    ticker: str
    params: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        p = ",".join(f"{k}={v}" for k, v in self.params.items())
        return f"{self.strategy} · {self.ticker}" + (f" ({p})" if p else "")


@dataclass
class LabRun:
    returns: pd.DataFrame         # one column per spec label, daily net returns
    trades: dict[str, np.ndarray]  # per-spec array of trade returns
    metrics: pd.DataFrame         # per-spec performance summary
    specs: dict[str, StrategySpec]


def trade_returns(prices: pd.Series, held_position: pd.Series,
                  daily_returns: pd.Series) -> np.ndarray:
    """Compounded return of each holding period (consecutive days with the same non-zero
    position). Uses the strategy's own net daily returns, so costs are included."""
    pos = held_position.fillna(0.0).to_numpy()
    r = daily_returns.fillna(0.0).to_numpy()
    out, acc, cur = [], 1.0, 0.0
    for p, x in zip(pos, r):
        if p != cur and cur != 0:
            out.append(acc - 1.0)
            acc = 1.0
        if p != 0:
            acc *= 1 + x
        cur = p
    if cur != 0:
        out.append(acc - 1.0)
    return np.asarray(out)


def run_lab(prices: dict[str, pd.Series] | pd.DataFrame, specs: list[StrategySpec],
            cost_bps: float = 5.0, risk_free_rate: float = 0.0) -> LabRun:
    cols, trades, used = {}, {}, {}
    for spec in specs:
        if spec.strategy not in STRATEGIES:
            raise ValueError(f"unknown strategy {spec.strategy!r}")
        fn, _ = STRATEGIES[spec.strategy]
        px = prices[spec.ticker].dropna()
        res = run_backtest(px, fn(px, **spec.params), cost_bps, risk_free_rate)
        cols[spec.label] = res.returns
        trades[spec.label] = trade_returns(px, res.positions, res.returns)
        used[spec.label] = spec
    rets = pd.DataFrame(cols).dropna(how="all").fillna(0.0)
    metrics = performance_summary(rets.iloc[1:], risk_free_rate).T
    metrics["Trades"] = [len(trades[c]) for c in rets.columns]
    metrics["Win rate"] = [float((trades[c] > 0).mean()) if len(trades[c]) else np.nan
                           for c in rets.columns]
    wins = [trades[c][trades[c] > 0].sum() for c in rets.columns]
    losses = [-trades[c][trades[c] < 0].sum() for c in rets.columns]
    metrics["Profit factor"] = [w / lo if lo > 0 else np.nan for w, lo in zip(wins, losses)]
    return LabRun(returns=rets, trades=trades, metrics=metrics, specs=used)


def grade(score: float) -> str:
    return "A" if score >= 80 else "B" if score >= 65 else "C" if score >= 50 else "D"


def diversity_report(returns: pd.DataFrame) -> dict:
    """Correlation matrix, pair classes, diversity score and grade, worst pair."""
    active = returns.loc[:, returns.std() > 0]
    c = active.corr()
    n = len(c)
    if n < 2:
        return {"corr": c, "score": 100.0, "grade": "A", "worst_pair": None,
                "classes": pd.DataFrame()}
    iu = np.triu_indices(n, 1)
    vals = c.to_numpy()[iu]
    score = float(np.clip(100 * (1 - vals.mean()), 0, 100))
    k = int(np.argmax(vals))
    worst = (c.index[iu[0][k]], c.columns[iu[1][k]], float(vals[k]))
    classes = c.map(lambda v: "diversifying" if v <= -0.10 else "redundant" if v >= 0.50
                    else "unrelated")
    return {"corr": c, "score": score, "grade": grade(score), "worst_pair": worst,
            "classes": classes, "mean_corr": float(vals.mean())}


def combine(returns: pd.DataFrame, method: str = "equal_risk",
            weights: pd.Series | None = None) -> tuple[pd.Series, pd.Series]:
    """Daily-rebalanced combination. ``equal_risk`` weights ∝ 1/σ (past full-sample σ)."""
    if weights is None:
        if method == "equal":
            weights = pd.Series(1.0, index=returns.columns)
        elif method == "equal_risk":
            sd = returns.std().replace(0, np.nan)
            weights = (1 / sd).fillna(0)
        else:
            raise ValueError("method must be 'equal' or 'equal_risk'")
    w = weights / weights.sum()
    return (returns[w.index] @ w).rename("portfolio"), w


def _sharpe(x: pd.Series) -> float:
    sd = x.std()
    return float(x.mean() / sd * np.sqrt(252)) if sd > 0 else -np.inf


def greedy_portfolio(returns: pd.DataFrame, size: int = 5, objective: str = "diversity",
                     min_sharpe: float | None = 0.0) -> list[str]:
    """Pick strategies one at a time, each time adding the one that most improves
    the objective: ``"diversity"`` (diversity score, ties broken by Sharpe) or
    ``"sharpe"`` (Sharpe of the equal-risk combination).

    Starts from the best stand-alone Sharpe. Candidates below ``min_sharpe`` are skipped.
    """
    pool = [c for c in returns.columns if returns[c].std() > 0]
    if min_sharpe is not None:
        pool = [c for c in pool if _sharpe(returns[c]) >= min_sharpe]
    if not pool:
        raise ValueError("no candidate strategy passes the quality filter")
    chosen = [max(pool, key=lambda c: _sharpe(returns[c]))]
    while len(chosen) < min(size, len(pool)):
        best, best_val = None, -np.inf
        for c in pool:
            if c in chosen:
                continue
            trial = chosen + [c]
            if objective == "diversity":
                val = diversity_report(returns[trial])["score"] + 1e-3 * _sharpe(returns[c])
            else:
                val = _sharpe(combine(returns[trial])[0])
            if val > best_val:
                best, best_val = c, val
        chosen.append(best)
    return chosen


def fold_analysis(returns: pd.Series, n_folds: int = 3) -> pd.DataFrame:
    """Split history into consecutive folds and report each one's performance."""
    r = returns.dropna()
    edges = np.linspace(0, len(r), n_folds + 1).astype(int)
    rows = []
    for i in range(n_folds):
        part = r.iloc[edges[i]:edges[i + 1]]
        rows.append({"fold": i + 1, "start": part.index[0], "end": part.index[-1],
                     "return": float((1 + part).prod() - 1), "sharpe": _sharpe(part),
                     "max_drawdown": max_drawdown(part)})
    out = pd.DataFrame(rows).set_index("fold")
    out.attrs["profitable_folds"] = int((out["return"] > 0).sum())
    return out


def trade_monte_carlo(trade_rets: np.ndarray, n_sims: int = 1000, initial: float = 10_000.0,
                      seed: int | None = 0) -> dict:
    """Resample the realized trades (with replacement, same count) into new sequences.

    Tells you how much of the result depends on the *order* and *luck* of trades.
    Returns percentile paths, P(profit), median final value and the 95th percentile
    of max drawdown.
    """
    t = np.asarray(trade_rets, dtype=float)
    if t.size < 5:
        raise ValueError("need at least 5 trades")
    rng = np.random.default_rng(seed)
    draws = t[rng.integers(0, t.size, size=(n_sims, t.size))]
    paths = initial * np.cumprod(1 + draws, axis=1)
    paths = np.hstack([np.full((n_sims, 1), initial), paths])
    peaks = np.maximum.accumulate(paths, axis=1)
    mdd = (paths / peaks - 1).min(axis=1)
    final = paths[:, -1]
    pct = pd.DataFrame(np.percentile(paths, [5, 25, 50, 75, 95], axis=0).T,
                       columns=["p5", "p25", "p50", "p75", "p95"])
    p_profit = float((final > initial).mean())
    return {"percentiles": pct, "p_profit": p_profit, "median_final": float(np.median(final)),
            "p95_max_drawdown": float(-np.percentile(-mdd, 95)),
            "verdict": "PASS" if p_profit >= 0.9 and np.median(final) > initial else "FAIL",
            "n_trades": int(t.size), "final": final}


def export_strategy_code(spec: StrategySpec, start: str = "2010-01-01",
                         cost_bps: float = 5.0) -> str:
    """A standalone, runnable Python script that reproduces this backtest."""
    fn, _ = STRATEGIES[spec.strategy]
    params = ", ".join(f"{k}={v!r}" for k, v in spec.params.items())
    return f'''"""Backtest exported from quantforge Strategy Lab.

Strategy : {spec.strategy}
Ticker   : {spec.ticker}
Params   : {spec.params}
Run      : pip install "quantforge[yahoo]"  then  python this_file.py
"""
from quantforge.backtest import run_backtest
from quantforge.backtest.strategies import {fn.__name__}
from quantforge.data import MarketData

md = MarketData("yahoo")
prices = md.history("{spec.ticker}", start="{start}")["adj_close"]
position = {fn.__name__}(prices{", " + params if params else ""})
result = run_backtest(prices, position, cost_bps={cost_bps}, risk_free_rate=md.risk_free_rate())
print(result.metrics.round(4))
print(result.trades.tail(10))
'''
