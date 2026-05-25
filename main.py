import csv
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.data_manager import DataManager
from engine.backtester import Backtester
from strategies.examples.sma_crossover import SMACrossover


def main():
    end = date.today().strftime("%Y-%m-%d")
    start = (date.today() - timedelta(days=730)).strftime("%Y-%m-%d")
    symbol = "AAPL"

    print(f"Scaricamento dati {symbol} dal {start} al {end}...")
    dm = DataManager()
    data = dm.get(symbol=symbol, market="stock", start=start, end=end, interval="1d")
    print(f"Dati caricati: {len(data)} barre\n")

    strategy = SMACrossover(symbol=symbol, fast_period=20, slow_period=50)
    bt = Backtester(initial_capital=10_000.0, commission=0.001, slippage=0.0005)

    print("Esecuzione backtest SMACrossover (20/50)...")
    result = bt.run(data, strategy)

    metrics = result["metrics"]
    print("\n=== METRICHE ===")
    print(f"  Total Return:         {metrics['total_return']:>8.2f}%")
    print(f"  CAGR:                 {metrics['cagr']:>8.2f}%")
    print(f"  Sharpe Ratio:         {metrics['sharpe_ratio']:>8.3f}")
    print(f"  Sortino Ratio:        {metrics['sortino_ratio']:>8.3f}")
    print(f"  Max Drawdown:         {metrics['max_drawdown']:>8.2f}%")
    print(f"  Max DD Duration:      {metrics['max_drawdown_duration']:>8} giorni")
    print(f"  Calmar Ratio:         {metrics['calmar_ratio']:>8.3f}")
    print(f"  Win Rate:             {metrics['win_rate']:>8.2f}%")
    print(f"  Profit Factor:        {metrics['profit_factor']:>8.3f}")
    print(f"  Totale Trade:         {metrics['total_trades']:>8}")
    print(f"  Avg Trade Return:     {metrics['avg_trade_return']:>8.2f}%")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "equity_curve.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "equity"])
        for ts, eq in result["equity_curve"]:
            writer.writerow([ts, round(eq, 4)])

    print(f"\nEquity curve salvata in: {out_path}")


if __name__ == "__main__":
    main()
