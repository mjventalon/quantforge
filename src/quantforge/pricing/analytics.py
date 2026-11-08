"""Option-chain analytics on listed data: expected move, max pain, open-interest
profile, put/call ratios and probability of finishing in the money."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

__all__ = ["expected_move", "max_pain", "put_call_ratios", "prob_in_the_money"]


def expected_move(chain: pd.DataFrame, spot: float, maturity: float,
                  atm_iv: float | None = None) -> dict[str, float]:
    """Market-implied move to expiry.

    * ``straddle``: price of the at-the-money straddle (call mid + put mid) — what
      traders quote as "the expected move".
    * ``one_sigma``: ``spot · σ_ATM · √T`` — a ±1 standard-deviation range (~68%).
    """
    calls = chain[chain["type"] == "call"].set_index("strike")["mid"]
    puts = chain[chain["type"] == "put"].set_index("strike")["mid"]
    strikes = calls.index.intersection(puts.index)
    if len(strikes) == 0:
        raise ValueError("chain has no strike with both a call and a put")
    k = min(strikes, key=lambda x: abs(x - spot))
    straddle = float(calls[k] + puts[k])
    out = {"atm_strike": float(k), "straddle": straddle, "straddle_pct": straddle / spot}
    if atm_iv is not None:
        one = spot * atm_iv * np.sqrt(maturity)
        out.update({"one_sigma": float(one), "one_sigma_pct": float(one / spot),
                    "low_1sd": spot - one, "high_1sd": spot + one})
    return out


def max_pain(chain: pd.DataFrame) -> tuple[float, pd.Series]:
    """Strike at which option holders' total intrinsic value at expiry is smallest.

    Uses open interest. Returns the strike and the full payout curve (per strike).
    Treat as a descriptive statistic: there is little evidence it predicts prices.
    """
    oi = chain.dropna(subset=["open_interest"])
    if oi["open_interest"].sum() <= 0:
        raise ValueError("no open interest in this chain")
    strikes = np.sort(oi["strike"].unique())
    c = oi[oi["type"] == "call"]
    p = oi[oi["type"] == "put"]
    pain = []
    for s in strikes:
        pay = (np.maximum(s - c["strike"], 0) * c["open_interest"]).sum()
        pay += (np.maximum(p["strike"] - s, 0) * p["open_interest"]).sum()
        pain.append(pay)
    curve = pd.Series(pain, index=strikes, name="holder_payout")
    return float(curve.idxmin()), curve


def put_call_ratios(chain: pd.DataFrame) -> dict[str, float]:
    by = chain.groupby("type")[["volume", "open_interest"]].sum()
    get = lambda col, t: float(by.loc[t, col]) if t in by.index else np.nan  # noqa: E731
    return {"volume_pcr": get("volume", "put") / get("volume", "call")
            if get("volume", "call") else np.nan,
            "oi_pcr": get("open_interest", "put") / get("open_interest", "call")
            if get("open_interest", "call") else np.nan}


def prob_in_the_money(spot: float, strike: float, maturity: float, rate: float,
                      volatility: float, option_type: str = "call",
                      dividend_yield: float = 0.0) -> float:
    """Risk-neutral probability of expiring in the money: N(d2) for calls, N(−d2) for puts."""
    d2 = (np.log(spot / strike) + (rate - dividend_yield - 0.5 * volatility**2) * maturity) / (
        volatility * np.sqrt(maturity))
    return float(norm.cdf(d2) if option_type == "call" else norm.cdf(-d2))
