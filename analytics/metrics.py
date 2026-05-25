from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def compute_metrics(
    equity_curve: List[Tuple[pd.Timestamp, float]],
    trades: List[dict],
    risk_free_rate: float = 0.02,
) -> Dict:
    if not equity_curve or len(equity_curve) < 2:
        return _empty_metrics()

    timestamps = [t for t, _ in equity_curve]
    values = np.array([v for _, v in equity_curve], dtype=float)

    initial = values[0]
    final = values[-1]

    total_return = (final / initial - 1) * 100 if initial > 0 else 0.0

    start_dt = pd.Timestamp(timestamps[0])
    end_dt = pd.Timestamp(timestamps[-1])
    years = max((end_dt - start_dt).days / 365.25, 1 / 365.25)
    cagr = ((final / initial) ** (1 / years) - 1) * 100 if initial > 0 else 0.0

    daily_returns = pd.Series(values).pct_change().dropna()
    trading_days = 252

    excess_returns = daily_returns - risk_free_rate / trading_days
    if daily_returns.std() > 0:
        sharpe = (excess_returns.mean() / daily_returns.std()) * np.sqrt(trading_days)
    else:
        sharpe = 0.0

    downside = daily_returns[daily_returns < 0]
    downside_std = downside.std() if len(downside) > 1 else 0.0
    if downside_std > 0:
        sortino = (excess_returns.mean() / downside_std) * np.sqrt(trading_days)
    else:
        sortino = 0.0

    rolling_max = pd.Series(values).cummax()
    drawdown_series = (pd.Series(values) - rolling_max) / rolling_max
    max_drawdown = drawdown_series.min() * 100

    dd_duration = _max_drawdown_duration(values, timestamps)

    calmar = (cagr / abs(max_drawdown)) if max_drawdown != 0 else 0.0

    sell_trades = [t for t in trades if t.get("side") == "sell" and t.get("pnl") is not None]
    total_trades = len(sell_trades)

    if total_trades > 0:
        winning = [t for t in sell_trades if t["pnl"] > 0]
        losing = [t for t in sell_trades if t["pnl"] <= 0]
        win_rate = len(winning) / total_trades * 100
        gross_profit = sum(t["pnl"] for t in winning)
        gross_loss = abs(sum(t["pnl"] for t in losing))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        pnl_pcts = [t["pnl_pct"] for t in sell_trades if t.get("pnl_pct") is not None]
        avg_trade_return = np.mean(pnl_pcts) if pnl_pcts else 0.0
    else:
        win_rate = 0.0
        profit_factor = 0.0
        avg_trade_return = 0.0

    return {
        "total_return": round(total_return, 2),
        "cagr": round(cagr, 2),
        "sharpe_ratio": round(sharpe, 3),
        "sortino_ratio": round(sortino, 3),
        "max_drawdown": round(max_drawdown, 2),
        "max_drawdown_duration": dd_duration,
        "calmar_ratio": round(calmar, 3),
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 3),
        "total_trades": total_trades,
        "avg_trade_return": round(avg_trade_return, 2),
    }


def _max_drawdown_duration(values: np.ndarray, timestamps: list) -> int:
    peak_idx = 0
    max_duration = 0
    current_duration = 0
    peak_val = values[0]

    for i in range(1, len(values)):
        if values[i] >= peak_val:
            peak_val = values[i]
            peak_idx = i
            current_duration = 0
        else:
            try:
                days = (pd.Timestamp(timestamps[i]) - pd.Timestamp(timestamps[peak_idx])).days
                current_duration = days
            except Exception:
                current_duration += 1
            max_duration = max(max_duration, current_duration)

    return max_duration


def _empty_metrics() -> Dict:
    return {
        "total_return": 0.0,
        "cagr": 0.0,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "max_drawdown": 0.0,
        "max_drawdown_duration": 0,
        "calmar_ratio": 0.0,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "total_trades": 0,
        "avg_trade_return": 0.0,
    }
