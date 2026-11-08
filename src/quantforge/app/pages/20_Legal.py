"""Policies: terms, privacy, risk disclaimer, data attribution, certification policy."""

import streamlit as st

from quantforge.app import branding as B

st.title("⚖️ Legal & policies")
st.caption(f"Last updated: {B.LAST_UPDATED}. These policies apply to the {B.APP_NAME} web app and "
           "open-source library. If you run your own copy, you are the operator of that copy.")
contact = (f"[{B.CONTACT_EMAIL}](mailto:{B.CONTACT_EMAIL})" if B.CONTACT_EMAIL else
           f"the creator via [LinkedIn]({B.LINKEDIN_URL})" if B.LINKEDIN_URL else "the operator")

t = st.tabs(["Terms of use", "Risk disclaimer", "Privacy", "Data sources", "Certificates",
             "Open-source license"])

with t[0]:
    st.markdown(f"""
#### Terms of use

1. **Purpose.** {B.APP_NAME} is a free research and education tool. By using it you agree to
   these terms.
2. **No advice.** Nothing on this site is investment, financial, legal, tax or accounting advice,
   nor an offer or solicitation to buy or sell any security. See the *Risk disclaimer*.
3. **No real trading.** {B.APP_NAME} does not execute real orders, hold funds or connect to
   brokerage accounts. Paper trading uses virtual money only; its results do not predict real
   results (real fills, liquidity, fees and taxes differ).
4. **Acceptable use.** Do not use the app to break the law, to overload it or the data providers
   it calls (automated scraping, denial-of-service), to break third-party terms of service, or to
   impersonate others. Respect each data provider's terms — they apply to you directly when you
   enter your own API key.
5. **Your API keys.** Keys you type are kept only in your browser session's server memory for
   the duration of the session, are never written to disk by the app, and are sent only to the
   provider they belong to.
6. **Availability.** The service is provided "as is" and "as available", without warranty of any
   kind, express or implied, including accuracy, fitness for a particular purpose and
   non-infringement. Features may change or stop at any time.
7. **Limitation of liability.** To the fullest extent permitted by law, the creator and
   contributors are not liable for any loss or damage arising from use of, or reliance on, the
   app, its models, data or certificates.
8. **Changes.** These terms may be updated; the date above shows the latest version.

Questions: {contact}.
""")

with t[1]:
    st.markdown("""
#### Risk disclaimer

- Trading and investing involve **substantial risk of loss**, including loss of more than your
  initial investment with leveraged products, options and short positions.
- **Past performance does not guarantee future results.** Backtests are hypothetical: they are
  built with hindsight, cannot capture every cost, slippage, liquidity limit or tax, and
  frequently overstate what is achievable live.
- **Models are simplifications.** Black-Scholes, GARCH, VaR, regime models and every other model
  here rest on assumptions that markets regularly violate, especially in crises.
- **Data can be wrong, delayed or incomplete.** Free sources such as Yahoo Finance are delayed and
  occasionally erroneous; "live" views are periodic refreshes, not exchange feeds.
- Decisions you make are **your own responsibility**. Consult a licensed professional before
  acting on any analysis.
""")

with t[2]:
    st.markdown(f"""
#### Privacy

- **No accounts, no tracking by {B.APP_NAME}.** The app has no sign-up, no advertising and no
  analytics code of its own.
- **Session data.** Tickers, settings, API keys, quiz answers and Academy progress live in the
  server's memory for your session only and disappear when it ends. Download your progress file
  if you want to keep it.
- **Paper-trading accounts** (virtual cash, orders, positions, watchlist) are stored on the
  server under a random account code kept in a cookie on your device. They contain no
  personal data. Delete them anytime from ⚙️ Account; anyone with your code can open them.
- **AI copilot** (optional, off until you allow it): when you enable it, the current page's
  field names, values and displayed results and your messages are sent to the AI company you
  chose (Anthropic, OpenAI or Google) with your own API key, under that company's terms and
  privacy policy. API keys and password fields are never sent. AI answers can be wrong.
- **Names on certificates** are used only to generate the PDF and its ID in your session; they
  are not stored. Verification recomputes the signature — no database of holders exists.
- **Third parties.** When you request data, the server calls the provider (Yahoo Finance, FRED,
  SEC, Massive, FMP or Alpha Vantage), which receives the request and, where used, your key.
  Their privacy policies apply.
- **Hosting.** The hosting provider of a deployment may keep standard technical logs (IP
  address, timestamps). Streamlit, the framework the app is built on, may collect anonymous usage
  statistics unless the operator disables them (`browser.gatherUsageStats = false`, which is the
  setting shipped with {B.APP_NAME}).
- **Cookies.** The app uses only the technical cookies/websocket session needed to run; none for
  advertising or profiling.
- **Your rights.** Since no personal data is retained, there is normally nothing to access or
  delete; for any request contact {contact}.
""")

with t[3]:
    st.markdown("""
#### Data sources & attribution

| Source | Used for | Terms |
|---|---|---|
| **Yahoo Finance** (via the open-source `yfinance` library) | Prices, options, fundamentals, search | Yahoo's terms: intended for personal use; not affiliated with or endorsed by Yahoo |
| **FRED®, Federal Reserve Bank of St. Louis** | Treasury yields, inflation, macro series | FRED terms of use; series copyrights remain with their owners |
| **U.S. SEC EDGAR** | Company ticker list | Public data; SEC fair-access policy (declared User-Agent, rate limits) |
| **Massive (formerly Polygon.io)** | Prices with your key | Your Massive subscription terms |
| **Financial Modeling Prep** | Prices, fundamentals with your key | Your FMP subscription terms |
| **Alpha Vantage** | Prices with your key | Your Alpha Vantage terms |

Every chart shows its data source. If a source fails, the app says so — it never replaces
missing data with invented numbers. Trademarks belong to their owners; their use here is purely
descriptive.
""")

with t[4]:
    st.markdown(f"""
#### Certification policy

- {B.APP_NAME} Academy certificates attest that the named person **completed a chapter's content
  and passed its quiz (≥ 80 %)** in the {B.APP_NAME} app on the date shown.
- They are **not** academic degrees, university credits, professional licenses or regulatory
  qualifications, and {B.APP_NAME} is **not an accredited institution**. Universities and
  organisations cited as reading sources do **not** endorse or issue these certificates.
- Each certificate ID is an HMAC-SHA256 signature of name, chapter and date. Anyone can check it
  on the *Verify a certificate* page. Quizzes are taken online without proctoring, so a
  certificate does not prove identity.
- Misrepresenting a certificate (editing it, claiming one you did not earn, presenting it as an
  accredited qualification) is prohibited. The operator may change keys, which can invalidate
  earlier development-mode IDs.
""")

with t[5]:
    st.markdown(f"""
#### Open-source license

The {B.APP_NAME} source code is released under the **MIT License** — © {B.AUTHOR}. You may use,
copy, modify and distribute it, including commercially, provided the copyright and license
notice are kept. The software is provided "as is", without warranty. Third-party libraries keep
their own licenses (NumPy, SciPy, pandas: BSD; Plotly, Streamlit: MIT/Apache-2.0; yfinance:
Apache-2.0; reportlab: BSD).
""")
