"""Paper-trading engine: order types, fills, accounting, margin, persistence."""

import pytest

from quantforge.paper import Account, Order, OrderError, Quote, target_orders
from quantforge.paper.store import load_wallet, new_wallet_id, save_wallet, valid_wallet_id


def acct(**kw):
    kw.setdefault("slippage_bps", 0.0)
    cash = kw.pop("cash", 100_000.0)
    return Account(starting_cash=cash, cash=cash, **kw)


def q(p, t, s="2026-11-06"):
    return Quote(p, f"{s}T{t}", s)


def test_default_account_has_one_million():
    a = Account()
    assert a.cash == a.starting_cash == 1_000_000 and a.buying_power() == 1_000_000


def test_market_order_waits_for_a_new_price():
    a = acct()
    a.submit(Order("AAPL", "buy", 10), q(200, "15:00"))
    assert a.process({"AAPL": q(200, "15:00")}) == []          # same bar: no fill
    f = a.process({"AAPL": q(201, "15:01")})
    assert len(f) == 1 and f[0].price == 201
    assert a.cash == pytest.approx(100_000 - 2010)
    assert a.positions["AAPL"].qty == 10 and a.positions["AAPL"].avg_cost == 201


def test_slippage_and_commissions():
    a = acct(slippage_bps=10, commission=1.0, commission_bps=5)
    a.submit(Order("MSFT", "buy", 100), q(400, "10:00"))
    f = a.process({"MSFT": q(400, "10:01")})[0]
    assert f.price == pytest.approx(400.4)
    assert f.commission == pytest.approx(1 + 100 * 400.4 * 5e-4)
    assert a.cash == pytest.approx(100_000 - 40_040 - f.commission)


def test_limit_orders_fill_at_limit_or_better():
    a = acct()
    a.submit(Order("X", "buy", 1, "limit", limit=99), q(100, "10:00"))
    assert a.process({"X": q(99.5, "10:01")}) == []
    assert a.process({"X": q(98.0, "10:02")})[0].price == 98.0
    a.submit(Order("X", "sell", 1, "limit", limit=105), q(98, "10:02"))
    assert a.process({"X": q(106, "10:03")})[0].price == 106


def test_stop_stop_limit_and_trailing():
    a = acct()
    a.submit(Order("X", "buy", 10), q(100, "10:00"))
    a.process({"X": q(100, "10:01")})
    a.submit(Order("X", "sell", 5, "stop", stop=95), q(100, "10:01"))
    assert a.process({"X": q(96, "10:02")}) == []
    assert a.process({"X": q(94, "10:03")})[0].price == 94
    a.submit(Order("X", "sell", 5, "trailing_stop", trail_pct=10), q(94, "10:03"))
    a.process({"X": q(110, "10:04")})                         # new high: stop at 99
    assert a.process({"X": q(100, "10:05")}) == []
    assert a.process({"X": q(98.9, "10:06")})[0].price == 98.9
    b = acct()
    b.submit(Order("Y", "buy", 1, "stop_limit", stop=105, limit=106), q(100, "10:00"))
    assert b.process({"Y": q(107, "10:01")}) == []            # triggered, above limit
    assert b.process({"Y": q(105.5, "10:02")})[0].price == 105.5


def test_day_order_expires_next_session_gtc_does_not():
    a = acct()
    day = a.submit(Order("X", "buy", 1, "limit", limit=50, tif="day"), q(100, "15:59"))
    gtc = a.submit(Order("X", "buy", 1, "limit", limit=50), q(100, "15:59"))
    a.process({"X": q(100, "16:00")})
    a.process({"X": Quote(99, "2026-11-09T09:31", "2026-11-09")})
    assert day.status == "expired" and gtc.status == "open"


def test_realized_pnl_average_cost_and_flip_to_short():
    a = acct()
    for px, t in ((100, "10:01"), (110, "10:03")):
        a.submit(Order("X", "buy", 10), q(px, "10:00" if t == "10:01" else "10:02"))
        a.process({"X": q(px, t)})
    assert a.positions["X"].avg_cost == pytest.approx(105)
    a.submit(Order("X", "sell", 25), q(120, "10:03"))
    a.process({"X": q(120, "10:04")})
    p = a.positions["X"]
    assert p.realized == pytest.approx(20 * 15)               # closed 20 at +15
    assert p.qty == -5 and p.avg_cost == 120                  # now short 5 at 120
    assert a.equity({"X": 120}) == pytest.approx(100_000 + 300)


def test_rejections():
    a = acct(cash=1_000)
    a.submit(Order("X", "buy", 100), q(100, "10:00"))
    a.process({"X": q(100, "10:01")})
    assert a.orders[-1].status == "rejected" and "buying power" in a.orders[-1].reason
    b = acct(cash=1_000)
    b.submit(Order("X", "sell", 30), q(100, "10:00"))   # $3,000 short needs $1,500 of own money
    b.process({"X": q(100, "10:01")})
    assert b.orders[-1].status == "rejected" and "150" in b.orders[-1].reason
    c = acct(allow_short=False)
    with pytest.raises(OrderError):
        c.submit(Order("X", "sell", 1), q(100, "10:00"))
    with pytest.raises(OrderError):
        c.submit(Order("X", "buy", 1, "limit"), q(100, "10:00"))
    with pytest.raises(OrderError):
        c.submit(Order("X", "buy", 1), None)


def test_short_margin_and_buying_power():
    a = acct(cash=10_000)
    a.submit(Order("X", "sell", 50), q(100, "10:00"))         # $5,000 short needs $7,500
    a.process({"X": q(100, "10:01")})
    assert a.positions["X"].qty == -50
    assert a.cash == 15_000 and a.buying_power() == pytest.approx(15_000 - 7_500)
    a.submit(Order("X", "buy", 50), q(100, "10:01"))          # cover
    a.process({"X": q(90, "10:02")})
    assert a.positions["X"].qty == 0 and a.positions["X"].realized == pytest.approx(500)


def test_cancel():
    a = acct()
    o = a.submit(Order("X", "buy", 1, "limit", limit=1), q(100, "10:00"))
    assert a.cancel(o.id) and o.status == "cancelled" and not a.cancel(o.id)


def test_rebalance_to_target_weights():
    a = acct()
    prices = {"AAA": 50.0, "BBB": 200.0}
    orders = target_orders(a, {"AAA": 0.6, "BBB": 0.4}, prices)
    for o in orders:
        a.submit(o, q(prices[o.symbol], "10:00"))
    a.process({s: q(p, "10:01") for s, p in prices.items()})
    w = a.positions_frame(prices).set_index("Symbol")["Weight"]
    assert w["AAA"] == pytest.approx(0.6) and w["BBB"] == pytest.approx(0.4)
    orders = target_orders(a, {"BBB": 1.0}, prices)           # AAA is sold first
    assert orders[0].symbol == "AAA" and orders[0].side == "sell"


def test_persistence_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("QUANTFORGE_DATA_DIR", str(tmp_path))
    a = acct()
    a.submit(Order("X", "buy", 3), q(10, "10:00"))
    a.process({"X": q(11, "10:01")})
    a.record_equity("2026-11-06T10:01:00+00:00")
    wid = new_wallet_id()
    assert valid_wallet_id(wid) and not valid_wallet_id("../etc/passwd")
    save_wallet(wid, [a])
    b = load_wallet(wid)[0]
    assert b.to_dict() == a.to_dict()
    assert load_wallet(new_wallet_id()) == []
    with pytest.raises(ValueError):
        load_wallet("../../x")
