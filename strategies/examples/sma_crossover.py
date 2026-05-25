from collections import deque
from typing import TYPE_CHECKING

import pandas as pd

try:
    from ..base_strategy import BaseStrategy
except ImportError:
    from strategies.base_strategy import BaseStrategy

if TYPE_CHECKING:
    from engine.portfolio import Portfolio


class SMACrossover(BaseStrategy):
    def __init__(self, symbol: str, fast_period: int = 20, slow_period: int = 50):
        super().__init__(symbol, params={"fast_period": fast_period, "slow_period": slow_period})
        self._prices: deque = deque(maxlen=slow_period)
        self._prev_fast: float = None
        self._prev_slow: float = None

    def _on_reset(self):
        slow_period = self.params.get("slow_period", 50)
        self._prices = deque(maxlen=slow_period)
        self._prev_fast = None
        self._prev_slow = None

    def _sma(self, n: int) -> float:
        if len(self._prices) < n:
            return None
        return sum(list(self._prices)[-n:]) / n

    def on_bar(self, bar: pd.Series, portfolio: "Portfolio"):
        self._current_bar = bar
        self._current_timestamp = bar.name if hasattr(bar, "name") else pd.Timestamp.now()

        self._prices.append(bar["close"])

        fast = self.params["fast_period"]
        slow = self.params["slow_period"]

        fast_sma = self._sma(fast)
        slow_sma = self._sma(slow)

        if fast_sma is None or slow_sma is None:
            self._prev_fast = fast_sma
            self._prev_slow = slow_sma
            return

        bullish_cross = (
            self._prev_fast is not None
            and self._prev_slow is not None
            and self._prev_fast <= self._prev_slow
            and fast_sma > slow_sma
        )
        bearish_cross = (
            self._prev_fast is not None
            and self._prev_slow is not None
            and self._prev_fast >= self._prev_slow
            and fast_sma < slow_sma
        )

        if bullish_cross and not portfolio.has_position(self.symbol):
            quantity = portfolio.cash / bar["close"]
            if quantity > 1e-8:
                self.buy(quantity)

        elif bearish_cross and portfolio.has_position(self.symbol):
            self.close_position(portfolio)

        self._prev_fast = fast_sma
        self._prev_slow = slow_sma
