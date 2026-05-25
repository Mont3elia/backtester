from typing import TYPE_CHECKING

import pandas as pd

try:
    from ..base_strategy import BaseStrategy
except ImportError:
    from strategies.base_strategy import BaseStrategy

if TYPE_CHECKING:
    from engine.portfolio import Portfolio


class EMACrossover(BaseStrategy):
    name = "EMA Crossover"
    description = "Golden/death cross tra due medie mobili esponenziali"
    param_schema = {
        "fast_period": {"type": "int", "default": 20, "min": 2, "max": 200, "label": "Fast Period"},
        "slow_period": {"type": "int", "default": 50, "min": 5, "max": 500, "label": "Slow Period"},
    }

    def __init__(self, symbol: str, **kwargs):
        super().__init__(symbol, **kwargs)
        self._fast_ema: float = None
        self._slow_ema: float = None
        self._prev_fast: float = None
        self._prev_slow: float = None
        self._bar_count: int = 0

    def _on_reset(self):
        self._fast_ema = None
        self._slow_ema = None
        self._prev_fast = None
        self._prev_slow = None
        self._bar_count = 0

    def _update_ema(self, prev_ema: float, price: float, period: int) -> float:
        alpha = 2.0 / (period + 1)
        if prev_ema is None:
            return price
        return alpha * price + (1 - alpha) * prev_ema

    def on_bar(self, bar: pd.Series, portfolio: "Portfolio"):
        self._current_bar = bar
        self._current_timestamp = bar.name if hasattr(bar, "name") else pd.Timestamp.now()

        price = bar["close"]
        fast = self.params["fast_period"]
        slow = self.params["slow_period"]

        self._bar_count += 1

        self._prev_fast = self._fast_ema
        self._prev_slow = self._slow_ema

        self._fast_ema = self._update_ema(self._fast_ema, price, fast)
        self._slow_ema = self._update_ema(self._slow_ema, price, slow)

        if self._bar_count <= slow:
            return

        if self._prev_fast is None or self._prev_slow is None:
            return

        bullish_cross = self._prev_fast <= self._prev_slow and self._fast_ema > self._slow_ema
        bearish_cross = self._prev_fast >= self._prev_slow and self._fast_ema < self._slow_ema

        if bullish_cross and not portfolio.has_position(self.symbol):
            quantity = portfolio.cash / price
            if quantity > 1e-8:
                self.buy(quantity)

        elif bearish_cross and portfolio.has_position(self.symbol):
            self.close_position(portfolio)
