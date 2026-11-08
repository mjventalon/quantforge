"""Factor exposure with tradable ETF proxies, and market performance tables.

Academic factors (Fama-French) are long-short paper portfolios. Here each
factor is built from liquid ETFs whose prices anyone can download, so the
analysis runs on live data:

=========  ===============================  ============================
Factor     Construction                     Meaning
=========  ===============================  ============================
Market     SPY − risk-free                  equity market risk
Size       IWM − SPY                        small caps vs large caps
Value      IWD − IWF                        value vs growth (Russell 1000)
Momentum   MTUM − SPY                       recent winners
Quality    QUAL − SPY                       profitable, stable firms
Low vol    USMV − SPY                       defensive stocks
Rates      IEF                              7-10y Treasuries (duration)
=========  ===============================  ============================
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..credit.regression import ols

__all__ = ["FactorResult", "FACTOR_PROXIES", "build_factor_returns", "factor_regression",
           "period_returns",
           "SECTOR_ETFS", "ASSET_CLASS_ETFS"]

FACTOR_PROXIES: dict[str, tuple[str, str | None]] = {
    "Market": ("SPY", None),
    "Size": ("IWM", "SPY"),
    "Value": ("IWD", "IWF"),
    "Momentum": ("MTUM", "SPY"),
    "Quality": ("QUAL", "SPY"),
    "Low vol": ("USMV", "SPY"),
    "Rates": ("IEF", None),
}

SECTOR_ETFS = {
    "XLK": "Technology", "XLF": "Financials", "XLV": "Health care", "XLY": "Consumer disc.",
    "XLP": "Consumer staples", "XLE": "Energy", "XLI": "Industrials", "XLB": "Materials",
    "XLU": "Utilities", "XLRE": "Real estate", "XLC": "Communication",
}

ASSET_CLASS_ETFS = {
    "SPY": "US large caps", "QQQ": "Nasdaq 100", "IWM": "US small caps", "EFA": "Developed ex-US",
    "EEM": "Emerging markets", "TLT": "US Treasuries 20y+", "IEF": "US Treasuries 7-10y",
    "LQD": "IG corporate bonds", "HYG": "High yield bonds", "GLD": "Gold", "USO": "Crude oil",
    "UUP": "US dollar", "VNQ": "US REITs", "IBIT": "Bitcoin (spot ETF)",
}


def build_factor_returns(etf_returns: pd.DataFrame, risk_free_rate: float = 0.0,
                         factors: list[str] | None = None,
                         periods_per_year: int = 252) -> pd.DataFrame:
    """Factor return series from ETF returns (columns must include the proxies needed)."""
    out = {}
    for name in factors or list(FACTOR_PROXIES):
        long_, short = FACTOR_PROXIES[name]
        if long_ not in etf_returns or (short and short not in etf_returns):
            continue
        if name == "Market":
            out[name] = etf_returns[long_] - risk_free_rate / periods_per_year
        elif short is None:
            out[name] = etf_returns[long_] - risk_free_rate / periods_per_year
        else:
            out[name] = etf_returns[long_] - etf_returns[short]
    return pd.DataFrame(out).dropna()


@dataclass
class FactorResult:
    table: pd.DataFrame            # coef, std_err, t, p_value; first row = annual alpha
    r_squared: float
    variance_share: pd.Series      # share of the asset's variance explained by each factor
    n_obs: int


def factor_regression(asset_returns: pd.Series, factor_returns: pd.DataFrame,
                      risk_free_rate: float = 0.0, periods_per_year: int = 252) -> FactorResult:
    """Multi-factor OLS of excess returns on factors, HC1 robust standard errors.

    The table has one row per term with beta, t-stat, p-value; alpha is annualized.
    """
    df = pd.concat([asset_returns.rename("_y"), factor_returns], axis=1).dropna()
    y = df["_y"] - risk_free_rate / periods_per_year
    X = df.drop(columns="_y")
    res = ols(y, X, cov_type="HC1")
    out = res.summary()[["coef", "std_err", "t", "p_value"]].copy()
    out.loc["const", ["coef", "std_err"]] *= periods_per_year
    out = out.rename(index={"const": "Alpha (annual)"})
    betas = res.params.drop("const")
    contrib = betas.to_numpy() * (X.cov().to_numpy() @ betas.to_numpy()) / y.var()
    return FactorResult(table=out, r_squared=float(res.r_squared),
                        variance_share=pd.Series(np.asarray(contrib), index=betas.index),
                        n_obs=int(res.n_obs))


def period_returns(prices: pd.DataFrame, as_of: pd.Timestamp | None = None) -> pd.DataFrame:
    """Trailing total returns: 1D, 1W, 1M, 3M, 6M, YTD, 1Y, 3Y (annualized), 1Y vol."""
    px = prices.dropna(how="all")
    end = pd.Timestamp(as_of) if as_of is not None else px.index[-1]
    px = px.loc[:end]
    last = px.iloc[-1]

    def back(offset: pd.DateOffset) -> pd.Series:
        sub = px.loc[: end - offset]
        return sub.iloc[-1] if len(sub) else pd.Series(np.nan, index=px.columns)

    ytd_base = px.loc[: pd.Timestamp(year=end.year, month=1, day=1) - pd.Timedelta(days=1)]
    out = pd.DataFrame({
        "1D": last / px.iloc[-2] - 1,
        "1W": last / back(pd.DateOffset(weeks=1)) - 1,
        "1M": last / back(pd.DateOffset(months=1)) - 1,
        "3M": last / back(pd.DateOffset(months=3)) - 1,
        "6M": last / back(pd.DateOffset(months=6)) - 1,
        "YTD": last / (ytd_base.iloc[-1] if len(ytd_base) else np.nan) - 1,
        "1Y": last / back(pd.DateOffset(years=1)) - 1,
        "3Y ann.": (last / back(pd.DateOffset(years=3))) ** (1 / 3) - 1,
        "1Y vol": px.pct_change().iloc[-252:].std() * np.sqrt(252),
    })
    out.attrs["as_of"] = end.strftime("%Y-%m-%d")
    return out
