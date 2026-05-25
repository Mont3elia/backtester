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


class MeanReversion(BaseStrategy):
    name = "Mean Reversion"
    description = "Buy quando il prezzo scende di N deviazioni standard sotto la media mobile; sell al ritorno alla media"
    param_schema = {
        "period": {"type": "int", "default": 20, "min": 5, "max": 200, "label": "Lookback Period"},
        "entry_std": {"type": "float", "default": 2.0, "min": 0.5, "max": 5.0, "label": "Entry Std Dev"},
    }

    def __init__(self, symbol: str, **kwargs):
        super().__init__(symbol, **kwargs)
        period = self.params["period"]
        self._prices: deque = deque(maxlen=period)

    def _on_reset(self):
        period = self.params.get("period", 20)
        self._prices = deque(maxlen=period)

    def _stats(self) -> tuple:
        period = self.params["period"]
        if len(self._prices) < period:
            return None, None
        prices = list(self._prices)
        mean = sum(prices) / period
        variance = sum((p - mean) ** 2 for p in prices) / period
        std = math.sqrt(variance) if variance > 0 else 0.0
        return mean, std

    def on_bar(self, bar: pd.Series, portfolio: "Portfolio"):
        self._current_bar = bar
        self._current_timestamp = bar.name if hasattr(bar, "name") else pd.Timestamp.now()

        price = bar["close"]
        self._prices.append(price)

        mean, std = self._stats()
        if mean is None or std == 0:
            return

        entry_std = self.params["entry_std"]
        lower_band = mean - entry_std * std

        if price <= lower_band and not portfolio.has_position(self.symbol):
            quantity = portfolio.cash / price
            if quantity > 1e-8:
                self.buy(quantity)

        elif price >= mean and portfolio.has_position(self.symbol):
            self.close_position(portfolio)
