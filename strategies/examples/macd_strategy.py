from typing import TYPE_CHECKING

import pandas as pd

try:
    from ..base_strategy import BaseStrategy
except ImportError:
    from strategies.base_strategy import BaseStrategy

if TYPE_CHECKING:
    from engine.portfolio import Portfolio


class MACDStrategy(BaseStrategy):
    name = "MACD Strategy"
    description = "Incrocio MACD line / signal line: rialzista = buy, ribassista = sell"
    param_schema = {
        "fast": {"type": "int", "default": 12, "min": 2, "max": 100, "label": "Fast EMA"},
        "slow": {"type": "int", "default": 26, "min": 5, "max": 200, "label": "Slow EMA"},
        "signal": {"type": "int", "default": 9, "min": 2, "max": 50, "label": "Signal Period"},
    }

    def __init__(self, symbol: str, **kwargs):
        super().__init__(symbol, **kwargs)
        self._fast_ema: float = None
        self._slow_ema: float = None
        self._signal_ema: float = None
        self._prev_macd: float = None
        self._prev_signal: float = None
        self._bar_count: int = 0

    def _on_reset(self):
        self._fast_ema = None
        self._slow_ema = None
        self._signal_ema = None
        self._prev_macd = None
        self._prev_signal = None
        self._bar_count = 0

    def _ema_step(self, prev: float, value: float, period: int) -> float:
        alpha = 2.0 / (period + 1)
        if prev is None:
            return value
        return alpha * value + (1 - alpha) * prev

    def on_bar(self, bar: pd.Series, portfolio: "Portfolio"):
        self._current_bar = bar
        self._current_timestamp = bar.name if hasattr(bar, "name") else pd.Timestamp.now()

        price = bar["close"]
        fast = self.params["fast"]
        slow = self.params["slow"]
        signal = self.params["signal"]

        self._bar_count += 1

        self._fast_ema = self._ema_step(self._fast_ema, price, fast)
        self._slow_ema = self._ema_step(self._slow_ema, price, slow)

        if self._bar_count < slow:
            return

        macd_line = self._fast_ema - self._slow_ema
        self._signal_ema = self._ema_step(self._signal_ema, macd_line, signal)
        signal_line = self._signal_ema

        if self._bar_count < slow + signal:
            self._prev_macd = macd_line
            self._prev_signal = signal_line
            return

        if self._prev_macd is None or self._prev_signal is None:
            self._prev_macd = macd_line
            self._prev_signal = signal_line
            return

        bullish_cross = self._prev_macd <= self._prev_signal and macd_line > signal_line
        bearish_cross = self._prev_macd >= self._prev_signal and macd_line < signal_line

        if bullish_cross and not portfolio.has_position(self.symbol):
            quantity = portfolio.cash / price
            if quantity > 1e-8:
                self.buy(quantity)

        elif bearish_cross and portfolio.has_position(self.symbol):
            self.close_position(portfolio)

        self._prev_macd = macd_line
        self._prev_signal = signal_line
