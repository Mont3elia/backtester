from collections import deque
from typing import TYPE_CHECKING

import math
import pandas as pd

try:
    from ..base_strategy import BaseStrategy
except ImportError:
    from strategies.base_strategy import BaseStrategy

if TYPE_CHECKING:
    from engine.portfolio import Portfolio


class BollingerStrategy(BaseStrategy):
    name = "Bollinger Bands"
    description = "Buy quando il prezzo tocca la banda inferiore, sell quando tocca quella superiore"
    param_schema = {
        "period": {"type": "int", "default": 20, "min": 5, "max": 200, "label": "Period"},
        "std_dev": {"type": "float", "default": 2.0, "min": 0.5, "max": 5.0, "label": "Std Dev Multiplier"},
    }

    def __init__(self, symbol: str, **kwargs):
        super().__init__(symbol, **kwargs)
        period = self.params["period"]
        self._prices: deque = deque(maxlen=period)

    def _on_reset(self):
        period = self.params.get("period", 20)
        self._prices = deque(maxlen=period)

    def _bands(self) -> tuple:
        period = self.params["period"]
        std_dev = self.params["std_dev"]
        if len(self._prices) < period:
            return None, None, None
        prices = list(self._prices)
        mean = sum(prices) / period
        variance = sum((p - mean) ** 2 for p in prices) / period
        std = math.sqrt(variance)
        upper = mean + std_dev * std
        lower = mean - std_dev * std
        return upper, mean, lower

    def on_bar(self, bar: pd.Series, portfolio: "Portfolio"):
        self._current_bar = bar
        self._current_timestamp = bar.name if hasattr(bar, "name") else pd.Timestamp.now()

        price = bar["close"]
        self._prices.append(price)

        upper, middle, lower = self._bands()
        if upper is None:
            return

        if price <= lower and not portfolio.has_position(self.symbol):
            quantity = portfolio.cash / price
            if quantity > 1e-8:
                self.buy(quantity)

        elif price >= upper and portfolio.has_position(self.symbol):
            self.close_position(portfolio)
