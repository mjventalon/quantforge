---
id: 12
level: 4
level_name: Derivatives
title: Options — calls, puts, payoffs and strategies
minutes: 30
objectives:
  - Draw the payoff of calls and puts, long and short
  - Compute break-even prices and maximum gain/loss
  - Use put-call parity and recognize common strategies
widgets: [payoff_lab]
sources:
  - title: "Options, Futures, and Other Derivatives"
    by: "John C. Hull (textbook)"
    url: ""
  - title: "Options education resources"
    by: "The Options Industry Council (OIC)"
    url: "https://www.optionseducation.org/"
  - title: "15.401 Finance Theory I — Options (Recitation 5)"
    by: "Andrew W. Lo — MIT OpenCourseWare"
    url: "https://ocw.mit.edu/courses/15-401-finance-theory-i-fall-2008/"
quiz:
  - q: "You buy a call with strike 100 for a premium of 5. At expiry the stock is 120. Your profit per share:"
    options: ["20", "15", "25", "−5"]
    answer: 1
    why: "Payoff = max(120 − 100, 0) = 20; minus premium 5 → 15."
  - q: "Break-even at expiry for that call:"
    options: ["95", "100", "105", "120"]
    answer: 2
    why: "Strike + premium = 105."
  - q: "Maximum loss when buying a put:"
    options: ["Unlimited", "The premium paid", "The strike", "Zero"]
    answer: 1
    why: "A long option can lose at most its premium."
  - q: "Selling a naked call has maximum loss:"
    options: ["The premium", "The strike", "Unlimited in theory", "Zero"]
    answer: 2
    why: "The stock can rise without limit; the short call holder must deliver at the strike."
  - q: "Put-call parity (European, no dividends): C − P equals"
    options: ["S − K", "S − K·e^(−rT)", "K − S", "0"]
    answer: 1
    why: "C − P = S − K e^(−rT). Otherwise an arbitrage exists."
  - q: "A long straddle (buy call + put, same strike) profits when:"
    options: ["The stock stays exactly at the strike", "The stock moves a lot in either direction", "Interest rates fall", "Volatility falls"]
    answer: 1
    why: "It needs a move larger than the total premium paid — a bet on volatility."
  - q: "US single-stock options are usually American-style, meaning:"
    options: ["They trade only in the US", "They can be exercised any time before expiry", "They can only be exercised at expiry", "They are cash-settled"]
    answer: 1
    why: "European options can only be exercised at expiry; the difference matters for pricing (chapter 14)."
---

## Definitions

- **Call**: the right, not the obligation, to **buy** the underlying at the **strike** $K$
  until/at expiry $T$.
- **Put**: the right to **sell** at $K$.
- The buyer pays a **premium** to the seller (writer). One US equity option contract
  usually covers **100 shares**.
- **European** = exercise only at expiry; **American** = any time before.

## Payoffs at expiry

$$\text{Call} = \max(S_T - K, 0), \qquad \text{Put} = \max(K - S_T, 0)$$

**Example.** Long call K = 100, premium 5. At $S_T$ = 120: payoff 20, profit **15**.
Break-even **105**. Max loss **5** (the premium). Max gain: unlimited.

| Position | Max gain | Max loss | View |
|---|---|---|---|
| Long call | Unlimited | Premium | Bullish |
| Long put | K − premium | Premium | Bearish / insurance |
| Short call | Premium | Unlimited | Neutral/bearish |
| Short put | Premium | K − premium | Neutral/bullish |

## Moneyness

A call is **in the money** (ITM) if $S > K$, **at the money** (ATM) if $S \approx K$,
**out of the money** (OTM) if $S < K$ (reversed for puts). Premium = **intrinsic value**
(what you'd get exercising now) + **time value**.

## Put-call parity

For European options on a non-dividend stock:

$$C - P = S - K e^{-rT}$$

A call minus a put with the same strike behaves exactly like a forward contract. quantforge
uses this relation on live chains to infer the market's forward price and dividend yield.

## Strategies

Combine legs to shape risk: **covered call** (stock + short call — income, capped upside),
**protective put** (stock + long put — insurance), **spreads** (limit cost and payoff),
**straddle/strangle** (bet on movement), **iron condor** (bet on calm). Build them with live
premiums in the Strategy Builder; experiment below.

{{widget:payoff_lab}}

## Summary

Options are asymmetric bets: buyers risk the premium, sellers collect it and take the tail.
Payoff diagrams, break-evens and parity are the vocabulary for everything that follows.
