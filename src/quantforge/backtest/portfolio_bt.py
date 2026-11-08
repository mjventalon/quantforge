"""Walk-forward portfolio backtests: re-optimize on past data only, hold, repeat.

This is the honest way to judge an optimizer. At each rebalance date the
weights are estimated from the trailing ``lookback`` window **ending that day**,
then held (drifting with prices) until the next rebalance.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from ..portfolio.capm import performance_summary
from ..portfolio.optimization import estimate_inputs, max_sharpe, min_variance, risk_parity

__all__ = ["walk_forward_portfolio", "OPTIMIZERS"]


def _equal(returns: pd.DataFrame, rf: float, bounds: tuple) -> np.ndarray:
    return np.full(returns.shape[1], 1.0 / returns.shape[1])


def _minvar(returns: pd.DataFrame, rf: float, bounds: tuple) -> np.ndarray:
    mu, cov = estimate_inputs(returns)
    return min_variance(mu, cov, bounds).weights.to_numpy()


def _maxsharpe(returns: pd.DataFrame, rf: float, bounds: tuple) -> np.ndarray:
    mu, cov = estimate_inputs(returns)
    try:
        return max_sharpe(mu, cov, rf, bounds).weights.to_numpy()
    except ValueError:  # every asset below rf in this window -> fall back to min variance
        return min_variance(mu, cov, bounds).weights.to_numpy()


def _riskparity(returns: pd.DataFrame, rf: float, bounds: tuple) -> np.ndarray:
    _, cov = estimate_inputs(returns)
    return risk_parity(cov).weights.to_numpy()


OPTIMIZERS: dict[str, Callable] = {
    "Equal weight": _equal,
    "Minimum variance": _minvar,
    "Maximum Sharpe": _maxsharpe,
    "Risk parity": _riskparity,
}


def walk_forward_portfolio(
    prices: pd.DataFrame,
    methods: list[str] | None = None,
    lookback: int = 252,
    rebalance: str = "ME",
    cost_bps: float = 5.0,
    bounds: tuple = (0.0, 1.0),
    risk_free_rate: float = 0.0,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame]:
    """Out-of-sample backtest of several allocation methods.

    Returns ``(daily_returns, weights_history, metrics)``.
    """
    methods = methods or list(OPTIMIZERS)
    rets = prices.pct_change().dropna()
    if len(rets) <= lookback + 21:
        raise ValueError("not enough history for this lookback")
    dates = rets.index[lookback:]
    rebal = set(pd.Series(dates, index=dates).resample(rebalance).last().dropna())
    out, weights_hist = {}, {}
    for m in methods:
        fn = OPTIMIZERS[m]
        w = None
        daily, hist = [], {}
        for d in dates:
            r_today = rets.loc[d].to_numpy()
            if w is not None:
                port_r = float(w @ r_today)
                w = w * (1 + r_today) / (1 + port_r)       # drift with prices
            else:
                port_r = 0.0
            if w is None or d in rebal:
                window = rets.loc[:d].iloc[-lookback:]
                new_w = fn(window, risk_free_rate, bounds)
                cost = 0.0 if w is None else np.abs(new_w - w).sum() * cost_bps / 1e4
                port_r -= cost
                w = new_w
                hist[d] = new_w
            daily.append(port_r)
        out[m] = pd.Series(daily, index=dates)
        weights_hist[m] = pd.DataFrame(hist, index=prices.columns).T
    returns = pd.DataFrame(out).iloc[1:]
    return returns, weights_hist, performance_summary(returns, risk_free_rate)
