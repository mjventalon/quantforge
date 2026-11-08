"""Optimize a portfolio on real prices and save an interactive HTML report.

Usage:  python examples/portfolio_report.py AAPL MSFT NVDA JPM XOM JNJ GLD TLT
"""

import sys

import numpy as np
import pandas as pd

from quantforge.data import MarketData
from quantforge.portfolio import (
    efficient_frontier,
    estimate_inputs,
    max_sharpe,
    min_variance,
    performance_summary,
    risk_parity,
)
from quantforge.risk import var_report
from quantforge.viz import correlation_heatmap, efficient_frontier_chart, weights_chart


def main(tickers: list[str]) -> None:
    md = MarketData()
    rets = md.returns(tickers, start="2019-01-01")
    rf = md.risk_free_rate("3M")
    mu, cov = estimate_inputs(rets)
    ms, mv, rp = max_sharpe(mu, cov, rf, (0, 0.3)), min_variance(mu, cov, (0, 0.3)), \
        risk_parity(cov, mu=mu, risk_free_rate=rf)
    for p in (ms, mv, rp):
        print(p)
    port = rets @ ms.weights
    print(performance_summary(port.to_frame("Max Sharpe"), rf).round(4))
    print(var_report(port, 0.99, position_value=1_000_000).round(4))

    figs = [
        efficient_frontier_chart(efficient_frontier(mu, cov, 50, (0, 0.3)), mu,
                                 pd.Series(np.sqrt(np.diag(cov)), mu.index),
                                 {"Max Sharpe": (ms.volatility, ms.expected_return),
                                  "Min variance": (mv.volatility, mv.expected_return)}, rf,
                                 source=rets.attrs.get("source")),
        weights_chart(pd.DataFrame({"Max Sharpe": ms.weights, "Min variance": mv.weights,
                                    "Risk parity": rp.weights})),
        correlation_heatmap(rets),
    ]
    with open("portfolio_report.html", "w") as fh:
        for i, f in enumerate(figs):
            fh.write(f.to_html(full_html=i == 0, include_plotlyjs="cdn" if i == 0 else False))
    print("Saved portfolio_report.html")


if __name__ == "__main__":
    main(sys.argv[1:] or ["AAPL", "MSFT", "NVDA", "JPM", "XOM", "JNJ", "GLD", "TLT"])
