from typing import Dict, List, Optional, Tuple

import pandas as pd

from .order import OrderSide
from .position import Position


class Portfolio:
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[dict] = []
        self.equity_curve: List[Tuple[pd.Timestamp, float]] = []

    def buy(
        self,
        symbol: str,
        quantity: float,
        price: float,
        commission: float = 0.0,
        timestamp: Optional[pd.Timestamp] = None,
    ) -> bool:
        cost = quantity * price
        commission_amount = cost * commission
        total_cost = cost + commission_amount

        if total_cost > self.cash:
            affordable = self.cash / (price * (1 + commission))
            if affordable < 1e-8:
                return False
            quantity = affordable
            cost = quantity * price
            commission_amount = cost * commission
            total_cost = cost + commission_amount

        self.cash -= total_cost

        if symbol in self.positions and self.positions[symbol].is_open():
            self.positions[symbol].update(quantity, price)
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                avg_price=price,
                side=OrderSide.BUY,
            )

        self.trade_history.append({
            "timestamp": timestamp,
            "symbol": symbol,
            "side": "buy",
            "quantity": quantity,
            "price": price,
            "commission": commission_amount,
            "pnl": None,
            "pnl_pct": None,
        })
        return True

    def sell(
        self,
        symbol: str,
        quantity: float,
        price: float,
        commission: float = 0.0,
        timestamp: Optional[pd.Timestamp] = None,
    ) -> bool:
        if symbol not in self.positions or not self.positions[symbol].is_open():
            return False

        position = self.positions[symbol]
        quantity = min(quantity, position.quantity)

        proceeds = quantity * price
        commission_amount = proceeds * commission
        net_proceeds = proceeds - commission_amount

        pnl = (price - position.avg_price) * quantity - commission_amount
        pnl_pct = (price / position.avg_price - 1) * 100 if position.avg_price > 0 else 0.0

        self.cash += net_proceeds
        position.quantity -= quantity

        self.trade_history.append({
            "timestamp": timestamp,
            "symbol": symbol,
            "side": "sell",
            "quantity": quantity,
            "price": price,
            "commission": commission_amount,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        })
        return True

    def equity(self, prices_dict: Dict[str, float]) -> float:
        total = self.cash
        for symbol, position in self.positions.items():
            if position.is_open() and symbol in prices_dict:
                total += position.market_value(prices_dict[symbol])
        return total

    def get_position(self, symbol: str) -> Optional[Position]:
        pos = self.positions.get(symbol)
        if pos and pos.is_open():
            return pos
        return None

    def has_position(self, symbol: str) -> bool:
        return self.get_position(symbol) is not None

    def record_equity(self, timestamp: pd.Timestamp, prices_dict: Dict[str, float]):
        eq = self.equity(prices_dict)
        self.equity_curve.append((timestamp, eq))
