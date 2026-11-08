---
id: 4
level: 1
level_name: Market Foundations
title: Reading a price chart
minutes: 25
objectives:
  - Read candlesticks (open, high, low, close) and volume
  - Choose a timeframe and a linear or logarithmic scale
  - Interpret moving averages, RSI and Bollinger bands — and their limits
widgets: [candle_reader, indicator_lab]
sources:
  - title: "New Concepts in Technical Trading Systems (1978) — origin of RSI and ATR"
    by: "J. Welles Wilder Jr. (book)"
    url: ""
  - title: "Bollinger on Bollinger Bands (2001)"
    by: "John Bollinger (book)"
    url: ""
  - title: "ECON 252 Financial Markets — lectures on efficient markets and behavioral finance"
    by: "Robert J. Shiller — Yale University (Open Yale Courses)"
    url: "https://oyc.yale.edu/economics/econ-252-11"
quiz:
  - q: "A daily candle has open 100, high 106, low 98, close 104. What color is it usually drawn?"
    options: ["Red/black (down)", "Green/white (up)", "Gray", "It depends on volume"]
    answer: 1
    why: "Close above open = up candle (green or hollow)."
  - q: "In that candle, how long is the upper wick?"
    options: ["2", "4", "6", "8"]
    answer: 0
    why: "Upper wick = high − max(open, close) = 106 − 104 = 2."
  - q: "Why use a log scale for a stock chart over 20 years?"
    options: ["It hides losses", "Equal vertical distances represent equal percentage moves", "It is required by law", "It shows volume"]
    answer: 1
    why: "On a log scale, a move from 10 to 20 looks as big as 100 to 200 — both are +100%."
  - q: "RSI(14) reads 78. The standard reading is:"
    options: ["Oversold", "Overbought (strong recent gains)", "Neutral", "A guaranteed sell signal"]
    answer: 1
    why: "Above 70 is conventionally 'overbought'. It describes past momentum — strong trends can stay overbought for long periods."
  - q: "The 50-day moving average crosses above the 200-day. Traders call this:"
    options: ["A death cross", "A golden cross", "A stop-loss", "A gap"]
    answer: 1
    why: "Golden cross = short MA above long MA. Whether it predicts anything must be tested — see the Backtester and chapter 11."
  - q: "Which statement is most accurate?"
    options: ["Indicators predict the future", "Indicators summarize past prices; their value must be tested out of sample", "Indicators are useless", "Volume never matters"]
    answer: 1
    why: "Every indicator is a function of past prices. Evidence on whether it adds predictive value comes only from honest testing."
---

## Candlesticks

Each candle summarizes one period (a minute, a day, a week) with four prices:

- **Open** — first trade of the period, **Close** — last trade,
- **High** and **Low** — extremes.

The **body** spans open→close: green/hollow when close > open, red/filled when close < open.
The **wicks** (shadows) reach the high and low.

**Example.** O = 100, H = 106, L = 98, C = 104 → green body from 100 to 104, upper wick
104→106 (length 2), lower wick 98→100 (length 2).

**Volume** (bars under the chart) is the number of shares traded. Large moves on large
volume involve more participants than moves on thin volume.

## Timeframe and scale

The same asset looks completely different on 1-minute, daily and monthly charts. Choose the
timeframe that matches your decision horizon.

Use a **log scale** for long histories: equal vertical distances then mean equal
**percentage** changes, so a crash in 1987 and a crash in 2020 can be compared fairly.

## Moving averages

$$\text{SMA}_n(t) = \frac{1}{n}\sum_{i=0}^{n-1} P_{t-i}$$

A smoothed trend line. Price above its 200-day SMA is a common definition of an uptrend.
Exponential moving averages (EMA) weight recent prices more.

## RSI (Relative Strength Index, Wilder 1978)

$$\text{RSI} = 100 - \frac{100}{1 + \text{RS}}, \qquad
\text{RS} = \frac{\text{average gain over } n}{\text{average loss over } n}$$

Ranges 0–100. Above 70 "overbought", below 30 "oversold" by convention.

## Bollinger bands

Middle = 20-day SMA; upper/lower = middle ± 2 rolling standard deviations. Price outside the
bands is statistically unusual *relative to the last 20 days*.

## A word of discipline

Indicators are **functions of past prices**. They organize information; they do not see the
future. Patterns that look obvious on a chart are often noise (our eyes find shapes
everywhere). The only way to know if a rule has value is to test it honestly on data it was
not designed on — that is chapter 11 and the Backtester page.

{{widget:candle_reader}}

{{widget:indicator_lab}}

## Summary

Candles show open, high, low, close; volume shows participation; log scales compare
percentage moves. Moving averages, RSI and Bollinger bands describe trend, momentum and
range — useful vocabulary, never proof.
