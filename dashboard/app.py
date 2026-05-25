import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data.data_manager import DataManager
from engine.backtester import Backtester
from strategies.examples.sma_crossover import SMACrossover
from strategies.examples.rsi_strategy import RSIStrategy

st.set_page_config(
    page_title="Backtester Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .metric-card {
        background-color: #1e2130;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
    }
    .metric-positive { color: #00d4aa; font-size: 1.6rem; font-weight: bold; }
    .metric-negative { color: #ff4b4b; font-size: 1.6rem; font-weight: bold; }
    .metric-neutral  { color: #a0a0b0; font-size: 1.6rem; font-weight: bold; }
    .metric-label    { color: #888; font-size: 0.8rem; margin-top: 4px; }
    .stButton > button { width: 100%; background-color: #21c55d; color: white;
                         font-size: 1rem; font-weight: bold; border: none;
                         border-radius: 6px; padding: 0.6rem 1rem; }
    .stButton > button:hover { background-color: #16a34a; }
</style>
""", unsafe_allow_html=True)


def sidebar_config():
    st.sidebar.title("Backtester Pro")

    st.sidebar.header("Dati")
    market = st.sidebar.selectbox("Mercato", ["Stock", "Crypto", "CSV"], index=0)

    if market == "Stock":
        symbol = st.sidebar.text_input("Simbolo", value="AAPL")
        filepath = None
        exchange = "binance"
    elif market == "Crypto":
        symbol = st.sidebar.text_input("Simbolo", value="BTC/USDT")
        exchange = st.sidebar.selectbox("Exchange", ["binance", "coinbase", "kraken", "okx"], index=0)
        filepath = None
    else:
        filepath = st.sidebar.text_input("Percorso CSV", value="")
        symbol = st.sidebar.text_input("Simbolo (etichetta)", value="ASSET")
        exchange = "binance"

    default_end = date.today()
    default_start = default_end - timedelta(days=730)
    start_date = st.sidebar.date_input("Data inizio", value=default_start)
    end_date = st.sidebar.date_input("Data fine", value=default_end)

    timeframe_opts = ["1d", "1wk", "1h", "15m", "5m", "1m"]
    timeframe = st.sidebar.selectbox("Timeframe", timeframe_opts, index=0)

    st.sidebar.header("Strategia")
    strategy_name = st.sidebar.selectbox("Strategia", ["SMA Crossover", "RSI Strategy"], index=0)

    strategy_params = {}
    if strategy_name == "SMA Crossover":
        strategy_params["fast_period"] = st.sidebar.number_input("Fast Period", min_value=2, max_value=200, value=20, step=1)
        strategy_params["slow_period"] = st.sidebar.number_input("Slow Period", min_value=2, max_value=500, value=50, step=1)
    else:
        strategy_params["period"] = st.sidebar.number_input("RSI Period", min_value=2, max_value=100, value=14, step=1)
        strategy_params["oversold"] = st.sidebar.slider("Oversold Level", min_value=5, max_value=50, value=30)
        strategy_params["overbought"] = st.sidebar.slider("Overbought Level", min_value=50, max_value=95, value=70)

    st.sidebar.header("Configurazione")
    capital = st.sidebar.number_input("Capitale iniziale ($)", min_value=100, max_value=10_000_000, value=10_000, step=100)
    commission = st.sidebar.slider("Commissione (%)", min_value=0.0, max_value=1.0, value=0.1, step=0.01) / 100
    slippage = st.sidebar.slider("Slippage (%)", min_value=0.0, max_value=1.0, value=0.05, step=0.01) / 100

    run = st.sidebar.button("Esegui Backtest")

    return {
        "market": market,
        "symbol": symbol,
        "filepath": filepath,
        "exchange": exchange,
        "start": str(start_date),
        "end": str(end_date),
        "timeframe": timeframe,
        "strategy_name": strategy_name,
        "strategy_params": strategy_params,
        "capital": capital,
        "commission": commission,
        "slippage": slippage,
        "run": run,
    }


def build_equity_chart(equity_curve, data: pd.DataFrame, capital: float) -> go.Figure:
    timestamps = [t for t, _ in equity_curve]
    values = [v for _, v in equity_curve]

    bh_values = None
    if not data.empty and len(timestamps) > 0:
        start_price = data["close"].iloc[0]
        bh_series = (data["close"] / start_price * capital).reindex(
            pd.DatetimeIndex(timestamps), method="nearest"
        )
        bh_values = bh_series.values

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=timestamps, y=values,
        mode="lines", name="Strategy",
        line=dict(color="#00d4aa", width=2),
        fill="tozeroy", fillcolor="rgba(0, 212, 170, 0.05)",
    ))

    if bh_values is not None:
        fig.add_trace(go.Scatter(
            x=timestamps, y=bh_values.tolist(),
            mode="lines", name="Buy & Hold",
            line=dict(color="#888", width=1.5, dash="dash"),
        ))

    fig.update_layout(
        template="plotly_dark",
        height=420,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(x=0.01, y=0.99),
        xaxis_title="Data",
        yaxis_title="Valore ($)",
        hovermode="x unified",
    )
    return fig


def build_drawdown_chart(equity_curve) -> go.Figure:
    values = pd.Series([v for _, v in equity_curve])
    timestamps = [t for t, _ in equity_curve]

    rolling_max = values.cummax()
    drawdown = (values - rolling_max) / rolling_max * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=timestamps, y=drawdown.tolist(),
        mode="lines", name="Drawdown",
        line=dict(color="#ff4b4b", width=1.5),
        fill="tozeroy", fillcolor="rgba(255, 75, 75, 0.2)",
    ))

    fig.update_layout(
        template="plotly_dark",
        height=360,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_title="Data",
        yaxis_title="Drawdown (%)",
        hovermode="x unified",
    )
    return fig


def build_trades_df(trades: list) -> pd.DataFrame:
    sell_trades = [t for t in trades if t.get("side") == "sell"]
    if not sell_trades:
        return pd.DataFrame()

    rows = []
    for t in sell_trades:
        pnl = t.get("pnl")
        pnl_pct = t.get("pnl_pct")
        rows.append({
            "Timestamp": t.get("timestamp"),
            "Tipo": t.get("side", "").upper(),
            "Prezzo": f"${t.get('price', 0):.4f}",
            "Quantità": f"{t.get('quantity', 0):.6f}",
            "P&L ($)": f"{pnl:+.2f}" if pnl is not None else "-",
            "P&L (%)": f"{pnl_pct:+.2f}%" if pnl_pct is not None else "-",
        })

    return pd.DataFrame(rows)


def metric_html(label: str, value: str, positive: bool | None = None) -> str:
    if positive is True:
        cls = "metric-positive"
    elif positive is False:
        cls = "metric-negative"
    else:
        cls = "metric-neutral"
    return f"""
    <div class="metric-card">
        <div class="{cls}">{value}</div>
        <div class="metric-label">{label}</div>
    </div>
    """


def display_results(result: dict, data: pd.DataFrame, capital: float):
    metrics = result["metrics"]
    equity_curve = result["equity_curve"]
    trades = result["trades"]

    st.markdown("---")
    st.subheader("Risultati")

    cols = st.columns(4)
    tr = metrics["total_return"]
    sr = metrics["sharpe_ratio"]
    md = metrics["max_drawdown"]
    wr = metrics["win_rate"]

    with cols[0]:
        st.markdown(metric_html("Total Return", f"{tr:+.2f}%", tr >= 0), unsafe_allow_html=True)
    with cols[1]:
        st.markdown(metric_html("Sharpe Ratio", f"{sr:.3f}", sr >= 1), unsafe_allow_html=True)
    with cols[2]:
        st.markdown(metric_html("Max Drawdown", f"{md:.2f}%", md > -10 if md != 0 else None), unsafe_allow_html=True)
    with cols[3]:
        st.markdown(metric_html("Win Rate", f"{wr:.1f}%", wr >= 50), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["Equity Curve", "Drawdown", "Lista Trade", "Metriche Dettagliate"])

    with tab1:
        fig = build_equity_chart(equity_curve, data, capital)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        fig = build_drawdown_chart(equity_curve)
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        df_trades = build_trades_df(trades)
        if df_trades.empty:
            st.info("Nessun trade chiuso durante il backtest.")
        else:
            st.dataframe(df_trades, use_container_width=True, hide_index=True)

    with tab4:
        metrics_display = {
            "Total Return (%)": metrics["total_return"],
            "CAGR (%)": metrics["cagr"],
            "Sharpe Ratio": metrics["sharpe_ratio"],
            "Sortino Ratio": metrics["sortino_ratio"],
            "Max Drawdown (%)": metrics["max_drawdown"],
            "Max Drawdown Duration (giorni)": metrics["max_drawdown_duration"],
            "Calmar Ratio": metrics["calmar_ratio"],
            "Win Rate (%)": metrics["win_rate"],
            "Profit Factor": metrics["profit_factor"],
            "Totale Trade": metrics["total_trades"],
            "Avg Trade Return (%)": metrics["avg_trade_return"],
        }
        df_metrics = pd.DataFrame(
            list(metrics_display.items()), columns=["Metrica", "Valore"]
        )
        st.dataframe(df_metrics, use_container_width=True, hide_index=True)


def main():
    config = sidebar_config()

    st.title("Backtester Pro")
    st.caption("Backtest event-driven con dati storici reali. Configurare i parametri nella sidebar e premere Esegui.")

    if not config["run"]:
        st.info("Configura i parametri nella sidebar e premi **Esegui Backtest** per iniziare.")
        return

    with st.spinner("Caricamento dati in corso..."):
        try:
            dm = DataManager()
            data = dm.get(
                symbol=config["symbol"],
                market=config["market"].lower(),
                start=config["start"],
                end=config["end"],
                interval=config["timeframe"],
                exchange=config["exchange"],
                filepath=config["filepath"],
            )
        except Exception as e:
            st.error(f"Errore nel caricamento dati: {e}")
            return

    if data.empty:
        st.error("I dati scaricati sono vuoti. Verificare simbolo e date.")
        return

    st.success(f"Dati caricati: {len(data)} barre ({data.index[0].date()} → {data.index[-1].date()})")

    with st.spinner("Esecuzione backtest..."):
        try:
            params = config["strategy_params"]
            symbol = config["symbol"]

            if config["strategy_name"] == "SMA Crossover":
                strategy = SMACrossover(
                    symbol=symbol,
                    fast_period=int(params["fast_period"]),
                    slow_period=int(params["slow_period"]),
                )
            else:
                strategy = RSIStrategy(
                    symbol=symbol,
                    period=int(params["period"]),
                    oversold=float(params["oversold"]),
                    overbought=float(params["overbought"]),
                )

            bt = Backtester(
                initial_capital=float(config["capital"]),
                commission=float(config["commission"]),
                slippage=float(config["slippage"]),
            )
            result = bt.run(data, strategy)
        except Exception as e:
            st.error(f"Errore durante il backtest: {e}")
            return

    display_results(result, data, float(config["capital"]))


if __name__ == "__main__":
    main()
