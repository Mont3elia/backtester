import pandas as pd
import yfinance as yf

VALID_INTERVALS = {"1m", "5m", "15m", "1h", "1d", "1wk"}


def fetch(symbol: str, start: str, end: str, interval: str = "1d") -> pd.DataFrame:
    if interval not in VALID_INTERVALS:
        raise ValueError(f"Interval '{interval}' not supported. Choose from: {VALID_INTERVALS}")

    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start, end=end, interval=interval, auto_adjust=True)

    if df.empty:
        raise ValueError(f"No data returned for symbol '{symbol}' in the given date range.")

    df = df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })

    df = df[["open", "high", "low", "close", "volume"]]
    df.index = pd.to_datetime(df.index)

    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    df = df.dropna()
    return df
