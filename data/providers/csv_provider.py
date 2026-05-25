import io
from pathlib import Path
from typing import Optional

import pandas as pd

COLUMN_ALIASES = {
    "open": ["open", "o", "Open", "OPEN"],
    "high": ["high", "h", "High", "HIGH"],
    "low": ["low", "l", "Low", "LOW"],
    "close": ["close", "c", "Close", "CLOSE", "adj close", "adj_close"],
    "volume": ["volume", "v", "Volume", "VOLUME", "vol"],
}

DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y%m%d",
    "%d-%m-%Y",
]


def _detect_separator(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        sample = f.read(4096)

    sniffer = __import__("csv").Sniffer()
    try:
        dialect = sniffer.sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except Exception:
        return ","


def _parse_dates(series: pd.Series) -> pd.Series:
    for fmt in DATE_FORMATS:
        try:
            return pd.to_datetime(series, format=fmt)
        except (ValueError, TypeError):
            continue
    return pd.to_datetime(series, infer_datetime_format=True)


def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
    col_lower = {c: c.strip().lower().replace(" ", "_") for c in df.columns}
    rename = {}
    for std_name, aliases in COLUMN_ALIASES.items():
        for col, normalized in col_lower.items():
            if normalized in [a.lower().replace(" ", "_") for a in aliases]:
                rename[col] = std_name
                break
    return df.rename(columns=rename)


def fetch(
    filepath: str,
    date_col: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> pd.DataFrame:
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {filepath}")

    sep = _detect_separator(filepath)
    df = pd.read_csv(filepath, sep=sep, engine="python")

    if df.empty:
        raise ValueError(f"CSV file '{filepath}' is empty.")

    df = _map_columns(df)

    if date_col and date_col in df.columns:
        df.index = _parse_dates(df[date_col])
        df = df.drop(columns=[date_col])
    else:
        date_candidates = [c for c in df.columns if "date" in c.lower() or "time" in c.lower()]
        if date_candidates:
            df.index = _parse_dates(df[date_candidates[0]])
            df = df.drop(columns=[date_candidates[0]])
        elif df.index.dtype == object:
            df.index = _parse_dates(pd.Series(df.index))

    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    df.index.name = "timestamp"

    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns after mapping: {missing}. Found: {list(df.columns)}")

    df = df[required]
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.dropna()
    df = df.sort_index()

    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index < pd.Timestamp(end)]

    return df
