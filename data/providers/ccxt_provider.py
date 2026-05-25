import time
from datetime import datetime, timezone

import ccxt
import pandas as pd

INTERVAL_MAP = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "1d": "1d",
    "1wk": "1w",
}


def _to_ms(dt_str: str) -> int:
    dt = datetime.strptime(dt_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def fetch(
    symbol: str,
    start: str,
    end: str,
    interval: str = "1d",
    exchange: str = "binance",
) -> pd.DataFrame:
    if interval not in INTERVAL_MAP:
        raise ValueError(f"Interval '{interval}' not supported. Choose from: {list(INTERVAL_MAP)}")

    try:
        exchange_class = getattr(ccxt, exchange)
    except AttributeError:
        raise ValueError(f"Exchange '{exchange}' not found in ccxt.")

    ex = exchange_class({"enableRateLimit": True})

    tf = INTERVAL_MAP[interval]
    since = _to_ms(start)
    end_ms = _to_ms(end)
    limit = 1000
    all_ohlcv = []

    while since < end_ms:
        ohlcv = ex.fetch_ohlcv(symbol, timeframe=tf, since=since, limit=limit)
        if not ohlcv:
            break

        all_ohlcv.extend(ohlcv)
        last_ts = ohlcv[-1][0]

        if last_ts >= end_ms or len(ohlcv) < limit:
            break

        since = last_ts + 1
        time.sleep(ex.rateLimit / 1000)

    if not all_ohlcv:
        raise ValueError(f"No data returned for '{symbol}' on {exchange}.")

    df = pd.DataFrame(all_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_localize(None)
    df = df.set_index("timestamp")
    df = df[df.index < pd.Timestamp(end)]
    df = df[df.index >= pd.Timestamp(start)]
    df = df.dropna()
    df = df[~df.index.duplicated(keep="first")]
    return df
