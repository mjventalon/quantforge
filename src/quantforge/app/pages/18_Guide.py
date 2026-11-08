import streamlit as st

from quantforge.app.common import page_setup

page_setup("Guide", "📘")

st.markdown("""
**New here? Start with this page.** Every tool in quantforge explained in plain English:
*what it is*, *when to use it*, *how to read it*. No maths needed.

> 🖱️ **On every chart:** scroll to **zoom**, click-and-drag to **move**, double-click to
> **reset**, hover for exact values, camera icon to **save** a picture.
""")

GUIDE = {
    "🚀 Getting started": """
**1. Pick a data source** in the left sidebar. *Yahoo Finance* is free and needs no key.
If you have a key for Massive (Polygon), FMP or Alpha Vantage, choose it and paste the key.

**2. Test the connection** on the Home page (*Connection check*).

**3. Type a ticker.** Start typing the first letters or the company name (`app` → Apple
AAPL) and pick from the suggestions. Not in the list? Type the exact symbol and press Enter, or
switch to *Search Yahoo* to look up any listed instrument worldwide (`MC.PA`, `7203.T`…).

**Good to know**
- Every number comes from a real source. If something can't be downloaded, you see an error —
  never a made-up value.
- Data is cached for a while, so pages reload fast.
- Free quotes can be delayed 15+ minutes.
""",
    "⚡ Live market": """
**What it is:** an intraday chart that **refreshes by itself** (every 5–60 s, you choose) and a
board of live mini-charts for major markets.

**How it works:** the app asks the data source for the latest 1-, 5- or 15-minute bars at each
refresh. Your zoom is kept between refreshes.

**Good to know:** free data is **delayed** (often 15 min for stocks) and only moves while the
market is open. Crypto (`BTC-USD`) trades 24/7 — perfect to see it move.
""",
    "🧪 Strategy Lab": """
**What it is:** run **many strategies on many assets at once**, then build one diversified
book from the best combination.

| Tab | What it shows |
|---|---|
| **Leaderboard** | Every strategy × asset ranked by Sharpe, return, drawdown, after costs |
| **Auto-build portfolio** | Picks strategies one by one to maximise **diversity** or Sharpe; diversity score A–D and a correlation map (green = diversifying, red = redundant) |
| **Robustness** | Performance in separate time **folds**, and a **Monte-Carlo of the trades** (shuffles the real trades thousands of times: how much was luck?) |
| **Parameter landscape** | A 3-D surface of Sharpe over two parameters — a broad plateau is robust, a lonely spike is overfitting |
| **Export code** | A standalone Python script that reproduces the backtest |
""",
    "🌀 Regimes & 3-D": """
**Regimes:** a Hidden Markov Model finds hidden market "moods" (calm / turbulent) from returns
alone. *Filtered* probabilities only use past data (what you could have known); *smoothed*
ones use the whole sample (for analysis only).

**Distribution surface:** a 3-D landscape of how the **distribution of returns** changed over
time — a tall narrow ridge = calm, a low wide one = stress.

**Live 3-D:** the same surface on today's intraday returns, updated every 30 seconds.
""",
    "🤖 AI copilot": """
**What it is:** an assistant in the left sidebar that knows the page you are on. Connect
**Claude**, **ChatGPT** or **Gemini** with your own API key.

**Permissions — you choose:**

| Mode | What the AI can do |
|---|---|
| Explain only | Answers questions: what a field means, how to read a result |
| Suggest — I approve | Proposes values and buttons; nothing changes until you press **Apply** |
| Autopilot | Fills the fields, presses the buttons, opens other pages, then explains |

You also tick **"I allow … to read this page"** for each AI: until then nothing is sent.

**What is sent:** the page's field names, current values and displayed results, plus your
messages. Never your API keys or passwords. Delete, reset and download buttons are never
available to the AI.

**Keys:** Claude → console.anthropic.com · ChatGPT → platform.openai.com · Gemini →
aistudio.google.com. API use is billed by each company separately from their chat
subscriptions. On your computer you can put them in `.env` (`ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`, `GEMINI_API_KEY`).

AI answers can be wrong — check the numbers on the page.
""",
    "💼 Paper trading": """
**What it is:** a trading simulator with **virtual money** (default $1,000,000) on **real
prices**. Your accounts are **saved**: close the app, come back tomorrow, everything is there.

**Orders:** market, limit, stop, stop-limit, trailing stop · buy, sell, **sell short** (150 %
margin, like Regulation T) · *good till cancelled* or *day* · cancel any open order.

**How fills work:** an order executes on the **next real price update** after you send it.
Outside market hours it waits for the next session — exactly like a broker queues it. Limit
orders fill at your limit or better; slippage and commissions are configurable (⚙️ Account).

**The board:** choose your widgets — order ticket, live chart with your trades, positions,
watchlist, equity curve vs SPY, allocation, VaR/ES, GARCH volatility, market regime,
strategy signals, **invest in a model portfolio** (equal weight, minimum variance, max
Sharpe, risk parity) and performance stats.

**Account code:** in ⚙️ Account. Keep it private; type it on another device to open the same
accounts. No real money, no order ever reaches an exchange.
""",
    "🧠 Heston · SABR · jumps": """
**What it is:** three professional option models **fitted to the live option chain**.

| Model | Idea | Used for |
|---|---|---|
| **SABR** | each expiry has its own smile (α level, ρ skew, ν curvature) | quoting smiles, rates & FX desks |
| **Heston** | volatility itself moves randomly and mean-reverts | one consistent surface for all maturities |
| **Merton jumps** | Black-Scholes + sudden jumps | crash risk, short-dated skew |

**Read it:** dots = market, lines = models. RMSE is the average error in volatility points.
Move the Heston sliders to see what each parameter does to the 3-D surface.
""",
    "⚙️ C++ engine": """
**What it is:** quantforge's pricing core rewritten in **C++17** and running on all CPU cores.

**Use it to:** price huge batches (whole option chains, millions of Monte-Carlo paths) fast.
The page benchmarks C++ against Python **on real inputs** and shows both results side by side.

**Build it once** with the button (or `quantforge-build-native` in the terminal). On a Mac,
install the compiler first: `xcode-select --install`.
""",
    "🎓 Academy & Code Lab": """
**Academy:** 23 chapters in 7 levels — from *what is a stock* to GARCH, VaR, regimes and
writing a C++ pricing engine. Each chapter has a lesson, live tools, coding exercises, a quiz
(80 % to pass) and a **certificate** with a verifiable ID.

**Your name** is entered once at the top of the Academy and remembered on your device; press
*Change* to edit it.

**Code Lab:** every "rewrite it yourself" exercise in one place, in **Python** and **C++**.
Python runs in your browser on the website; on your own computer (`quantforge-app`) both
languages are graded automatically.

**Verify a certificate:** anyone can check a certificate ID + name on the *Verify* page.
""",
    "🌡️ Market pulse": """
**What it is:** a heatmap of how sectors, asset classes or your watchlist performed over
1 day, 1 week, 1 month… up to 3 years.

**Use it to:** see in 5 seconds what is leading and lagging the market.

**How to read it:** green = gained, red = lost. Darker = bigger move. The ranking chart sorts
everything from best to worst for the period you pick.
""",
    "📊 Stock analysis": """
**What it is:** a full chart of one asset with the classic technical indicators.

| Indicator | What it tells you |
|---|---|
| **Moving averages** (50, 200 days) | Trend. Price above the 200-day line ≈ uptrend. 50 crossing above 200 = "golden cross". |
| **Bollinger bands** | Normal range of the price. Touching the bands = unusual move. |
| **RSI** (0–100) | Speed of recent moves. Above 70 = overbought, below 30 = oversold. |
| **MACD** | Momentum. MACD line crossing above the signal line = momentum turning up. |
| **Volume** | How much was traded. Big moves on big volume are more meaningful. |

**Signals today** turns these into simple sentences. They describe the chart; they are not
predictions.

Tabs below: performance stats (return, Sharpe, drawdown), 6 ways to measure volatility, the
**volatility cone** (is today's volatility high or low versus history?) and the US Treasury
yield curve.
""",
    "🧮 Options pricer": """
**What it is:** prices a real listed option with three models and compares with the market.

**Steps:** ticker → expiry → call/put → strike → American (US stocks) or European.

**How to read it**
- **Market mid** = middle of bid and ask: what the option really trades at.
- **Black-Scholes / Binomial / Monte-Carlo** = model values using the volatility you chose.
  With *Market implied* volatility they match the market by construction; switch to
  *Historical* to see if options look expensive (model < market) or cheap.
- **Implied vol** = the volatility the market is pricing in.

**Greeks** (how the price reacts):
- **Delta**: change for a $1 move in the stock (≈ probability-like for calls, 0 to 1).
- **Gamma**: how fast delta changes.
- **Vega**: change for +1 point of volatility.
- **Theta**: value lost per day just from time passing.
- **Rho**: change for +1% interest rates.

**Open interest & expected move tab**
- **Expected move**: how much the market expects the stock to move by expiry.
- **Call wall / put wall**: strikes with the most open contracts.
- **Put/call ratio** above 1 = more protection being held.
""",
    "🌋 Volatility surface": """
**What it is:** the implied volatility of every strike and expiry, in 2-D (smiles) and 3-D.

**Why it matters:** the market does *not* use one volatility. For indices, low strikes cost
more (crash insurance) → the **skew**. Short-dated vol above long-dated vol = market stress.

**How to read it:** each curve = one expiry. The 3-D surface can be rotated with the mouse.
The table gives the at-the-money volatility for each expiry (the **term structure**).
""",
    "🧩 Strategy builder": """
**What it is:** build multi-leg option trades (spreads, straddles, iron condors…) with real
prices.

**Steps:** choose a template, then edit the table: strike, quantity (**+** buy, **−** sell).
Add or delete rows freely.

**How to read the chart:** green area = profit at expiry, red area = loss. Black diamonds =
**break-even** prices. The dashed line = what the position is worth *today*.
""",
    "🎯 Portfolio": """
**What it is:** finds the best mix of assets for the risk you take (Nobel-prize Markowitz
theory).

- **Frontier**: each dot is a possible portfolio. The blue line is the best possible return for
  each level of risk. ★ **Max Sharpe** = best return per unit of risk.
- **Weights & risk**: how much to hold, and how much *risk* each asset brings (often very
  different from its weight).
- **CAPM**: **beta** = how much an asset moves with the market (1.5 = 50% more). **Alpha** =
  return not explained by the market (check the p-value: below 0.05 = statistically real).
- **Factors**: what drives each asset — market, small vs large, value vs growth, momentum,
  quality, low volatility, interest rates.
- **Black-Litterman**: start from the market's own view and add yours ("JPM beats XOM by 3%")
  with a confidence level.

⚠️ Expected returns come from the past and are very noisy. Test ideas in the **Backtester**.
""",
    "🌱 Wealth simulator": """
**What it is:** "If I invest $X now and $Y every month, what could I have in N years?"

**How it works:** it replays real months of your portfolio's history in random order,
thousands of times, so real crashes and recoveries are included.

**How to read it:** the middle line is the typical result; the light band holds 90% of
outcomes. Turn on *Today's dollars* to remove inflation (latest US CPI).
""",
    "🔁 Backtester": """
**What it is:** tests a trading rule on real history, honestly.

**Strategies**
- **SMA crossover**: own when the short average is above the long one (follow the trend).
- **Time-series momentum**: own when the last 12 months were positive.
- **RSI / Bollinger mean reversion**: buy after sharp drops, sell after recoveries.
- **Volatility targeting**: hold more when markets are calm, less when they are wild.

**Honesty rules built in:** decisions use only past data; trading costs are charged.

**Parameter search:** finds the best settings on the first 60% of history, then shows how
they did on the last 40%. If test results collapse, the "best" settings were luck.

**Walk-forward portfolio:** re-optimizes every month with only past data — the real-life
test of the Portfolio page.
""",
    "🔗 Pairs trading": """
**What it is:** a market-neutral strategy on two related assets (e.g. Coca-Cola and Pepsi).

**Idea:** when the price gap gets unusually wide, bet that it closes: sell the expensive one,
buy the cheap one.

**How to read it**
- **Cointegration p-value** below 0.05 = the gap has historically closed (good candidate).
- **Half-life** = typical days for the gap to close halfway.
- **z-score** = how stretched the gap is: red zone → short the spread, green zone → long the
  spread, grey zone → close.
""",
    "🛡️ Risk": """
**What it is:** how much could I lose, and in which scenarios?

- **VaR 99%** = a loss you should not exceed on 99 days out of 100.
- **ES** (Expected Shortfall) = the *average* loss on the worst 1 day in 100. More honest about
  disasters.
- **Contributions**: which asset brings the most risk.
- **Backtest**: was the VaR right in the past? 🟢 green zone = yes.
- **Historical stress**: what your portfolio would have done in 1987, 2000, 2008, Covid 2020,
  2022, SVB 2023, April 2025… using real prices. *(\\*) = asset didn't exist yet, estimated
  from its beta.*
""",
    "〰️ Time series": """
**What it is:** statistics on the behaviour of returns over time.

- **ADF test**: prices wander randomly (not stationary); daily returns don't.
- **ACF**: returns have almost no memory (hard to predict)… but **squared returns** do:
  calm and stormy periods cluster.
- **ARMA**: a model to forecast returns. Expect wide intervals — that's honest.
- **GARCH**: a model of volatility. Gives today's volatility, its long-run level, how fast it
  goes back (half-life) and a forecast you can compare with option implied volatility.
""",
    "🏦 Credit": """
**What it is:** how likely is a company to default?

- **Merton / KMV**: treats the company's stock as an option on its assets. Uses the market cap,
  the stock's volatility and the debt from the latest filing. **Distance to default** = how many
  "standard deviations" the company is from default. Bigger = safer.
- **Altman Z-score**: accounting score. Above 2.99 safe, 1.81–2.99 grey zone, below 1.81
  distress.
- **PD model**: upload your own loan data (CSV) to train and test a logistic regression.
  **AUC** above 0.7 = useful model; **calibration** checks predicted vs real default rates.
""",
    "❓ FAQ": """
**A page shows a red error.** The data source could not deliver that data (wrong ticker, no
options, rate limit, provider down). quantforge shows the error instead of guessing.

**Numbers differ from my broker.** Free data can be delayed; option mids move fast; models
use the inputs shown at the top of each page.

**Can I use this to trade?** It is a research and learning tool. Nothing here is investment
advice.

**Where is the code?** On GitHub — every model has its formula and references in the source.
""",
}

left, right = st.columns([1, 3])
topic = left.radio("Topic", list(GUIDE), label_visibility="collapsed", key="guide_topic")
with right, st.container(border=True):
    st.markdown(f"### {topic}")
    st.markdown(GUIDE[topic])
