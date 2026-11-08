"""Look-ahead-free backtesting: single-asset rules, parameter search with a
train/test split, and walk-forward portfolio optimization."""

from .engine import BacktestResult, grid_search, run_backtest, trades_from_positions
from .lab import (
    LabRun,
    StrategySpec,
    combine,
    diversity_report,
    export_strategy_code,
    fold_analysis,
    greedy_portfolio,
    run_lab,
    trade_monte_carlo,
    trade_returns,
)
from .pairs import PairsResult, pairs_backtest
from .portfolio_bt import OPTIMIZERS, walk_forward_portfolio
from .strategies import (
    STRATEGIES,
    bollinger_reversion,
    buy_and_hold,
    rsi_reversion,
    sma_crossover,
    time_series_momentum,
    volatility_target,
)

__all__ = [
    "BacktestResult", "run_backtest", "grid_search", "trades_from_positions",
    "StrategySpec", "LabRun", "run_lab", "trade_returns", "diversity_report",
    "greedy_portfolio", "combine", "fold_analysis", "trade_monte_carlo", "export_strategy_code",
    "walk_forward_portfolio", "OPTIMIZERS", "PairsResult", "pairs_backtest",
    "STRATEGIES", "buy_and_hold", "sma_crossover", "time_series_momentum", "rsi_reversion",
    "bollinger_reversion", "volatility_target",
]
