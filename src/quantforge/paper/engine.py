"""Paper-trading engine: virtual money, real prices.

Order types: market, limit, stop, stop-limit, trailing stop (percent). Time in force: ``day``
or ``gtc``. Long and (optionally) short positions with a Reg-T style 150 % margin check.

Fill model — deliberately conservative and data-driven:

* An order is evaluated only on a **price update newer than the one seen when it was
  submitted**. During market hours that is the next bar (about a minute later); outside
  market hours the order waits for the next real quote, exactly like a broker queues orders.
  No exchange calendar is needed: if no new price arrives, nothing fills.
* Market orders fill at that new price; triggered limit orders fill at the better of the
  limit and the current price; slippage (bps) moves the price against you; commissions are
  charged per order and/or in bps of notional.
* ``day`` orders expire once a price from a later session date than their first active date
  arrives.

Accounting: average-cost method, realized P&L booked on every reduction, positions may flip
from long to short in one order (split into close + open).
"""

from __future__ import annotations

import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd

__all__ = ["Quote", "Order", "Fill", "Position", "Account", "OrderError", "ORDER_TYPES",
           "target_orders"]

ORDER_TYPES = ("market", "limit", "stop", "stop_limit", "trailing_stop")
MARGIN_REQ = 1.5          # Reg-T initial requirement for short sales (150 % of proceeds)


