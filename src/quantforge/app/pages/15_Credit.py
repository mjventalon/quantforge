from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

from quantforge.app.common import (
    cached_fundamentals,
    guard,
    history,
    page_setup,
    pct,
    risk_free,
    ticker_input,
)
from quantforge.credit import (
    altman_z_score,
    calibration_table,
    classification_report,
    kmv_default_point,
    logistic_regression,
    merton_model,
    roc_curve,
    woe_iv,
)
from quantforge.viz import calibration_chart, roc_chart

HOW_TO = """1. **Merton/KMV**: type a company ticker. Market cap and debt come from its latest filing; the model turns them into a **distance to default** and a probability of default.
2. **Altman Z**: classic accounting score — safe / grey / distress zone.
3. **PD model**: upload your own loan CSV with a 0/1 default column to fit and validate a logistic regression."""

page_setup("Credit risk", "🏦", HOW_TO)
prov = st.session_state.get("provider", "yahoo")
tabs = st.tabs(["Merton / KMV (listed company)", "Altman Z-score", "PD model on your data"])

with tabs[0]:
    ticker = ticker_input(default="F")
    f = guard(cached_fundamentals, prov, ticker, what="fundamentals")
    hist = history(ticker, date.today().replace(year=date.today().year - 1), date.today())
    sig_e = float(np.log(hist["adj_close"]).diff().std() * np.sqrt(252))
    rf = risk_free("1Y")
    st.markdown(f"**{f.get('name') or ticker}** · {f.get('sector') or ''} · fiscal "
                f"{f.get('fiscal_date')} · currency {f.get('currency')} · source {f['source']}")
    c = st.columns(4)
    e_val = c[0].number_input("Equity value (market cap)", value=float(f["market_cap"] or 0.0),
                              format="%.0f")
    std = c[1].number_input("Short-term debt", value=float(f["short_term_debt"] or 0.0),
                            format="%.0f")
    ltd = c[2].number_input("Long-term debt", value=float(f["long_term_debt"] or 0.0),
                            format="%.0f")
    sig_in = c[3].number_input("Equity vol (1y realized, %)", value=round(sig_e * 100, 2)) / 100
    missing = [k for k in ("market_cap", "short_term_debt", "long_term_debt") if f.get(k) is None]
    if missing:
        st.warning(f"Not reported by the provider: {', '.join(missing)}. Fill them from the "
                   "company's latest 10-K/10-Q.")
    dp = kmv_default_point(std, ltd)
    if e_val <= 0 or dp <= 0:
        st.info("Need a positive market cap and debt to run the model.")
    else:
        res = merton_model(e_val, sig_in, dp, rf, 1.0)
        m = st.columns(5)
        m[0].metric("Distance to default", f"{res.distance_to_default:.2f} σ")
        m[1].metric("1y PD (risk-neutral)", pct(res.default_probability, 3))
        m[2].metric("Asset value", f"{res.asset_value / 1e9:,.1f} bn")
        m[3].metric("Asset vol", pct(res.asset_vol))
        m[4].metric("Implied credit spread", f"{res.credit_spread * 1e4:,.0f} bp")
        st.caption(f"Default point = STD + ½ LTD = {dp:,.0f} · r = {pct(rf)} (FRED 1Y) · "
                   f"{'converged' if res.converged else 'solver did NOT fully converge'}. "
                   "Merton PDs are model outputs, best used to rank firms; they are not "
                   "ratings.")
        vols = np.linspace(max(0.05, sig_in * 0.5), sig_in * 2, 40)
        dds = [merton_model(e_val, v, dp, rf).distance_to_default for v in vols]
        st.line_chart(pd.DataFrame({"distance to default": dds}, index=np.round(vols * 100, 1)),
                      x_label="Equity vol (%)")

with tabs[1]:
    st.markdown("Original Altman (1968) model for public manufacturers.")
    keys = ["working_capital", "retained_earnings", "ebit", "market_cap", "revenue",
            "total_assets", "total_liabilities"]
    vals = {k: f.get(k) for k in keys}
    edit = st.data_editor(pd.DataFrame({"value": vals}), width="stretch",
                          key=f"altman_{ticker}")
    v = edit["value"]
    if v.isna().any() or (v[["total_assets", "total_liabilities"]] <= 0).any():
        st.warning("Some items are missing — fill them from the latest annual report.")
    else:
        z = altman_z_score(v["working_capital"], v["retained_earnings"], v["ebit"],
                           v["market_cap"], v["revenue"], v["total_assets"],
                           v["total_liabilities"])
        icon = {"safe": "🟢", "grey": "🟡", "distress": "🔴"}[z["zone"]]
        st.metric("Z-score", f"{z['z_score']:.2f}", f"{icon} {z['zone']} zone")
        st.dataframe(pd.DataFrame({k: [z[k]] for k in ("x1", "x2", "x3", "x4", "x5")}),
                     hide_index=True)

with tabs[2]:
    st.markdown("Upload **your own** loan-level CSV with a 0/1 default column. The model is "
                "fitted by maximum likelihood (logistic regression) and validated on a hold-out "
                "sample.")
    up = st.file_uploader("CSV file", type=["csv"])
    if up is None:
        st.info("Public datasets you can use: Lending Club loan data, the UCI "
                "'Default of Credit Card Clients' dataset, or Freddie Mac single-family loans.")
        st.stop()
    data = pd.read_csv(up)
    st.dataframe(data.head(), width="stretch")
    target = st.selectbox("Default column (0/1)", data.columns)
    numeric = [c for c in data.select_dtypes("number").columns if c != target]
    feats = st.multiselect("Predictors", numeric, numeric[: min(6, len(numeric))])
    if not feats:
        st.stop()
    d = data[[target] + feats].dropna()
    standardize = st.checkbox("Standardize predictors", True)
    X = d[feats]
    if standardize:
        X = (X - X.mean()) / X.std()
    test_share = st.slider("Hold-out share", 0.1, 0.5, 0.3)
    rng = np.random.default_rng(42)
    test = rng.random(len(d)) < test_share
    fit = logistic_regression(d.loc[~test, target], X[~test], l2=st.number_input("L2 penalty",
                                                                                   0.0, 100.0,
                                                                                   0.0))
    st.dataframe(fit.summary().style.format("{:.4f}"), width="stretch")
    st.write(f"Pseudo-R² {fit.pseudo_r2:.3f} · AIC {fit.aic:,.1f} · n = {fit.n_obs} · "
             f"{'converged' if fit.converged else 'not converged'}")
    p_test = fit.predict_proba(X[test])
    y_test = d.loc[test, target].to_numpy()
    rep = classification_report(y_test, p_test, st.slider("Decision threshold", 0.01, 0.99, 0.5))
    m = st.columns(5)
    m[0].metric("AUC (hold-out)", f"{rep.auc:.3f}")
    m[1].metric("Gini", f"{rep.gini:.3f}")
    m[2].metric("KS", f"{rep.ks:.3f}")
    m[3].metric("Brier", f"{rep.brier:.4f}")
    m[4].metric("Recall", pct(rep.recall, 1))
    fpr, tpr, _ = roc_curve(y_test, p_test)
    c1, c2 = st.columns(2)
    c1.plotly_chart(roc_chart(fpr, tpr, rep.auc), width="stretch")
    c2.plotly_chart(calibration_chart(calibration_table(y_test, p_test)),
                    width="stretch")
    st.dataframe(rep.confusion, width="stretch")
    iv = {c: woe_iv(d[c], d[target])[1] for c in feats}
    st.markdown("**Information value per predictor**")
    st.bar_chart(pd.Series(iv).sort_values(ascending=False))
