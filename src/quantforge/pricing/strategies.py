"""Multi-leg option strategies: payoff at expiry, value and Greeks before expiry.

>>> from quantforge.pricing.strategies import OptionLeg, Strategy
>>> s = Strategy([OptionLeg("call", 100, +1), OptionLeg("call", 110, -1)], name="Bull call spread")
>>> s.payoff(120)
10.0
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ._common import OptionType
from .black_scholes import bs_greeks

__all__ = ["OptionLeg", "StockLeg", "Strategy", "PRESETS"]


@dataclass(frozen=True)
class OptionLeg:
    option_type: str
    strike: float
    quantity: float = 1.0            # +long / -short, in contracts of 1 underlying
    maturity: float | None = None    # years; None = strategy default
    volatility: float | None = None  # None = strategy default
    premium: float | None = None     # price paid/received per unit; None = BS value at entry


@dataclass(frozen=True)
class StockLeg:
    quantity: float = 1.0
    entry_price: float | None = None


@dataclass
class Strategy:
    legs: list[OptionLeg | StockLeg]
    name: str = "Custom"
    multiplier: float = 1.0
    _premiums: dict[int, float] = field(default_factory=dict, repr=False)

    def entry_cost(self, spot: float, maturity: float, rate: float, volatility: float,
                   dividend_yield: float = 0.0) -> float:
        """Net debit (>0) or credit (<0) to open the position."""
        cost = 0.0
        for i, leg in enumerate(self.legs):
            if isinstance(leg, StockLeg):
                cost += leg.quantity * (leg.entry_price if leg.entry_price is not None else spot)
                continue
            prem = leg.premium
            if prem is None:
                prem = float(bs_greeks(spot, leg.strike, leg.maturity or maturity, rate,
                                       leg.volatility or volatility, leg.option_type,
                                       dividend_yield).price)
            self._premiums[i] = prem
            cost += leg.quantity * prem
        return cost * self.multiplier

    def payoff(self, spot_at_expiry: float | np.ndarray) -> float | np.ndarray:
        """Intrinsic value at expiry (excluding premiums)."""
        s = np.asarray(spot_at_expiry, dtype=float)
        total = np.zeros_like(s)
        for leg in self.legs:
            if isinstance(leg, StockLeg):
                total = total + leg.quantity * s
            elif OptionType.parse(leg.option_type) is OptionType.CALL:
                total = total + leg.quantity * np.maximum(s - leg.strike, 0.0)
            else:
                total = total + leg.quantity * np.maximum(leg.strike - s, 0.0)
        out = total * self.multiplier
        return float(out) if out.ndim == 0 else out

    def profit_at_expiry(self, spot_at_expiry: np.ndarray, entry_spot: float, maturity: float,
                         rate: float, volatility: float, dividend_yield: float = 0.0) -> np.ndarray:
        cost = self.entry_cost(entry_spot, maturity, rate, volatility, dividend_yield)
        return np.asarray(self.payoff(spot_at_expiry)) - cost

    def value(self, spot: np.ndarray | float, time_left: float, rate: float, volatility: float,
              dividend_yield: float = 0.0) -> dict[str, np.ndarray]:
        """Mark-to-model value and Greeks with ``time_left`` years to the default expiry."""
        s = np.atleast_1d(np.asarray(spot, dtype=float))
        agg = {k: np.zeros_like(s) for k in ("price", "delta", "gamma", "vega", "theta", "rho")}
        for leg in self.legs:
            if isinstance(leg, StockLeg):
                agg["price"] += leg.quantity * s
                agg["delta"] += leg.quantity
                continue
            t = max(time_left if leg.maturity is None else leg.maturity, 1e-6)
            g = bs_greeks(s, leg.strike, t, rate, leg.volatility or volatility,
                          leg.option_type, dividend_yield)
            for k in agg:
                agg[k] = agg[k] + leg.quantity * np.asarray(getattr(g, k))
        return {k: v * self.multiplier for k, v in agg.items()}

    def breakevens(self, entry_spot: float, maturity: float, rate: float, volatility: float,
                   dividend_yield: float = 0.0, span: float = 3.0) -> list[float]:
        grid = np.linspace(entry_spot / span, entry_spot * span, 20001)
        pnl = self.profit_at_expiry(grid, entry_spot, maturity, rate, volatility, dividend_yield)
        idx = np.where(np.diff(np.sign(pnl)) != 0)[0]
        return [float(grid[i] - pnl[i] * (grid[i + 1] - grid[i]) / (pnl[i + 1] - pnl[i]))
                for i in idx]


def _p(spot: float, pct: float) -> float:
    return round(spot * pct, 2)


#: Factory functions for common strategies, keyed by display name.
PRESETS = {
    "Long call": lambda s: [OptionLeg("call", _p(s, 1.0), 1)],
    "Long put": lambda s: [OptionLeg("put", _p(s, 1.0), 1)],
    "Covered call": lambda s: [StockLeg(1), OptionLeg("call", _p(s, 1.05), -1)],
    "Protective put": lambda s: [StockLeg(1), OptionLeg("put", _p(s, 0.95), 1)],
    "Bull call spread": lambda s: [OptionLeg("call", _p(s, 1.0), 1),
                                   OptionLeg("call", _p(s, 1.1), -1)],
    "Bear put spread": lambda s: [OptionLeg("put", _p(s, 1.0), 1),
                                  OptionLeg("put", _p(s, 0.9), -1)],
    "Long straddle": lambda s: [OptionLeg("call", _p(s, 1.0), 1), OptionLeg("put", _p(s, 1.0), 1)],
    "Long strangle": lambda s: [OptionLeg("call", _p(s, 1.05), 1),
                                OptionLeg("put", _p(s, 0.95), 1)],
    "Iron condor": lambda s: [OptionLeg("put", _p(s, 0.85), 1), OptionLeg("put", _p(s, 0.93), -1),
                              OptionLeg("call", _p(s, 1.07), -1),
                              OptionLeg("call", _p(s, 1.15), 1)],
    "Butterfly (calls)": lambda s: [OptionLeg("call", _p(s, 0.93), 1),
                                    OptionLeg("call", _p(s, 1.0), -2),
                                    OptionLeg("call", _p(s, 1.07), 1)],
    "Collar": lambda s: [StockLeg(1), OptionLeg("put", _p(s, 0.93), 1),
                         OptionLeg("call", _p(s, 1.07), -1)],
}
