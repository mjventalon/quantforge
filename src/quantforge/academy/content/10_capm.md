---
id: 10
level: 3
level_name: Portfolio Construction
title: CAPM, alpha and factor models
minutes: 25
objectives:
  - Use CAPM to compute a required return
  - Estimate and judge alpha with its t-statistic
  - Decompose returns into factor exposures (size, value, momentum…)
widgets: [capm_regression_live, factor_live]
sources:
  - title: "Capital Asset Prices: A Theory of Market Equilibrium under Conditions of Risk, Journal of Finance 19(3), 1964"
    by: "William F. Sharpe (paper — Nobel Prize 1990)"
    url: ""
  - title: "Common Risk Factors in the Returns on Stocks and Bonds, Journal of Financial Economics 33(1), 1993"
    by: "Eugene F. Fama & Kenneth R. French (paper)"
    url: ""
  - title: "Kenneth R. French — Data Library (factor returns)"
    by: "Tuck School of Business, Dartmouth College"
    url: "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"
quiz:
  - q: "r_f = 4%, expected market return = 9%, beta = 1.2. CAPM required return?"
    options: ["9%", "10%", "10.8%", "13%"]
    answer: 1
    why: "4% + 1.2 × (9% − 4%) = 10%."
  - q: "In CAPM, which risk is rewarded with higher expected return?"
    options: ["Total volatility", "Systematic (beta) risk only", "Company-specific risk", "Liquidity of the stock"]
    answer: 1
    why: "Specific risk can be diversified away for free, so the model says it earns no premium."
  - q: "A fund's estimated alpha is +2%/year with t = 0.9. Best interpretation?"
    options: ["Proven skill", "Not statistically distinguishable from zero", "Negative skill", "Beta is 0.9"]
    answer: 1
    why: "|t| < 2: the alpha could easily be luck."
  - q: "In the Fama-French model, the 'value' factor (HML) is long:"
    options: ["High book-to-market stocks, short low book-to-market", "Large caps, short small caps", "Bonds, short stocks", "Winners, short losers"]
    answer: 0
    why: "HML = High minus Low book-to-market. SMB = Small minus Big. Momentum = winners minus losers."
  - q: "The security market line plots:"
    options: ["Volatility vs return", "Beta vs expected return", "Price vs time", "Correlation vs beta"]
    answer: 1
    why: "Assets above the SML earned more than their beta justifies (positive alpha)."
  - q: "A stock's regression on 5 factors has R² = 0.85. This means:"
    options: ["85% of its return variance is explained by the factors", "It will rise 85%", "Its alpha is 85%", "It has 85% correlation with gold"]
    answer: 0
    why: "Only 15% of its variance is stock-specific."
---

## CAPM

The Capital Asset Pricing Model (Sharpe 1964, Lintner 1965) says only **systematic** risk is
rewarded:

$$E[R_i] = r_f + \beta_i\,(E[R_m] - r_f)$$

**Example.** $r_f$ = 4%, $E[R_m]$ = 9%, β = 1.2 → $4\% + 1.2 \times 5\% = 10\%$.

Plot β against expected return: the straight line is the **security market line**. Points
above it outperformed their risk; points below underperformed.

## Alpha

Run the regression from chapter 7 on excess returns:

$$R_i - r_f = \alpha_i + \beta_i(R_m - r_f) + \varepsilon_i$$

$\alpha$ is the return not explained by market exposure — what active managers sell. Judge it
with its **t-statistic**: an alpha of +2% with t = 0.9 is indistinguishable from luck. Over
many funds, some will show high alphas purely by chance.

{{widget:capm_regression_live}}

## Factor models

Empirically, one beta is not enough. Fama and French (1993) added **size** (small minus big)
and **value** (high minus low book-to-market); later research added **momentum**,
**profitability/quality** and **low volatility**:

$$R_i - r_f = \alpha + \beta_{M}\,MKT + \beta_{S}\,SMB + \beta_{V}\,HML + \beta_{Mom}\,MOM + \dots + \varepsilon$$

The academic factors are long-short paper portfolios (Ken French's data library publishes
them). quantforge builds **tradable proxies** from ETFs (IWM − SPY for size, IWD − IWF for
value, MTUM − SPY for momentum…) so the analysis runs on live prices.

{{widget:factor_live}}

## Summary

CAPM prices beta; alpha is what is left and must be statistically significant to mean
anything; factor models explain much of what looks like skill.
