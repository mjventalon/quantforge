r"""Vectorized, look-ahead-free backtesting.

Timing convention (the most common source of fake backtest profits):

* A strategy computes its **target position** at the close of day *t* using
  data up to and including *t*.
* That position earns the asset's return from close *t* to close *t+1*.
* Trading costs are charged on every change of position (turnover), in basis
  points of traded notional.

So ``strategy_return[t] = position[t-1] * asset_return[t] - cost * |position[t] - position[t-1]|``:
the cost of a trade made at the close of *t* is booked on day *t*.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from itertools import product

import pandas as pd

from ..portfolio.capm import performance_summary

__all__ = ["BacktestResult", "run_backtest", "grid_search", "trades_from_positions"]


@dataclass
class BacktestResult:
    """Output of :func:`run_backtest`."""

    returns: pd.Series            # strategy daily returns, net of costs
    benchmark: pd.Series          # buy-and-hold daily returns of the same asset
    positions: pd.Series          # position held during each day's return
    equity: pd.Series             # growth of 1
    trades: pd.DataFrame
    metrics: pd.DataFrame
    params: dict = field(default_factory=dict)

    @property
    def exposure(self) -> float:
        """Share of days with a non-zero position."""
        return float((self.positions != 0).mean())


def trades_from_positions(positions: pd.Series, prices: pd.Series) -> pd.DataFrame:
    """One row per position change: date, price, old → new position."""
    pos = positions.fillna(0.0)
    change = pos.diff().fillna(pos.iloc[0] if len(pos) else 0.0)
    idx = change[change != 0].index
    return pd.DataFrame({"price": prices.reindex(idx), "from": pos.shift(1).fillna(0).loc[idx],
                         "to": pos.loc[idx]}, index=idx).rename_axis("date")


def run_backtest(
    prices: pd.Series,
    target_position: pd.Series,
    cost_bps: float = 5.0,
    risk_free_rate: float = 0.0,
    params: dict | None = None,
) -> BacktestResult:
    """Backtest a target-position series (e.g. +1 long, 0 flat, −1 short, or any weight).

    Parameters
    ----------
    prices
        Adjusted close prices.
    target_position
        Desired exposure decided at each close (aligned to ``prices``).
    cost_bps
        One-way trading cost in basis points of notional traded (commission + spread).
    """
    px = prices.dropna()
    asset_ret = px.pct_change().fillna(0.0)
    target = target_position.reindex(px.index).ffill().fillna(0.0)
    held = target.shift(1).fillna(0.0)                       # decided yesterday, held today
    turnover = target.diff().abs().fillna(target.abs())       # traded at today's close
    strat = held * asset_ret - turnover * cost_bps / 1e4      # cost booked the day it trades
    equity = (1 + strat).cumprod()
    bench = asset_ret.copy()
    metrics = performance_summary(pd.DataFrame({"Strategy": strat.iloc[1:],
                                                "Buy & hold": bench.iloc[1:]}), risk_free_rate)
    turnover_ann = float(turnover.mean() * 252)
    extra = pd.DataFrame({"Strategy": [len(trades_from_positions(target, px)), turnover_ann,
                                       float((held != 0).mean())],
                          "Buy & hold": [1, 0.0, 1.0]},
                         index=["Trades", "Annual turnover", "Time in market"])
    return BacktestResult(
        returns=strat.rename("strategy"), benchmark=bench.rename("buy_and_hold"),
        positions=held.rename("position"), equity=equity.rename("equity"),
        trades=trades_from_positions(target, px), metrics=pd.concat([metrics, extra]),
        params=params or {},
    )


def grid_search(
    prices: pd.Series,
    strategy: Callable[..., pd.Series],
    grid: dict[str, Iterable],
    cost_bps: float = 5.0,
    train_fraction: float = 0.6,
    metric: str = "Sharpe",
    risk_free_rate: float = 0.0,
) -> tuple[pd.DataFrame, dict]:
    """Try every parameter combination on a **training** window, report each one's
    metric on train *and* on the untouched **test** window.

    Returns the full table and the parameters that were best on train. A big
    drop from train to test is the signature of overfitting.
    """
    px = prices.dropna()
    split = px.index[int(len(px) * train_fraction)]
    rows = []
    keys = list(grid)
    for values in product(*(list(grid[k]) for k in keys)):
        p = dict(zip(keys, values))
        try:
            pos = strategy(px, **p)
        except ValueError:
            continue
        full = run_backtest(px, pos, cost_bps, risk_free_rate)
        tr = full.returns.loc[:split].iloc[1:]
        te = full.returns.loc[split:].iloc[1:]
        m_tr = performance_summary(tr.to_frame("x"), risk_free_rate).loc[metric, "x"]
        m_te = performance_summary(te.to_frame("x"), risk_free_rate).loc[metric, "x"]
        rows.append({**p, f"train_{metric}": m_tr, f"test_{metric}": m_te})
    if not rows:
        raise ValueError("no valid parameter combination")
    table = pd.DataFrame(rows)
    best = table.loc[table[f"train_{metric}"].idxmax(), keys].to_dict()
    table.attrs["split_date"] = split
    return table, best
