---
id: 2
level: 1
level_name: Market Foundations
title: How trading works — orders, bid/ask and liquidity
minutes: 20
objectives:
  - Explain the bid, the ask and the spread
  - Choose between market, limit and stop orders
  - Understand going long, going short and why liquidity matters
widgets: [spread_calculator]
sources:
  - title: "How Stock Markets Work — Types of Orders, Executing an Order, Long and Short"
    by: "U.S. Securities and Exchange Commission (Investor.gov)"
    url: "https://www.investor.gov/introduction-investing"
  - title: "ECON 252 Financial Markets (Spring 2011) — lectures on exchanges and brokerage"
    by: "Robert J. Shiller — Yale University (Open Yale Courses)"
    url: "https://oyc.yale.edu/economics/econ-252-11"
quiz:
  - q: "A stock shows bid 99.98 and ask 100.02. You place a market buy order for 100 shares. Roughly what do you pay per share?"
    options: ["99.98", "100.00", "100.02", "It depends on yesterday's close"]
    answer: 2
    why: "A market buy takes the best available ask (if enough shares are offered at that price)."
  - q: "What is the spread in the previous question, in basis points of the mid price?"
    options: ["0.4 bp", "4 bp", "40 bp", "0.04 bp"]
    answer: 1
    why: "Spread = 0.04; mid = 100.00; 0.04 / 100 = 0.0004 = 4 basis points (1 bp = 0.01%)."
  - q: "You want to buy only if the price is 50 or lower. Which order?"
    options: ["Market order", "Limit buy at 50", "Stop buy at 50", "Short sale"]
    answer: 1
    why: "A limit buy order executes only at the limit price or better (lower)."
  - q: "What is the main risk of a market order in an illiquid stock?"
    options: ["It may never execute", "It may execute at a much worse price than the last trade", "It is illegal", "It always executes at the mid price"]
    answer: 1
    why: "Market orders guarantee execution, not price. Thin order books can produce poor fills (slippage)."
  - q: "You short-sell a stock at $50 and buy it back at $40. Ignoring costs, your profit per share is:"
    options: ["−$10", "$10", "$40", "$90"]
    answer: 1
    why: "Short = sell first, buy later. You gain when the price falls: 50 − 40 = $10. Losses are unlimited if the price rises."
  - q: "A stop (stop-loss) sell order at $45 on a stock trading at $50 means:"
    options: ["Sell immediately at $45", "Become a market sell order if the price trades at or below $45", "Never sell below $45", "Buy at $45"]
    answer: 1
    why: "A stop order triggers when the stop price is reached and then executes as a market order — the fill can be below $45 in a fast market."
---

## Two prices, not one

At any moment a liquid stock has two prices:

- the **bid** — the highest price someone is willing to **pay** (you can sell there),
- the **ask** (or offer) — the lowest price someone is willing to **accept** (you can buy there).

The **spread** = ask − bid is a cost paid by whoever trades immediately. The **mid** price
is (bid + ask) / 2.

**Example.** Bid 99.98 / ask 100.02. Spread = 0.04 = 0.04% of 100 = **4 basis points**
(1 basis point = 0.01%). Buy and immediately sell 1,000 shares and you lose about $40 to the
spread before any commission.

## Order types

| Order | What it does | Guarantees | Risk |
|---|---|---|---|
| **Market** | Trade now at the best available price | Execution | Bad price in thin or fast markets |
| **Limit** | Trade only at your price or better | Price | May never execute |
| **Stop (stop-loss)** | Becomes a market order once a trigger price trades | Triggering | Fill can be far below the trigger (gaps) |
| **Stop-limit** | Becomes a limit order at the trigger | Price | May not execute in a crash |

## Liquidity

**Liquidity** is the ability to trade size quickly without moving the price. Signs of good
liquidity: tight spreads, large volume, many orders at each price level. Mega-caps like AAPL
and ETFs like SPY are extremely liquid; small caps and far out-of-the-money options are not.
In the quantforge backtester, the **cost per trade (bps)** setting is where you account for
spread and commissions.

## Long and short

- **Long**: buy first, profit if the price rises. Maximum loss = what you paid.
- **Short**: borrow shares, sell them, buy back later. Profit if the price falls. Losses are
  **unlimited** in theory, you pay a borrow fee, and you owe any dividends paid meanwhile.

## Market hours and venues

US stock exchanges (NYSE, Nasdaq) hold their regular session from 9:30 to 16:00 New York
time on trading days, with pre- and post-market sessions that are less liquid. Crypto trades
around the clock. Prices you see from free data sources can be delayed.

{{widget:spread_calculator}}

## Summary

Every trade crosses a spread. Market orders buy certainty of execution, limit orders buy
certainty of price. Liquidity determines how expensive trading is — and every serious
backtest must charge for it.
