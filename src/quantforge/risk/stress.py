"""Stress testing with real historical crisis windows and hypothetical shocks.

Historical scenarios replay what each asset **actually did** between the
scenario's start and end dates (peak-to-trough of the S&P 500 in each crisis).
If an asset has no data for a window (e.g. it IPO'd later), its loss is
estimated from its beta to a benchmark and the benchmark's actual move; such
rows are flagged ``method="beta proxy"`` so nothing is presented as observed
when it was not.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = [
    "Scenario",
    "HISTORICAL_SCENARIOS",
    "historical_stress_test",
    "hypothetical_stress_test",
]


@dataclass(frozen=True)
class Scenario:
    name: str
    start: str
    end: str
    description: str


#: Major market stress windows (dates = S&P 500 peak and trough of each episode).
HISTORICAL_SCENARIOS: list[Scenario] = [
    Scenario("Black Monday 1987", "1987-10-02", "1987-10-19", "S&P 500 -20.5% on Oct 19 alone"),
    Scenario("Dot-com crash", "2000-03-24", "2002-10-09", "Tech bubble burst, S&P 500 ~-49%"),
    Scenario("9/11", "2001-09-10", "2001-09-21", "Markets closed 4 days, then sold off"),
    Scenario("Global Financial Crisis", "2007-10-09", "2009-03-09", "Lehman collapse, S&P 500 ~-57%"),
    Scenario("Lehman month", "2008-09-12", "2008-10-10", "Lehman bankruptcy to October panic"),
    Scenario("Flash Crash 2010", "2010-04-23", "2010-07-02", "May 6 flash crash and euro worries"),
    Scenario("US downgrade 2011", "2011-07-22", "2011-10-03", "S&P downgrades US debt, euro crisis"),
    Scenario("China deval. 2015", "2015-08-10", "2015-08-25", "Yuan devaluation, Aug 24 selloff"),
    Scenario("Volmageddon 2018", "2018-01-26", "2018-02-08", "VIX spike, short-vol ETN blowups"),
    Scenario("Q4 2018 selloff", "2018-09-20", "2018-12-24", "Fed tightening fears"),
    Scenario("COVID-19 crash", "2020-02-19", "2020-03-23", "Fastest bear market on record, ~-34%"),
    Scenario("2022 rate shock", "2022-01-03", "2022-10-12", "Inflation and Fed hikes, ~-25%"),
    Scenario("SVB / regional banks", "2023-03-08", "2023-03-13", "Silicon Valley Bank failure"),
    Scenario("Tariff shock 2025", "2025-04-02", "2025-04-08", "US 'Liberation Day' tariffs selloff"),
]


def _window_return(px: pd.Series, start: str, end: str) -> float | None:
    s = px.loc[start:end].dropna()
    if len(s) < 2 or s.index[0] > pd.Timestamp(start) + pd.Timedelta(days=7):
        return None
    return float(s.iloc[-1] / s.iloc[0] - 1)


def _beta(asset: pd.Series, bench: pd.Series) -> float:
    r = pd.concat([asset.pct_change(), bench.pct_change()], axis=1, sort=True).dropna()
    if len(r) < 60:
        return 1.0
    c = np.cov(r.iloc[:, 0], r.iloc[:, 1])
    return float(c[0, 1] / c[1, 1])


def historical_stress_test(
    prices: pd.DataFrame,
    weights: Mapping[str, float] | pd.Series,
    benchmark: pd.Series | None = None,
    scenarios: list[Scenario] | None = None,
    portfolio_value: float = 1.0,
) -> pd.DataFrame:
    """Replay historical crises on a portfolio.

    Parameters
    ----------
    prices
        Adjusted close prices (wide), covering the scenario windows you want.
    weights
        Portfolio weights by column name.
    benchmark
        Benchmark prices (e.g. SPY) for the beta-proxy fallback.

    Returns
    -------
    DataFrame, one row per scenario: portfolio return, P&L, per-asset returns,
    and how many assets used the beta proxy. Scenarios that cannot be computed
    at all are omitted.
    """
    w = pd.Series(weights, dtype=float)
    scenarios = scenarios or HISTORICAL_SCENARIOS
    betas = {a: _beta(prices[a].dropna(), benchmark) for a in w.index} if benchmark is not None \
        else {}
    rows = []
    for sc in scenarios:
        asset_ret, proxied = {}, []
        bench_ret = _window_return(benchmark, sc.start, sc.end) if benchmark is not None else None
        for a in w.index:
            r = _window_return(prices[a], sc.start, sc.end) if a in prices else None
            if r is None and bench_ret is not None:
                r = betas.get(a, 1.0) * bench_ret
                proxied.append(a)
            asset_ret[a] = r
        if any(v is None for v in asset_ret.values()):
            continue
        port = float(sum(w[a] * asset_ret[a] for a in w.index))
        rows.append({
            "scenario": sc.name, "start": sc.start, "end": sc.end,
            "portfolio_return": port, "pnl": port * portfolio_value,
            "benchmark_return": bench_ret,
            "proxied_assets": ", ".join(proxied) if proxied else "",
            **{f"ret_{a}": v for a, v in asset_ret.items()},
            "description": sc.description,
        })
    return pd.DataFrame(rows).set_index("scenario") if rows else pd.DataFrame()


def hypothetical_stress_test(
    returns: pd.DataFrame,
    weights: Mapping[str, float] | pd.Series,
    benchmark_returns: pd.Series,
    market_shocks: tuple[float, ...] = (-0.05, -0.10, -0.20, -0.30, -0.40),
    vol_multiplier: float = 1.0,
    portfolio_value: float = 1.0,
    custom: Mapping[str, float] | None = None,
) -> pd.DataFrame:
    """Factor-shock stress: each asset moves ``beta × market_shock``.

    ``vol_multiplier > 1`` adds a 2-sigma idiosyncratic adverse move scaled by
    that factor (stressed correlation breakdown). ``custom`` maps asset to an
    explicit shock and overrides the beta rule for that asset.
    """
    w = pd.Series(weights, dtype=float)
    data = pd.concat([returns[w.index], benchmark_returns.rename("_mkt")], axis=1).dropna()
    var_m = data["_mkt"].var()
    out = []
    for shock in market_shocks:
        row = {"market_shock": shock}
        port = 0.0
        for a in w.index:
            beta = data[a].cov(data["_mkt"]) / var_m
            resid_sd = (data[a] - beta * data["_mkt"]).std() * np.sqrt(21)
            move = beta * shock - (vol_multiplier - 1.0) * 2 * resid_sd
            if custom and a in custom:
                move = custom[a]
            row[f"ret_{a}"] = move
            port += w[a] * move
        row["portfolio_return"] = port
        row["pnl"] = port * portfolio_value
        out.append(row)
    return pd.DataFrame(out).set_index("market_shock")
