from typing import TYPE_CHECKING
import importlib

import pandas as pd

from .order import OrderSide, OrderType
from .portfolio import Portfolio

if TYPE_CHECKING:
    from ..strategies.base_strategy import BaseStrategy


def _get_compute_metrics():
    try:
        from ..analytics.metrics import compute_metrics
        return compute_metrics
    except ImportError:
        import analytics.metrics as m
        return m.compute_metrics


class Backtester:
    def __init__(
        self,
        initial_capital: float = 10_000.0,
        commission: float = 0.001,
        slippage: float = 0.0005,
    ):
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage

    def run(self, data: pd.DataFrame, strategy: "BaseStrategy") -> dict:
        if data.empty:
            raise ValueError("Data is empty, cannot run backtest.")

        required_cols = {"open", "high", "low", "close", "volume"}
        missing = required_cols - set(data.columns)
        if missing:
            raise ValueError(f"Data is missing required columns: {missing}")

        portfolio = Portfolio(self.initial_capital)
        strategy.reset()

        pending_orders = []

        for i in range(len(data)):
            bar = data.iloc[i]
            timestamp = data.index[i]

            if pending_orders:
                if i < len(data):
                    exec_price_base = bar["open"]
                    for order in pending_orders:
                        if order.side == OrderSide.BUY:
                            fill_price = exec_price_base * (1 + self.slippage)
                        else:
                            fill_price = exec_price_base * (1 - self.slippage)

                        if order.order_type == OrderType.LIMIT:
                            if order.side == OrderSide.BUY and fill_price > order.price:
                                order.cancel()
                                continue
                            if order.side == OrderSide.SELL and fill_price < order.price:
                                order.cancel()
                                continue

                        if order.side == OrderSide.BUY:
                            success = portfolio.buy(
                                symbol=order.symbol,
                                quantity=order.quantity,
                                price=fill_price,
                                commission=self.commission,
                                timestamp=timestamp,
                            )
                            if success:
                                order.fill(fill_price)
                            else:
                                order.reject()
                        else:
                            success = portfolio.sell(
                                symbol=order.symbol,
                                quantity=order.quantity,
                                price=fill_price,
                                commission=self.commission,
                                timestamp=timestamp,
                            )
                            if success:
                                order.fill(fill_price)
                            else:
                                order.reject()

                pending_orders = []

            prices = {col: bar[col] for col in ["open", "high", "low", "close"] if col in bar}
            portfolio.record_equity(timestamp, {strategy.symbol: bar["close"]})

            strategy.on_bar(bar, portfolio)

            if strategy.orders:
                pending_orders = list(strategy.orders)
                strategy.orders.clear()

        compute_metrics = _get_compute_metrics()
        metrics = compute_metrics(
            equity_curve=portfolio.equity_curve,
            trades=portfolio.trade_history,
        )

        return {
            "equity_curve": portfolio.equity_curve,
            "trades": portfolio.trade_history,
            "metrics": metrics,
            "portfolio": portfolio,
        }
