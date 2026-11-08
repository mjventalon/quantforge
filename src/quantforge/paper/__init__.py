"""Paper trading: virtual money on real market prices, saved between sessions.

>>> from quantforge.paper import Account, Order, Quote
>>> acc = Account(starting_cash=10_000, cash=10_000, slippage_bps=0)
>>> _ = acc.submit(Order("AAPL", "buy", 10), Quote(200.0, "2026-11-06T15:59"))
>>> fills = acc.process({"AAPL": Quote(201.0, "2026-11-06T16:00")})
>>> round(acc.cash, 2)
7990.0
"""

from .engine import ORDER_TYPES, Account, Fill, Order, OrderError, Position, Quote, target_orders
from .store import data_dir, load_wallet, new_wallet_id, save_wallet, valid_wallet_id

__all__ = ["Account", "Order", "Fill", "Position", "Quote", "OrderError", "ORDER_TYPES",
           "target_orders", "data_dir", "load_wallet", "save_wallet", "new_wallet_id",
           "valid_wallet_id"]
