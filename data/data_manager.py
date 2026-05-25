from typing import Optional

import pandas as pd

try:
    from .providers import ccxt_fetch, csv_fetch, yfinance_fetch
except ImportError:
    from data.providers import ccxt_fetch, csv_fetch, yfinance_fetch


class DataManager:
    def __init__(self):
        self._cache: dict = {}

    def get(
        self,
        symbol: str,
        market: str,
        start: str,
        end: str,
        interval: str = "1d",
        exchange: str = "binance",
        filepath: Optional[str] = None,
    ) -> pd.DataFrame:
        cache_key = (symbol, market, start, end, interval)
        if cache_key in self._cache:
            return self._cache[cache_key]

        market = market.lower()

        if market == "stock":
            df = yfinance_fetch(symbol, start, end, interval)
        elif market == "crypto":
            df = ccxt_fetch(symbol, start, end, interval, exchange=exchange)
        elif market == "forex":
            df = yfinance_fetch(symbol, start, end, interval)
        elif market == "csv":
            if not filepath:
                raise ValueError("filepath must be provided for market='csv'")
            df = csv_fetch(filepath, start=start, end=end)
        else:
            raise ValueError(f"Unknown market type: '{market}'. Choose from: stock, crypto, forex, csv")

        self._cache[cache_key] = df
        return df

    def clear_cache(self):
        self._cache.clear()
