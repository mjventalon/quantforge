"""Paper trading — virtual money, real prices, saved between visits."""

import json
from urllib.parse import quote as urlquote

import pandas as pd
import streamlit as st

from quantforge.app.code_exercises import embed_html
from quantforge.app.common import page_setup
from quantforge.app.paper_widgets import DEFAULT_WIDGETS, WIDGETS, day_pnl, get_quotes
from quantforge.paper import Account, load_wallet, new_wallet_id, save_wallet, valid_wallet_id

HOW_TO = """1. **Open an account** (virtual money — $1,000,000 by default). It is saved: come back
   tomorrow and everything is still here. Keep your **account code** to open it on another device.
2. Use the **Order ticket**: market, limit, stop, stop-limit or trailing-stop orders, buy or sell
   (short selling allowed with 150 % margin), good till cancelled or day.
3. Orders execute on the **next real price update** — outside market hours they wait for the
   next session, like at a broker. Prices come from your data source and may be delayed.
4. Pick the **widgets** you want on your board (charts, P&L, risk, GARCH, regimes, signals,
   model portfolios…). The board refreshes automatically.

No real money is involved and no order ever reaches an exchange."""

page_setup("Paper trading", "💼", HOW_TO)
COOKIE = "qf_wallet"


def _set_cookie(wid: str) -> None:
    v = json.dumps(urlquote(wid))
    embed_html("<script>const c='" + COOKIE + "='+" + v + "+'; path=/; max-age=63072000; "
               "SameSite=Lax';try{window.parent.document.cookie=c}catch(e){}"
               "try{document.cookie=c}catch(e){}</script>", 1)


# ------------------------------------------------------------------ wallet (saved accounts)
if "pt_wallet" not in st.session_state:
    try:
        ck = st.context.cookies.get(COOKIE)
    except Exception:  # noqa: BLE001
        ck = None
    if isinstance(ck, str) and valid_wallet_id(ck) and load_wallet(ck):
        st.session_state["pt_wallet"] = ck
wid = st.session_state.get("pt_wallet")
accounts = load_wallet(wid) if wid else []

if not accounts:
    st.markdown("### Open your paper trading account")
    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.markdown("**New account**")
        name = st.text_input("Account name", "My paper account", key="pt_new_name")
        cash = st.number_input("Starting cash ($)", 1_000.0, 100_000_000.0, 1_000_000.0,
                               10_000.0, format="%.0f", key="pt_new_cash")
        short = st.toggle("Allow short selling", True, key="pt_new_short")
        if st.button("Open account", type="primary", key="pt_open"):
            wid = new_wallet_id()
            save_wallet(wid, [Account(name=name, starting_cash=cash, cash=cash,
                                      allow_short=short, widgets=list(DEFAULT_WIDGETS))])
            st.session_state["pt_wallet"] = wid
            st.session_state["pt_new_cookie"] = True
            st.rerun()
    with c2, st.container(border=True):
        st.markdown("**I already have an account code**")
        code = st.text_input("Account code", key="pt_code", type="password").strip()
        if st.button("Open", key="pt_open_code"):
            if valid_wallet_id(code) and load_wallet(code):
                st.session_state["pt_wallet"] = code
                st.session_state["pt_new_cookie"] = True
                st.rerun()
            else:
                st.error("No account found for this code.")
    st.stop()

if st.session_state.pop("pt_new_cookie", False):
    _set_cookie(wid)

names = [a.name for a in accounts]
top = st.columns([3, 2, 1])
idx = top[0].selectbox("Account", range(len(accounts)), format_func=lambda i: names[i],
                       index=min(st.session_state.get("pt_idx", 0), len(accounts) - 1),
                       key="pt_idx", label_visibility="collapsed")
refresh = top[1].segmented_control("Refresh", ["Off", "10s", "30s", "60s"], default="30s",
                                   key="pt_refresh", label_visibility="collapsed",
                                   help="How often prices, orders and P&L update")
run_every = {"10s": 10, "30s": 30, "60s": 60}.get(refresh)


def money(x: float, sign: bool = False) -> str:
    """Compact dollars that fit a metric tile: $1.25M, $250.4K, $980.12."""
    s = "+" if sign and x >= 0 else ("-" if x < 0 else "")
    a = abs(x)
    body = (f"{a / 1e9:,.3f}B" if a >= 1e9 else f"{a / 1e6:,.3f}M" if a >= 1e6 else
            f"{a / 1e3:,.2f}K" if a >= 1e4 else f"{a:,.2f}")
    return f"{s}${body}"


def save() -> None:
    save_wallet(wid, accounts)


