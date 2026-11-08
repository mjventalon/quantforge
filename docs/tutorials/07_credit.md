# 7 · Credit risk: Merton/KMV, Altman Z and PD models

## 7.1 Merton: default risk from the stock market

Equity is a call option on the firm's assets with strike = debt. From the observed market
cap and equity volatility we solve for the hidden asset value and asset volatility, then get
the **distance to default** (how many standard deviations the assets are above the debt).

```python
import numpy as np
from quantforge.data import MarketData
from quantforge.credit import merton_model, kmv_default_point

md = MarketData("yahoo")
t = "F"
f = md.fundamentals(t)          # latest annual filing; missing items are None
print({k: f[k] for k in ("name", "fiscal_date", "market_cap", "short_term_debt",
                         "long_term_debt")})

px = md.history(t, start=str(np.datetime64("today") - np.timedelta64(365, "D")))
sigma_e = np.log(px["adj_close"]).diff().std() * np.sqrt(252)
debt = kmv_default_point(f["short_term_debt"], f["long_term_debt"])   # STD + ½ LTD
res = merton_model(f["market_cap"], sigma_e, debt, md.risk_free_rate("1Y"))
print(res)
```

If the provider does not report an item, quantforge returns `None` and you fill it in from
the company's 10-K. It is never estimated silently.

Use Merton PDs to **rank** companies and follow trends. Absolute levels are model outputs,
not ratings. Financial firms (banks) do not fit the model well because deposits are not
"debt" in the same sense.

## 7.2 Altman Z-score

```python
from quantforge.credit import altman_z_score
z = altman_z_score(f["working_capital"], f["retained_earnings"], f["ebit"],
                   f["market_cap"], f["revenue"], f["total_assets"], f["total_liabilities"])
print(z)   # zone: safe > 2.99, grey 1.81–2.99, distress < 1.81
```

Designed for public manufacturers; interpret with care for other sectors.

## 7.3 Logistic regression PD model on loan data

Use a real loan-level dataset (examples: Lending Club loan data, UCI "Default of Credit Card
Clients", Freddie Mac single-family). Columns: one 0/1 default flag plus borrower features.

```python
import pandas as pd
from quantforge.credit import (logistic_regression, classification_report, roc_curve,
                               calibration_table, woe_iv)
from quantforge.viz import roc_chart, calibration_chart

df = pd.read_csv("loans.csv")                        # your file
features = ["dti", "fico", "revol_util", "annual_inc"]
d = df[["default"] + features].dropna()
X = (d[features] - d[features].mean()) / d[features].std()

train = d.sample(frac=0.7, random_state=0).index
test = d.index.difference(train)
model = logistic_regression(d.loc[train, "default"], X.loc[train])
print(model.summary())        # coefficients, z-tests, p-values, odds ratios

p = model.predict_proba(X.loc[test])
rep = classification_report(d.loc[test, "default"], p)
print(f"AUC {rep.auc:.3f}  Gini {rep.gini:.3f}  KS {rep.ks:.3f}")

fpr, tpr, _ = roc_curve(d.loc[test, "default"], p)
roc_chart(fpr, tpr, rep.auc).show()
calibration_chart(calibration_table(d.loc[test, "default"], p)).show()
```

* **AUC / Gini / KS** measure ranking power (Gini > 0.5 is good for retail credit).
* **Calibration** checks that a predicted 5% PD really defaults about 5% of the time.
* **Information value** (`woe_iv`) screens predictors before modelling.

Next: [the dashboard](08_dashboard.md).
