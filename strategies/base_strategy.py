from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

import pandas as pd

try:
    from ..engine.order import Order, OrderSide, OrderType, OrderStatus
except ImportError:
    from engine.order import Order, OrderSide, OrderType, OrderStatus

if TYPE_CHECKING:
    from engine.portfolio import Portfolio


class BaseStrategy(ABC):
    name: str = "Base"
    description: str = ""
    param_schema: dict = {}

    def __init__(self, symbol: str, **kwargs):
        self.symbol = symbol
        self.params: dict = {}
        self.orders: List[Order] = []
        self._current_bar: pd.Series = None
        self._current_timestamp: pd.Timestamp = None

        for key, schema in self.__class__.param_schema.items():
            if key in kwargs:
                value = kwargs[key]
            else:
                value = schema.get("default")
            self.params[key] = value
            setattr(self, key, value)

    def reset(self):
        self.orders = []
        self._on_reset()

    def _on_reset(self):
        pass

    @abstractmethod
    def on_bar(self, bar: pd.Series, portfolio: "Portfolio"):
        pass

    def _make_order(self, side: OrderSide, quantity: float, order_type: OrderType = OrderType.MARKET, price: float = None) -> Order:
        ts = self._current_timestamp or pd.Timestamp.now()
        p = price if price is not None else (self._current_bar["close"] if self._current_bar is not None else 0.0)
        return Order(
            timestamp=ts,
            symbol=self.symbol,
            side=side,
            quantity=quantity,
            price=p,
            order_type=order_type,
            status=OrderStatus.PENDING,
        )

    def buy(self, quantity: float, price: float = None, order_type: OrderType = OrderType.MARKET):
        order = self._make_order(OrderSide.BUY, quantity, order_type, price)
        self.orders.append(order)

    def sell(self, quantity: float, price: float = None, order_type: OrderType = OrderType.MARKET):
        order = self._make_order(OrderSide.SELL, quantity, order_type, price)
        self.orders.append(order)

    def close_position(self, portfolio: "Portfolio"):
        position = portfolio.get_position(self.symbol)
        if position and position.is_open():
            self.sell(position.quantity)
