from dataclasses import dataclass

from .order import OrderSide


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_price: float
    side: OrderSide

    def market_value(self, price: float) -> float:
        return self.quantity * price

    def unrealized_pnl(self, price: float) -> float:
        if self.side == OrderSide.BUY:
            return self.quantity * (price - self.avg_price)
        return self.quantity * (self.avg_price - price)

    def is_open(self) -> bool:
        return self.quantity > 0

    def update(self, additional_quantity: float, fill_price: float):
        total_cost = self.avg_price * self.quantity + fill_price * additional_quantity
        self.quantity += additional_quantity
        if self.quantity > 0:
            self.avg_price = total_cost / self.quantity
