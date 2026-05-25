from collections import deque
from typing import TYPE_CHECKING

import pandas as pd

try:
    from ..base_strategy import BaseStrategy
except ImportError:
    from strategies.base_strategy import BaseStrategy

if TYPE_CHECKING:
    from engine.portfolio import Portfolio


class RSIStrategy(BaseStrategy):
    name = "RSI Strategy"
    description = "Entra in ipervenduto, esce in ipercomprato"
    param_schema = {
        "period": {"type": "int", "default": 14, "min": 2, "max": 100, "label": "RSI Period"},
        "oversold": {"type": "float", "default": 30.0, "min": 5.0, "max": 50.0, "label": "Oversold"},
        "overbought": {"type": "float", "default": 70.0, "min": 50.0, "max": 95.0, "label": "Overbought"},
    }

    def __init__(self, symbol: str, **kwargs):
        super().__init__(symbol, **kwargs)
        period = self.params["period"]
        self._prices: deque = deque(maxlen=period + 1)
        self._avg_gain: float = None
        self._avg_loss: float = None
        self._bar_count: int = 0

    def _on_reset(self):
        period = self.params.get("period", 14)
        self._prices = deque(maxlen=period + 1)
        self._avg_gain = None
        self._avg_loss = None
        self._bar_count = 0

    def _compute_rsi(self, close: float) -> float | None:
        period = self.params["period"]
        self._prices.append(close)
        self._bar_count += 1

        if len(self._prices) < 2:
            return None

        change = self._prices[-1] - self._prices[-2]
        gain = max(change, 0.0)
        loss = max(-change, 0.0)

        if self._bar_count == period + 1:
            changes = [self._prices[i + 1] - self._prices[i] for i in range(len(self._prices) - 1)]
            gains = [max(c, 0) for c in changes]
            losses = [max(-c, 0) for c in changes]
            self._avg_gain = sum(gains) / period
            self._avg_loss = sum(losses) / period
        elif self._bar_count > period + 1 and self._avg_gain is not None:
            self._avg_gain = (self._avg_gain * (period - 1) + gain) / period
            self._avg_loss = (self._avg_loss * (period - 1) + loss) / period
        else:
            return None

        if self._avg_loss == 0:
            return 100.0
        rs = self._avg_gain / self._avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def on_bar(self, bar: pd.Series, portfolio: "Portfolio"):
        self._current_bar = bar
        self._current_timestamp = bar.name if hasattr(bar, "name") else pd.Timestamp.now()

        rsi = self._compute_rsi(bar["close"])
        if rsi is None:
            return

        oversold = self.params["oversold"]
        overbought = self.params["overbought"]

        if rsi < oversold and not portfolio.has_position(self.symbol):
            quantity = portfolio.cash / bar["close"]
            if quantity > 1e-8:
                self.buy(quantity)

        elif rsi > overbought and portfolio.has_position(self.symbol):
            self.close_position(portfolio)
