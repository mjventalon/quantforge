"""VaR, backtest and historical stress test for a real multi-asset portfolio.

Usage:  python examples/risk_dashboard.py
"""

import numpy as np

from quantforge.data import MarketData
from quantforge.risk import backtest_var, historical_stress_test, rolling_var, var_report

WEIGHTS = {"SPY": 0.5, "TLT": 0.3, "GLD": 0.2}
VALUE = 1_000_000


def main() -> None:
    md = MarketData()
    rets = md.returns(list(WEIGHTS), start="2010-01-01")
    port = rets @ np.array(list(WEIGHTS.values()))
    print(var_report(port, 0.99, position_value=VALUE).round(4), "\n")
    bt = backtest_var(port, rolling_var(port, 250, 0.99), 0.99)
    print(f"Backtest: {bt.n_exceptions} exceptions vs {bt.expected_exceptions:.1f} expected, "
          f"Kupiec p={bt.kupiec_pvalue:.3f}, Christoffersen p={bt.christoffersen_pvalue:.3f}, "
          f"Basel zone {bt.basel_zone}\n")
    px = md.prices(list(WEIGHTS) + ["SPY"], start="1990-01-01", dropna=False)
    res = historical_stress_test(px, WEIGHTS, px["SPY"].dropna(), portfolio_value=VALUE)
    print(res[["start", "end", "portfolio_return", "pnl", "proxied_assets"]].round(4))


if __name__ == "__main__":
    main()
