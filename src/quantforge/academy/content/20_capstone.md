---
id: 20
level: 6
level_name: Capstone
title: Capstone — run a complete quantitative research project
minutes: 90
objectives:
  - Formulate a falsifiable research question
  - Execute data, model, backtest, risk and robustness steps with quantforge
  - Write a short, honest research note
widgets: [capstone_checklist]
sources:
  - title: "18.S096 — final paper requirement and case studies"
    by: "MIT OpenCourseWare (Kempthorne, Lee, Strela, Xia)"
    url: "https://ocw.mit.edu/courses/18-s096-topics-in-mathematics-with-applications-in-finance-fall-2013/"
  - title: "Kenneth R. French — Data Library (to compare with academic factors)"
    by: "Tuck School of Business, Dartmouth College"
    url: "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"
quiz:
  - q: "Which is a falsifiable research question?"
    options: ["Is trading good?", "Did a 12-1 momentum rule on sector ETFs beat equal weight after 5 bps costs, out of sample 2015–2025?", "Will NVDA go up?", "Is the market efficient?"]
    answer: 1
    why: "It specifies data, rule, benchmark, costs and test period — it can be proven wrong."
  - q: "The correct order of a research project is:"
    options: ["Backtest, then choose the question", "Question → data → method → in-sample design → out-of-sample test → risk & robustness → write-up", "Write-up first", "Optimize until Sharpe > 2"]
    answer: 1
    why: "Decide what would refute you before looking at results."
  - q: "Your strategy's out-of-sample Sharpe is 0.3 vs 1.8 in-sample. The honest write-up:"
    options: ["Reports only in-sample", "Reports both and discusses likely overfitting", "Changes the test period until it works", "Hides the test"]
    answer: 1
    why: "Negative results are results. Reporting them is what makes research credible."
  - q: "Which robustness check is most informative?"
    options: ["Running the same backtest twice", "Varying parameters, periods, markets and costs", "Using more decimals", "Changing chart colors"]
    answer: 1
    why: "A real effect should survive reasonable variations."
  - q: "A Monte-Carlo resampling of trades shows P(profit) = 62%. This suggests:"
    options: ["A highly reliable edge", "Results depend substantially on luck and trade ordering", "No risk", "The strategy is guaranteed"]
    answer: 1
    why: "A robust edge should be profitable in the large majority of resampled sequences."
---

## The project

Choose **one** question and answer it end to end with real data. Examples:

- Does time-series momentum on sector ETFs beat equal weighting **out of sample**, after costs?
- How did a 60/40 portfolio's Expected Shortfall change across volatility regimes since 2005?
- Is the skew of SPY options a useful signal for next-month realized volatility?
- Which of KO/PEP, XOM/CVX, GLD/GDX is cointegrated, and does a pairs rule survive costs?

## The protocol

1. **Question & hypothesis** — write what result would *refute* you, before testing.
2. **Data** — tickers, period, provider; note survivorship and missing data.
3. **Method** — model or rule, parameters, costs, benchmark.
4. **In-sample design** — choose parameters on the first part only.
5. **Out-of-sample test** — untouched period or walk-forward.
6. **Risk** — drawdown, VaR/ES, stress scenarios, regime breakdown.
7. **Robustness** — vary parameters, markets, periods and costs; Monte-Carlo of trades.
8. **Write-up** — one page: question, data, method, results (including failures), limits.

Use the Backtester, Strategy Lab, Regimes, Risk and Portfolio pages; export CSVs and charts
for your note.

{{widget:capstone_checklist}}

## What a good note looks like

Short, specific, reproducible: someone else could rerun it from your description. It reports
uncertainty (t-stats, confidence intervals, out-of-sample results) and limitations. It makes
no promise about future returns.

## Summary

Research is a disciplined argument with data. The habits from this course — real data, no
look-ahead, costs, out-of-sample tests, honest reporting — are what separate quantitative
research from storytelling.
