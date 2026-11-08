# 1 · Getting started & API keys

This tutorial installs quantforge, connects it to real market data and runs your first
analysis. Time: 10 minutes.

## 1.1 Install

You need Python 3.10 or newer.

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/quantforge
cd quantforge
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[all]"
```

Check:

```bash
python -c "import quantforge; print(quantforge.__version__)"
```

## 1.2 Choose a data provider

| Provider | Key needed | Free tier | Best for |
|---|---|---|---|
| **Yahoo Finance** (`yahoo`) | no | yes (personal use) | getting started, option chains, fundamentals |
| **Massive** (ex-Polygon.io, `polygon`) | yes | end-of-day stocks | clean adjusted history; options with a paid plan |
| **Financial Modeling Prep** (`fmp`) | yes | ~250 calls/day | fundamentals, history |
| **Alpha Vantage** (`alphavantage`) | yes | ~25 calls/day | quick history checks |
| **FRED** (rates) | optional | yes | US Treasury yields, used automatically |

Get keys at massive.com (formerly polygon.io), financialmodelingprep.com, alphavantage.co and
fred.stlouisfed.org (free sign-up for each).

## 1.3 Store your keys safely

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
QUANTFORGE_PROVIDER=polygon
POLYGON_API_KEY=your_key_here
```

quantforge reads `.env` from the folder you run Python from. The file is in `.gitignore`, so
it never ends up on GitHub. You can also pass a key directly:
`MarketData("polygon", api_key="...")`.

## 1.4 First real data

```python
from quantforge.data import MarketData

md = MarketData()            # uses QUANTFORGE_PROVIDER, else a keyed provider, else Yahoo
print(md)                    # MarketData(provider='yahoo')

aapl = md.history("AAPL", start="2023-01-01")
print(aapl.tail())
print(aapl.attrs)            # {'source': 'yahoo', 'fetched_at': '2026-...'}

print("Last price:", md.quote("AAPL"))
print("3M T-bill:", md.risk_free_rate("3M"))
print(md.yield_curve())
```

Every DataFrame keeps its **source** and **download time** in `.attrs`. If a ticker is wrong
or a provider is down, you get a `DataError` with the reason. quantforge never replaces
missing data with made-up numbers.

## 1.5 Several tickers at once

```python
prices = md.prices(["AAPL", "MSFT", "SPY"], start="2020-01-01")   # adjusted closes
daily = md.returns(["AAPL", "MSFT", "SPY"], start="2020-01-01")
weekly = md.returns(["AAPL", "MSFT", "SPY"], start="2020-01-01", frequency="W")
```

Rows where one ticker is missing are dropped so the result is ready for covariance work
(`dropna=False` keeps them).

## 1.6 Caching

Downloads are cached in `~/.cache/quantforge` for 6 hours so you do not burn API quota while
experimenting. Turn it off with `MarketData(cache=False)` or change `cache_ttl=` (seconds).

## 1.7 Launch the dashboard

```bash
quantforge-app
```

Your browser opens at `http://localhost:8501`. Next: [pricing options](02_option_pricing.md).