with top[2].popover("⚙️ Account"):
    acc0 = accounts[idx]
    st.markdown("**Account code** (keep it private — it opens this wallet anywhere):")
    st.code(wid, language=None)
    new_name = st.text_input("Rename", acc0.name, key="pt_rename")
    acc0.allow_short = st.toggle("Allow short selling", acc0.allow_short, key="pt_set_short")
    acc0.commission = st.number_input("Commission per order ($)", 0.0, 100.0,
                                      float(acc0.commission), 0.5, key="pt_set_comm")
    acc0.commission_bps = st.number_input("Commission (bps of notional)", 0.0, 100.0,
                                          float(acc0.commission_bps), 0.5, key="pt_set_bps")
    acc0.slippage_bps = st.number_input("Slippage (bps)", 0.0, 100.0, float(acc0.slippage_bps),
                                        0.5, key="pt_set_slip")
    if st.button("Save settings", key="pt_save_set"):
        acc0.name = new_name.strip() or acc0.name
        save()
        st.rerun()
    st.divider()
    nn = st.text_input("New account name", "Strategy B", key="pt_add_name")
    nc = st.number_input("Starting cash ($)", 1_000.0, 100_000_000.0, 1_000_000.0, 10_000.0,
                         format="%.0f", key="pt_add_cash")
    if st.button("➕ Add account", key="pt_add"):
        accounts.append(Account(name=nn, starting_cash=nc, cash=nc,
                                widgets=list(DEFAULT_WIDGETS)))
        save()
        st.rerun()
    st.download_button("⬇️ Export (JSON)", json.dumps(acc0.to_dict(), indent=1),
                       f"paper_{acc0.name}.json", key="pt_export")
    st.divider()
    if st.toggle("Danger zone", key="pt_danger"):
        if st.button("Reset this account to its starting cash", key="pt_reset"):
            accounts[idx] = Account(name=acc0.name, starting_cash=acc0.starting_cash,
                                    cash=acc0.starting_cash, allow_short=acc0.allow_short,
                                    watchlist=acc0.watchlist, widgets=acc0.widgets)
            save()
            st.rerun()
        if len(accounts) > 1 and st.button("Delete this account", key="pt_delete"):
            accounts.pop(idx)
            st.session_state["pt_idx"] = 0
            save()
            st.rerun()
        if st.button("Sign out of this wallet on this device", key="pt_signout"):
            st.session_state.pop("pt_wallet", None)
            embed_html("<script>const c='" + COOKIE + "=; path=/; max-age=0';"
                       "try{window.parent.document.cookie=c}catch(e){}</script>", 1)
            st.rerun()

acc = accounts[idx]
if not acc.widgets:
    acc.widgets = list(DEFAULT_WIDGETS)
chosen = st.multiselect("Widgets on your board", list(WIDGETS), default=acc.widgets,
                        key=f"pt_widgets_{idx}")
if chosen != acc.widgets:
    acc.widgets = chosen
    save()


@st.fragment(run_every=run_every)
def board() -> None:
    symbols = sorted({*acc.watchlist, *(s for s, p in acc.positions.items() if abs(p.qty) > 0),
                      *(o.symbol for o in acc.open_orders())})[:30]
    quotes, errors = get_quotes(symbols)
    fills = acc.process(quotes)
    acc.record_equity()
    save()
    for f in fills:
        st.toast(f"Filled: {f.side} {f.qty:,.4g} {f.symbol} @ {f.price:,.4f}", icon="✅")
    for o in acc.orders[-10:]:
        if o.status == "rejected" and not o.note.endswith("(seen)"):
            st.toast(f"Rejected {o.symbol}: {o.reason}", icon="⛔")
            o.note += " (seen)"

    px = {s: q.price for s, q in quotes.items()}
    eq = acc.equity(px)
    tot = eq - acc.starting_cash
    m = st.columns(6)
    m[0].metric("Equity", money(eq), f"{tot / acc.starting_cash:+.2%} all time",
                help=f"${eq:,.2f}")
    dp = day_pnl(acc, quotes)
    m[1].metric("Today's P&L", money(dp, True), f"{dp / max(eq - dp, 1):+.2%}",
                help=f"${dp:+,.2f}")
    m[2].metric("Total P&L", money(tot, True), help=f"${tot:+,.2f}")
    m[3].metric("Cash", money(acc.cash), help=f"${acc.cash:,.2f}")
    m[4].metric("Buying power", money(acc.buying_power(px)),
                help=f"${acc.buying_power(px):,.2f}")
    m[5].metric("Open orders", len(acc.open_orders()))
    last = max((q.ts for q in quotes.values()), default="")
    st.caption(f"💡 Virtual money on real prices · last price {pd.Timestamp(last):%Y-%m-%d %H:%M} "
               f"UTC · refreshed {pd.Timestamp.now():%H:%M:%S}"
               + (f" · ⚠️ no price for {', '.join(errors)}" if errors else "") if last else "")

    cols = st.columns(2)
    for i, name in enumerate(acc.widgets):
        with cols[i % 2], st.container(border=True):
            st.markdown(f"**{name}**")
            try:
                WIDGETS[name](acc, quotes, save)
            except Exception as exc:  # noqa: BLE001 - one widget must not break the board
                st.error(f"{name}: {exc}")


board()
st.caption("Paper trading only: no real money, no order routing. Not investment advice.")
