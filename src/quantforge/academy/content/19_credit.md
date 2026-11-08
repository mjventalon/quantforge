---
id: 19
level: 5
level_name: Advanced Risk & Econometrics
title: Credit risk — default probability and scoring
minutes: 30
objectives:
  - Define PD, LGD, EAD and expected loss
  - Use the Merton model to compute distance to default from market data
  - Build and validate a logistic-regression scorecard (AUC, Gini, KS, calibration)
widgets: [merton_live, logit_demo]
sources:
  - title: "On the Pricing of Corporate Debt: The Risk Structure of Interest Rates, Journal of Finance 29(2), 1974"
    by: "Robert C. Merton (paper)"
    url: ""
  - title: "Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy, Journal of Finance 23(4), 1968"
    by: "Edward I. Altman (paper)"
    url: ""
  - title: "18.S096 — Lecture 26: Introduction to Counterparty Credit Risk"
    by: "MIT OpenCourseWare (Kempthorne, Lee, Strela, Xia)"
    url: "https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/"
quiz:
  - q: "PD = 2%, LGD = 40%, EAD = $1,000,000. Expected loss?"
    options: ["$20,000", "$8,000", "$400,000", "$800"]
    answer: 1
    why: "EL = PD × LGD × EAD = 0.02 × 0.4 × 1,000,000 = $8,000."
  - q: "In the Merton model, equity is viewed as:"
    options: ["A bond", "A call option on the firm's assets with strike = debt", "A put on the debt", "A forward"]
    answer: 1
    why: "Shareholders get max(V − D, 0) at maturity."
  - q: "Distance to default of 3.1 means:"
    options: ["The firm defaults in 3.1 years", "Assets are about 3.1 standard deviations above the default point", "PD = 3.1%", "Leverage is 3.1"]
    answer: 1
    why: "Risk-neutral PD = N(−DD) = N(−3.1) ≈ 0.1%."
  - q: "An AUC of 0.5 for a default model means:"
    options: ["Perfect ranking", "No better than random", "50% default rate", "Well calibrated"]
    answer: 1
    why: "AUC = probability a random defaulter is scored riskier than a random non-defaulter; 0.5 = coin flip."
  - q: "Gini coefficient relates to AUC by:"
    options: ["Gini = AUC", "Gini = 2·AUC − 1", "Gini = 1 − AUC", "Gini = AUC²"]
    answer: 1
    why: "AUC 0.8 → Gini 0.6."
  - q: "A model ranks borrowers well (AUC 0.85) but predicts 2% PD for a group that actually defaults at 8%. It is:"
    options: ["Perfect", "Discriminating but poorly calibrated", "Calibrated but not discriminating", "Overfitted by definition"]
    answer: 1
    why: "Ranking (discrimination) and level accuracy (calibration) are different properties; check both."
---

## The building blocks

$$\text{Expected Loss} = PD \times LGD \times EAD$$

- **PD** — probability of default over a horizon,
- **LGD** — loss given default (1 − recovery rate),
- **EAD** — exposure at default.

**Example.** PD 2%, LGD 40%, EAD \$1M → EL = **\$8,000**.

## Structural model: Merton (1974)

Shareholders own the firm's assets $V$ but must repay debt $D$ at $T$. At maturity they get
$\max(V_T - D, 0)$ — **equity is a call option on the assets**. Using Black-Scholes, the
observed market cap $E$ and equity volatility $\sigma_E$ give two equations:

$$E = V N(d_1) - D e^{-rT}N(d_2), \qquad \sigma_E E = N(d_1)\,\sigma_V V$$

Solve for the unobservable $V$ and $\sigma_V$. Then

$$DD = d_2 = \frac{\ln(V/D) + (r - \tfrac12\sigma_V^2)T}{\sigma_V\sqrt T}, \qquad PD_{RN} = N(-DD)$$

**Example.** Market cap \$4bn, equity vol 40%, default point \$6bn, $r$ = 4%, 1 year →
$V \approx \$9.76$bn, $\sigma_V \approx 16.4\%$, **DD ≈ 3.13**, PD ≈ 0.09%. The KMV convention
sets the default point at short-term debt + ½ long-term debt. Use Merton PDs to **rank** and
**monitor**; they are not ratings.

{{widget:merton_live}}

## Statistical scoring

Banks also estimate PD from borrower data with **logistic regression**:

$$P(\text{default}) = \frac{1}{1 + e^{-(\beta_0 + \beta_1 x_1 + \dots)}}$$

Validate on data not used for fitting:

- **Discrimination**: AUC (0.5 random, 1 perfect), Gini = 2·AUC − 1, KS statistic.
- **Calibration**: predicted vs observed default rates by bucket.
- **Stability** and **information value** of predictors.

The classic **Altman Z-score** (1968) combines five accounting ratios: above 2.99 "safe",
1.81–2.99 "grey", below 1.81 "distress" (calibrated on manufacturers).

{{widget:logit_demo}}

## Summary

Credit risk = probability × severity × exposure. Merton reads default risk from equity
markets; scorecards learn it from borrower data. Always validate discrimination *and*
calibration.
