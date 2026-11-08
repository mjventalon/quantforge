---
id: 8
level: 2
level_name: Risk & Statistics
title: Interest rates, bonds and the yield curve
minutes: 25
objectives:
  - Discount future cash flows (present value)
  - Price a bond and explain why bond prices fall when yields rise
  - Read the Treasury yield curve and know what an inversion is
widgets: [bond_calculator, live_yield_curve]
sources:
  - title: "15.401 Finance Theory I — Present Value Relations; Fixed-Income Securities"
    by: "Andrew W. Lo — MIT OpenCourseWare"
    url: "https://ocw.mit.edu/courses/15-401-finance-theory-i-fall-2008/"
  - title: "18.S096 — Lecture on interest rates (price-yield relationship, bootstrapping the yield curve)"
    by: "MIT OpenCourseWare (Kempthorne, Lee, Strela, Xia)"
    url: "https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/"
  - title: "Federal Reserve Economic Data (FRED) — Treasury constant-maturity yields"
    by: "Federal Reserve Bank of St. Louis"
    url: "https://fred.stlouisfed.org/"
quiz:
  - q: "What is $100 received in 5 years worth today at a 5% annual discount rate?"
    options: ["$95.00", "$78.35", "$75.00", "$127.63"]
    answer: 1
    why: "PV = 100 / 1.05^5 = $78.35."
  - q: "A bond's yield rises. Its price:"
    options: ["Rises", "Falls", "Does not change", "Doubles"]
    answer: 1
    why: "Price = present value of fixed cash flows; a higher discount rate lowers it."
  - q: "A 10-year bond pays a 4% annual coupon. If market yields are 4%, it trades at about:"
    options: ["Par (100)", "Below par", "Above par", "Zero"]
    answer: 0
    why: "When coupon rate = yield, the bond prices at par."
  - q: "Same bond, but yields are 5%. Its price is closest to:"
    options: ["100.00", "96.04", "92.28", "105.00"]
    answer: 2
    why: "Σ 4/1.05^t (t=1..10) + 100/1.05^10 = 92.28."
  - q: "An 'inverted' yield curve means:"
    options: ["Long-term yields are above short-term yields", "Short-term yields are above long-term yields", "All yields are zero", "Bonds pay no coupons"]
    answer: 1
    why: "Normally long yields exceed short ones. Inversion (e.g. 2-year above 10-year) has preceded many US recessions, though not with a fixed lag."
  - q: "Which bond is more sensitive to a 1% rise in yields?"
    options: ["A 2-year bond", "A 30-year bond", "Both equally", "Neither"]
    answer: 1
    why: "Longer maturity → higher duration → larger price change for a given yield move."
---

## Time value of money

A dollar today is worth more than a dollar tomorrow because it can earn interest.

$$PV = \frac{CF_T}{(1+y)^T}, \qquad FV = PV(1+y)^T$$

**Example.** \$100 in 5 years at 5%: $100/1.05^5 = \$78.35$.

## Pricing a bond

A bond is a list of fixed cash flows. Its price is their present value at the market yield
$y$:

$$P = \sum_{t=1}^{T}\frac{C}{(1+y)^t} + \frac{F}{(1+y)^T}$$

**Example.** 10-year, 4% annual coupon, face 100:

| Yield | Price |
|---|---|
| 4.0% | 100.00 (par) |
| 4.5% | 96.04 |
| 5.0% | 92.28 |

Price and yield move in **opposite directions**. The sensitivity is the **duration**: longer
bonds lose more when yields rise. (2022 was a painful lesson for long-bond holders.)

{{widget:bond_calculator}}

## The yield curve

Plot the yields of government bonds against maturity (1 month → 30 years) and you get the
**yield curve**. Normally it slopes **upward** (investors want more to lend for longer).
When short yields exceed long yields the curve is **inverted** — historically a warning sign
that has preceded many US recessions, though with variable timing and false alarms.

The short end is anchored by the central bank's policy rate; the long end reflects expected
future rates, inflation and a term premium. quantforge uses the **3-month Treasury yield**
as the risk-free rate $r_f$ in Sharpe ratios, CAPM and option pricing, interpolating the curve
for other maturities.

{{widget:live_yield_curve}}

## Summary

Discounting turns future cash into today's value. Bond prices fall when yields rise, more so
for long maturities. The yield curve summarizes the price of money across horizons and feeds
every model in quantforge as the risk-free rate.