class OrderError(ValueError):
    """The order is invalid or cannot be accepted."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Quote:
    price: float
    ts: str              # ISO timestamp of the price (exchange time, as given by the source)
    session: str = ""    # trading date of the price (YYYY-MM-DD), for day-order expiry


@dataclass
class Order:
    symbol: str
    side: str                  # "buy" | "sell"
    qty: float
    type: str = "market"
    limit: float | None = None
    stop: float | None = None
    trail_pct: float | None = None
    tif: str = "gtc"           # "day" | "gtc"
    id: str = field(default_factory=lambda: secrets.token_hex(4))
    status: str = "open"       # open | filled | cancelled | rejected | expired
    submitted: str = field(default_factory=_now)
    ref_ts: str = ""           # timestamp of the last price seen at submission
    active_session: str = ""
    triggered: bool = False
    hwm: float | None = None   # trailing reference (high for sells, low for buys)
    filled_ts: str = ""
    fill_price: float | None = None
    reason: str = ""
    note: str = ""


@dataclass
class Fill:
    order_id: str
    symbol: str
    side: str
    qty: float
    price: float
    commission: float
    ts: str
    realized: float


@dataclass
class Position:
    qty: float = 0.0
    avg_cost: float = 0.0
    realized: float = 0.0


@dataclass
class Account:
    name: str = "My paper account"
    starting_cash: float = 1_000_000.0
    cash: float = 1_000_000.0
    allow_short: bool = True
    commission: float = 0.0          # per order, in account currency
    commission_bps: float = 0.0      # of notional
    slippage_bps: float = 2.0
    id: str = field(default_factory=lambda: secrets.token_urlsafe(9))
    created: str = field(default_factory=_now)
    positions: dict[str, Position] = field(default_factory=dict)
    orders: list[Order] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    equity_history: list[tuple[str, float]] = field(default_factory=list)
    watchlist: list[str] = field(default_factory=lambda: ["SPY", "AAPL", "MSFT", "NVDA",
                                                          "BTC-USD"])
    widgets: list[str] = field(default_factory=list)
    last_prices: dict[str, float] = field(default_factory=dict)

    # ------------------------------------------------------------------ serialization
    def to_dict(self) -> dict:
        d = asdict(self)
        d["positions"] = {k: asdict(v) for k, v in self.positions.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Account:
        d = dict(d)
        pos = {k: Position(**v) for k, v in d.pop("positions", {}).items()}
        orders = [Order(**o) for o in d.pop("orders", [])]
        fills = [Fill(**f) for f in d.pop("fills", [])]
        hist = [tuple(x) for x in d.pop("equity_history", [])]
        known = set(cls.__dataclass_fields__)
        acc = cls(**{k: v for k, v in d.items() if k in known})
        acc.positions, acc.orders, acc.fills, acc.equity_history = pos, orders, fills, hist
        return acc

    # ------------------------------------------------------------------ valuation
    def market_value(self, prices: dict[str, float] | None = None) -> float:
        px = {**self.last_prices, **(prices or {})}
        return float(sum(p.qty * px.get(s, p.avg_cost) for s, p in self.positions.items()))

    def equity(self, prices: dict[str, float] | None = None) -> float:
        return self.cash + self.market_value(prices)

    def short_exposure(self, prices: dict[str, float] | None = None) -> float:
        px = {**self.last_prices, **(prices or {})}
        return float(sum(-p.qty * px.get(s, p.avg_cost) for s, p in self.positions.items()
                         if p.qty < 0))

    def buying_power(self, prices: dict[str, float] | None = None) -> float:
        """Cash free for new trades. Long positions are fully paid (cash account); short
        positions keep 150 % of their market value aside (the proceeds + 50 % of your own
        money, as under Regulation T)."""
        return max(0.0, self.cash - MARGIN_REQ * self.short_exposure(prices))

    def positions_frame(self, prices: dict[str, float] | None = None) -> pd.DataFrame:
        px = {**self.last_prices, **(prices or {})}
        rows = []
        eq = self.equity(prices)
        for s, p in sorted(self.positions.items()):
            if abs(p.qty) < 1e-12:
                continue
            last = px.get(s, np.nan)
            mv = p.qty * last
            rows.append({"Symbol": s, "Side": "long" if p.qty > 0 else "short", "Qty": p.qty,
                         "Avg cost": p.avg_cost, "Last": last, "Market value": mv,
                         "Unrealized P&L": (last - p.avg_cost) * p.qty,
                         "Unrealized %": (last / p.avg_cost - 1) * np.sign(p.qty)
                         if p.avg_cost else np.nan,
                         "Realized P&L": p.realized,
                         "Weight": mv / eq if eq else np.nan})
        return pd.DataFrame(rows)

    def realized_pnl(self) -> float:
        return float(sum(p.realized for p in self.positions.values()))

    def total_commissions(self) -> float:
        return float(sum(f.commission for f in self.fills))

    # ------------------------------------------------------------------ orders
    def submit(self, order: Order, quote: Quote | None) -> Order:
        """Validate and queue an order. ``quote`` is the latest known price for the symbol."""
        o = order
        o.symbol = o.symbol.strip().upper()
        if o.side not in ("buy", "sell"):
            raise OrderError("side must be 'buy' or 'sell'")
        if o.type not in ORDER_TYPES:
            raise OrderError(f"unknown order type {o.type!r}")
        if o.tif not in ("day", "gtc"):
            raise OrderError("time in force must be 'day' or 'gtc'")
        if not (o.qty > 0) or not np.isfinite(o.qty):
            raise OrderError("quantity must be positive")
        if o.type in ("limit", "stop_limit") and not (o.limit and o.limit > 0):
            raise OrderError("a positive limit price is required")
        if o.type in ("stop", "stop_limit") and not (o.stop and o.stop > 0):
            raise OrderError("a positive stop price is required")
        if o.type == "trailing_stop" and not (o.trail_pct and 0 < o.trail_pct < 100):
            raise OrderError("trailing percent must be between 0 and 100")
        if quote is None or not np.isfinite(quote.price) or quote.price <= 0:
            raise OrderError(f"no valid price for {o.symbol}; cannot accept the order")
        held = self.positions.get(o.symbol, Position()).qty
        if o.side == "sell" and o.qty > max(held, 0) + 1e-12 and not self.allow_short:
            raise OrderError("short selling is disabled for this account")
        o.ref_ts = quote.ts
        if o.type == "trailing_stop":
            o.hwm = quote.price
        self.last_prices[o.symbol] = quote.price
        self.orders.append(o)
        return o

    def cancel(self, order_id: str) -> bool:
        for o in self.orders:
            if o.id == order_id and o.status == "open":
                o.status, o.reason = "cancelled", "cancelled by you"
                return True
        return False

    def open_orders(self) -> list[Order]:
        return [o for o in self.orders if o.status == "open"]

    # ------------------------------------------------------------------ matching
    def process(self, quotes: dict[str, Quote]) -> list[Fill]:
        """Evaluate open orders against new prices; mark the book; returns new fills."""
        new: list[Fill] = []
        for s, q in quotes.items():
            if np.isfinite(q.price) and q.price > 0:
                self.last_prices[s.upper()] = q.price
        for o in self.orders:
            if o.status != "open":
                continue
            q = quotes.get(o.symbol)
            if q is None or not q.ts or q.ts <= o.ref_ts:
                continue                          # no fresh price since submission
            sess = q.session or q.ts[:10]
            if not o.active_session:
                o.active_session = sess
            elif o.tif == "day" and sess > o.active_session:
                o.status, o.reason = "expired", "day order expired at the end of its session"
                continue
            price = self._match(o, q.price)
            if price is not None:
                f = self._execute(o, price, q.ts)
                if f is not None:
                    new.append(f)
        return new

    def _match(self, o: Order, px: float) -> float | None:
        buy = o.side == "buy"
        if o.type == "market":
            return px
        if o.type == "limit":
            return min(px, o.limit) if buy and px <= o.limit else (
                max(px, o.limit) if not buy and px >= o.limit else None)
        if o.type in ("stop", "stop_limit"):
            if not o.triggered:
                o.triggered = (px >= o.stop) if buy else (px <= o.stop)
                if not o.triggered:
                    return None
            if o.type == "stop":
                return px
            return min(px, o.limit) if buy and px <= o.limit else (
                max(px, o.limit) if not buy and px >= o.limit else None)
        # trailing stop: sell trails the high, buy trails the low
        k = o.trail_pct / 100
        if buy:
            o.hwm = min(o.hwm, px)
            return px if px >= o.hwm * (1 + k) else None
        o.hwm = max(o.hwm, px)
        return px if px <= o.hwm * (1 - k) else None

    def _execute(self, o: Order, raw: float, ts: str) -> Fill | None:
        slip = self.slippage_bps / 1e4
        price = raw * (1 + slip) if o.side == "buy" else raw * (1 - slip)
        if o.type in ("limit", "stop_limit"):   # slippage never breaks the limit
            price = min(price, o.limit) if o.side == "buy" else max(price, o.limit)
        signed = o.qty if o.side == "buy" else -o.qty
        fee = self.commission + abs(signed) * price * self.commission_bps / 1e4
        pos = self.positions.setdefault(o.symbol, Position())

        # -- risk check on the post-trade book: cash − 150 % × shorts ≥ 0
        new_cash = self.cash - signed * price - fee
        prices = {**self.last_prices, o.symbol: raw}
        before = pos.qty
        after = before + signed
        short_after = (self.short_exposure(prices) - max(-before, 0.0) * raw
                       + max(-after, 0.0) * raw)
        if new_cash - MARGIN_REQ * short_after < -1e-9 and not (
                o.side == "buy" and after <= 0 and before < 0):   # covering always allowed
            o.status = "rejected"
            o.reason = ("insufficient margin for the short sale (150 % required)"
                        if after < 0 else "insufficient buying power")
            return None

        # -- accounting (average cost)
        realized = 0.0
        if before == 0 or np.sign(before) == np.sign(signed):
            tot = abs(before) + abs(signed)
            pos.avg_cost = (abs(before) * pos.avg_cost + abs(signed) * price) / tot
        else:
            closing = min(abs(signed), abs(before))
            realized = closing * (price - pos.avg_cost) * np.sign(before)
            if abs(signed) > abs(before):            # flipped side
                pos.avg_cost = price
            elif abs(after) < 1e-12:
                pos.avg_cost = 0.0
        realized -= fee
        pos.qty = 0.0 if abs(after) < 1e-12 else after
        pos.realized += realized
        self.cash = new_cash
        o.status, o.fill_price, o.filled_ts = "filled", price, ts
        f = Fill(o.id, o.symbol, o.side, o.qty, price, fee, ts, realized)
        self.fills.append(f)
        return f

    # ------------------------------------------------------------------ history
    def record_equity(self, ts: str | None = None, min_seconds: int = 60) -> None:
        ts = ts or _now()
        eq = self.equity()
        if self.equity_history:
            last_ts = pd.Timestamp(self.equity_history[-1][0])
            if (pd.Timestamp(ts) - last_ts).total_seconds() < min_seconds:
                self.equity_history[-1] = (self.equity_history[-1][0], eq)
                return
        self.equity_history.append((ts, eq))
        if len(self.equity_history) > 20_000:               # keep files small
            self.equity_history = self.equity_history[-20_000:]

    def equity_series(self) -> pd.Series:
        if not self.equity_history:
            return pd.Series(dtype=float)
        s = pd.Series([v for _, v in self.equity_history],
                      index=pd.to_datetime([t for t, _ in self.equity_history], utc=True))
        return s[~s.index.duplicated(keep="last")]


def target_orders(account: Account, weights: dict[str, float], prices: dict[str, float],
                  invest_fraction: float = 1.0, min_trade: float = 1.0,
                  fractional: bool = True) -> list[Order]:
    """Market orders that move the account to ``weights`` × ``invest_fraction`` of equity.

    Sells are listed first so their cash is available for the buys. Weights may be negative
    (short) if the account allows it. Positions not in ``weights`` are closed."""
    eq = account.equity(prices)
    want = {s.upper(): w * invest_fraction for s, w in weights.items()}
    syms = set(want) | {s for s, p in account.positions.items() if abs(p.qty) > 1e-12}
    sells, buys = [], []
    for s in sorted(syms):
        px = prices.get(s) or account.last_prices.get(s)
        if not px:
            raise OrderError(f"no price for {s}")
        cur = account.positions.get(s, Position()).qty
        tgt = want.get(s, 0.0) * eq / px
        if not fractional:
            tgt = np.floor(tgt) if tgt >= 0 else np.ceil(tgt)
        d = tgt - cur
        if abs(d) * px < min_trade:
            continue
        (buys if d > 0 else sells).append(Order(s, "buy" if d > 0 else "sell", abs(d),
                                                note="rebalance"))
    return sells + buys
