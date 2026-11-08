---
id: 1
level: 1
level_name: Market Foundations
title: What financial markets are and what you can buy
minutes: 20
objectives:
  - Explain what a stock, a bond, a fund, an ETF and an index are
  - Tell the difference between primary and secondary markets
  - Read a ticker symbol, including indices, crypto and foreign listings
widgets: [market_snapshot]
sources:
  - title: "Introduction to Investing — Investing Basics & Glossary"
    by: "U.S. Securities and Exchange Commission (Investor.gov)"
    url: "https://www.investor.gov/introduction-investing"
  - title: "ECON 252 Financial Markets (Spring 2011), Lecture 1"
    by: "Robert J. Shiller — Yale University (Open Yale Courses)"
    url: "https://oyc.yale.edu/economics/econ-252-11"
  - title: "15.401 Finance Theory I (Fall 2008), Introduction and Course Overview"
    by: "Andrew W. Lo — MIT OpenCourseWare"
    url: "https://ocw.mit.edu/courses/15-401-finance-theory-i-fall-2008/"
quiz:
  - q: "You own one share of a company. What do you own?"
    options: ["A loan to the company", "A small fraction of the company's ownership", "A promise of a fixed annual payment", "The right to buy the company later"]
    answer: 1
    why: "A share (stock, equity) is a slice of ownership. A loan to the company is a bond."
  - q: "A company issues a 10-year bond with a 4% annual coupon and $1,000 face value. If it does not default, what does the holder receive?"
    options: ["$40 a year for 10 years, then $1,000", "$1,040 once after 10 years", "A share of the profits", "$400 a year for 10 years"]
    answer: 0
    why: "Coupon = 4% × $1,000 = $40 per year; the face value is repaid at maturity."
  - q: "What is the S&P 500?"
    options: ["A company", "An index measuring the stock prices of about 500 large US companies", "A government bond", "A stock exchange"]
    answer: 1
    why: "An index is a number that summarizes the prices of a basket. You cannot buy it directly — you buy a fund that tracks it (e.g. SPY, VOO)."
  - q: "What mainly distinguishes an ETF from a classic mutual fund?"
    options: ["ETFs cannot hold stocks", "ETF shares trade on an exchange all day at market prices", "ETFs are always actively managed", "ETFs never charge fees"]
    answer: 1
    why: "Exchange-traded funds trade like stocks during market hours; mutual fund orders are filled once a day at the net asset value."
  - q: "When you buy Apple shares on the Nasdaq, who usually receives your money?"
    options: ["Apple", "Another investor who sells the shares (secondary market)", "The SEC", "The Nasdaq index"]
    answer: 1
    why: "Companies raise money in the primary market (IPOs, new issues). Day-to-day trading happens between investors in the secondary market."
  - q: "On Yahoo Finance, what is ^GSPC?"
    options: ["A crypto coin", "The S&P 500 index", "Gold futures", "A Paris-listed stock"]
    answer: 1
    why: "The ^ prefix marks an index. Crypto looks like BTC-USD, futures like GC=F, Paris listings like MC.PA."
---

## Why markets exist

A financial market connects people who **have money today** with people who **need money
today**. Savers want their money to grow; companies and governments want to fund projects.
Markets let the first group lend to or invest in the second, and let everyone *change their
mind* later by selling to someone else.

That second point matters: a company raises money once, in the **primary market** (an IPO
or a new bond issue). Afterwards the securities change hands between investors in the
**secondary market** — that is what you see on a stock exchange every day. The company does
not receive money when you buy its shares from another investor.

## The main things you can buy

| Instrument | What you own | How you make or lose money |
|---|---|---|
| **Stock** (share, equity) | A fraction of a company | Price changes + dividends. Shareholders are paid *last* if the company fails. |
| **Bond** | A loan to a company or government | Fixed coupons + repayment of the face value at maturity. Price falls when interest rates rise. |
| **Fund** (mutual fund) | A slice of a managed basket | Value of the basket minus fees. |
| **ETF** | A fund whose shares trade on an exchange | Same as a fund, but you can buy and sell all day. |
| **Index** | Nothing — it is a *measurement* | You invest in it through an index fund or ETF. |
| **Derivative** (option, future) | A contract whose value depends on another asset | Covered from Level 4. |
| **Crypto asset** | A digital token | Price changes only; no company earnings behind most tokens. |

**Example.** A 10-year bond with a $1,000 face value and a 4% coupon pays $40 a year for
ten years and then returns the $1,000 — *if the issuer does not default*.

## Indices: thermometers of the market

An index summarizes a whole market in one number. The **S&P 500** tracks about 500 large US
companies, weighted by market value; the **Nasdaq-100** tracks large non-financial companies
listed on Nasdaq; the **CAC 40** tracks 40 large French companies. Funds such as SPY or VOO
hold the stocks of the S&P 500 so investors can own "the market" in one trade.

## Reading a ticker symbol

Every instrument has a short code. quantforge uses Yahoo Finance conventions:

- `AAPL` — Apple, a US stock
- `SPY` — an ETF tracking the S&P 500
- `^GSPC` — the S&P 500 **index** itself (the `^` means index)
- `MC.PA` — LVMH on Euronext **Paris** (suffix = exchange)
- `BTC-USD` — bitcoin priced in US dollars
- `EURUSD=X` — the euro/dollar exchange rate
- `GC=F` — gold **futures**

Try the snapshot below: it downloads real prices for one instrument of each kind.

{{widget:market_snapshot}}

## Key words

**Security** — a tradable financial asset (stock, bond, fund share…). **Issuer** — the
entity that creates a security to raise money. **Market capitalization** — share price ×
number of shares. **Liquidity** — how easily you can buy or sell without moving the price.

## Summary

Markets move money from savers to users of capital. Stocks give ownership, bonds give
fixed claims, funds and ETFs give baskets, indices measure, derivatives transfer risk.
Most trading is between investors in the secondary market.
