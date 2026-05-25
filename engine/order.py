from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pandas as pd


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class Order:
    timestamp: pd.Timestamp
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    order_type: OrderType = OrderType.MARKET
    status: OrderStatus = OrderStatus.PENDING
    fill_price: Optional[float] = None

    def fill(self, fill_price: float):
        self.fill_price = fill_price
        self.status = OrderStatus.FILLED

    def cancel(self):
        self.status = OrderStatus.CANCELLED

    def reject(self):
        self.status = OrderStatus.REJECTED

    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED

    @property
    def is_pending(self) -> bool:
        return self.status == OrderStatus.PENDING
