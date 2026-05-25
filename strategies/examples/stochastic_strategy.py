from collections import deque
from typing import TYPE_CHECKING

import pandas as pd

try:
    from ..base_strategy import BaseStrategy
except ImportError:
    from strategies.base_strategy import BaseStrategy

if TYPE_CHECKING:
    from engine.portfolio import Portfolio


class StochasticStrategy(BaseStrategy):
    name = "Stochastic Strategy"
    description = "Buy quando %K scende sotto oversold, sell quando supera overbought"
    param_schema = {
        "k_period": {"type": "int", "default": 14, "min": 2, "max": 50, "label": "K Period"},
        "d_period": {"type": "int", "default": 3, "min": 1, "max": 20, "label": "D Period (smoothing)"},
        "oversold": {"type": "float", "default": 20.0, "min": 5.0, "max": 40.0, "label": "Oversold"},
        "overbought": {"type": "float", "default": 80.0, "min": 60.0, "max": 95.0, "label": "Overbought"},
    }

    def __init__(self, symbol: str, **kwargs):
        super().__init__(symbol, **kwargs)
        k_period = self.params["k_period"]
        d_period = self.params["d_period"]
        self._highs: deque = deque(maxlen=k_period)
        self._lows: deque = deque(maxlen=k_period)
        self._closes: deque = deque(maxlen=k_period)
        self._k_values: deque = deque(maxlen=d_period)

    def _on_reset(self):
        k_period = self.params.get("k_period", 14)
        d_period = self.params.get("d_period", 3)
        self._highs = deque(maxlen=k_period)
        self._lows = deque(maxlen=k_period)
        self._closes = deque(maxlen=k_period)
        self._k_values = deque(maxlen=d_period)

    def _compute_k(self) -> float | None:
        k_period = self.params["k_period"]
        if len(self._highs) < k_period:
            return None
        highest_high = max(self._highs)
        lowest_low = min(self._lows)
        denom = highest_high - lowest_low
        if denom == 0:
            return None
        close = self._closes[-1]
        return 100.0 * (close - lowest_low) / denom

    def on_bar(self, bar: pd.Series, portfolio: "Portfolio"):
        self._current_bar = bar
        self._current_timestamp = bar.name if hasattr(bar, "name") else pd.Timestamp.now()

        self._highs.append(bar["high"])
        self._lows.append(bar["low"])
        self._closes.append(bar["close"])

        k = self._compute_k()
        if k is None:
            return

        self._k_values.append(k)

        oversold = self.params["oversold"]
        overbought = self.params["overbought"]

        if k < oversold and not portfolio.has_position(self.symbol):
            quantity = portfolio.cash / bar["close"]
            if quantity > 1e-8:
                self.buy(quantity)

        elif k > overbought and portfolio.has_position(self.symbol):
            self.close_position(portfolio)
