"""Price a live listed option three ways and compare with the market.

Usage:  python examples/price_live_option.py AAPL
"""

import sys

import numpy as np

from quantforge.data import MarketData
from quantforge.pricing import (
    binomial_price,
    bs_greeks,
    implied_forward,
    implied_volatility,
    mc_european,
)


def main(ticker: str = "AAPL") -> None:
    md = MarketData()
    spot = md.quote(ticker)
    expiry = md.option_expiries(ticker)[min(3, len(md.option_expiries(ticker)) - 1)]
    chain = md.option_chain(ticker, expiry)
    T = chain["days"].iloc[0] / 365
    curve = md.yield_curve()
    r = float(np.interp(T, curve.index, curve.values))
    q = r - np.log(implied_forward(chain, spot, r, T) / spot) / T

    print(f"{ticker} spot {spot:.2f} | expiry {expiry:%Y-%m-%d} ({T * 365:.0f}d) | "
          f"r {r:.2%} | q {q:.2%} | source {chain.attrs['source']}\n")
    print(f"{'type':5}{'strike':>9}{'mid':>9}{'IV':>8}{'BS':>9}{'Amer.':>9}{'MC':>9}{'delta':>8}")
    for typ in ("call", "put"):
        sub = chain[chain["type"] == typ]
        for _, row in sub.iloc[((sub["strike"] - spot).abs()).argsort()[:3]].iterrows():
            try:
                iv = implied_volatility(row["mid"], spot, row["strike"], T, r, typ, q)
            except ValueError:
                continue
            g = bs_greeks(spot, row["strike"], T, r, iv, typ, q)
            am = binomial_price(spot, row["strike"], T, r, iv, typ, "american", q).price
            mc = mc_european(spot, row["strike"], T, r, iv, typ, q, seed=0).price
            print(f"{typ:5}{row['strike']:9.2f}{row['mid']:9.3f}{iv:8.2%}{g.price:9.3f}"
                  f"{am:9.3f}{mc:9.3f}{g.delta:8.3f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "AAPL")
