import sys
import os
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data.data_manager import DataManager
from engine.backtester import Backtester
from strategies.registry import discover, get_all
from strategies.base_strategy import BaseStrategy

try:
    from streamlit_ace import st_ace
    _ACE_AVAILABLE = True
except ImportError:
    _ACE_AVAILABLE = False

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

# Always discover strategies at module load so custom ones are always registered
discover()

CUSTOM_DIR = Path(__file__).parent.parent / "strategies" / "custom"

TEMPLATE = '''\
from strategies.base_strategy import BaseStrategy

class MiaStrategia(BaseStrategy):
    name = "Mia Strategia"
    description = "Descrizione breve della strategia"
    param_schema = {
        "period": {"type": "int", "default": 20, "min": 2, "max": 200, "label": "Periodo"},
        "threshold": {"type": "float", "default": 0.5, "min": 0.0, "max": 5.0, "label": "Soglia"},
    }

    def on_bar(self, bar, portfolio):
        # bar è un pd.Series con: open, high, low, close, volume
        # self.prices è una lista dei prezzi close visti finora
        # self.period, self.threshold sono accessibili direttamente
        #
        # Per comprare:  self.buy(quantity)
        # Per vendere:   self.sell(quantity)
        # Per chiudere:  self.close_position()

        self.prices.append(bar["close"])

        if len(self.prices) < self.period:
            return

        # Esempio: media mobile semplice
        sma = sum(self.prices[-self.period:]) / self.period
        current_price = bar["close"]

        # Logica di esempio: compra se prezzo sotto la media, vendi se sopra
        position = portfolio.positions.get(self.symbol)

        if current_price < sma * (1 - self.threshold / 100) and not position:
            self.buy(1)
        elif current_price > sma and position and position.is_open():
            self.close_position()
'''


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_code(code: str):
    """
    Execute the code string and return the first BaseStrategy subclass found,
    or raise ValueError with a human-readable message.
    """
    namespace = {}
    try:
        exec(code, namespace)  # noqa: S102
    except Exception as exc:
        raise ValueError(f"Errore di esecuzione: {exc}") from exc

    cls = None
    for obj in namespace.values():
        if (
            isinstance(obj, type)
            and issubclass(obj, BaseStrategy)
            and obj is not BaseStrategy
        ):
            cls = obj
            break

    if cls is None:
        raise ValueError("Nessuna classe che eredita da BaseStrategy trovata.")

    return cls


def _list_custom_files():
    """Return sorted list of .py files in strategies/custom/ (excluding __init__)."""
    return sorted(
        p for p in CUSTOM_DIR.glob("*.py") if p.name != "__init__.py"
    )


# ---------------------------------------------------------------------------
# Backtest page helpers (unchanged from original)
# ---------------------------------------------------------------------------

def sidebar_config():
    st.sidebar.header("Dati")
    market_label = st.sidebar.selectbox(
        "Mercato",
        ["Azioni", "Crypto", "Forex", "Futures"],
        index=0,
    )

    exchange = "binance"
    filepath = None

    if market_label == "Azioni":
        market = "stock"
        symbol = st.sidebar.text_input("Simbolo", value="AAPL", placeholder="AAPL")
    elif market_label == "Crypto":
        market = "crypto"
        symbol = st.sidebar.text_input("Simbolo", value="BTC/USDT", placeholder="BTC/USDT")
        exchange = st.sidebar.selectbox("Exchange", ["binance", "coinbase", "kraken", "okx"], index=0)
    elif market_label == "Forex":
        market = "forex"
        symbol = st.sidebar.text_input("Simbolo", value="EURUSD", placeholder="EURUSD")
        st.sidebar.caption("es. EURUSD, GBPJPY, USDJPY")
    else:  # Futures
        market = "futures"
        symbol = st.sidebar.text_input("Simbolo", value="ES", placeholder="ES")
        st.sidebar.caption("es. ES, NQ, CL, GC")

    default_end = date.today()
    default_start = default_end - timedelta(days=730)
    start_date = st.sidebar.date_input("Data inizio", value=default_start)
    end_date = st.sidebar.date_input("Data fine", value=default_end)

    timeframe_opts = ["1d", "1wk", "1h", "15m", "5m", "1m"]
    timeframe = st.sidebar.selectbox("Timeframe", timeframe_opts, index=0)

    st.sidebar.header("Strategia")
    strategies = get_all()
    strategy_names = list(strategies.keys())
    strategy_name = st.sidebar.selectbox("Strategia", strategy_names, index=0)
    strategy_cls = strategies[strategy_name]

    if strategy_cls.description:
        st.sidebar.caption(strategy_cls.description)

    strategy_params = {}
    if strategy_cls.param_schema:
        for param, schema in strategy_cls.param_schema.items():
            if schema["type"] == "int":
                val = st.sidebar.number_input(
                    schema["label"],
                    min_value=schema["min"],
                    max_value=schema["max"],
                    value=schema["default"],
                    step=1,
                )
                strategy_params[param] = int(val)
            elif schema["type"] == "float":
                val = st.sidebar.slider(
                    schema["label"],
                    min_value=float(schema["min"]),
                    max_value=float(schema["max"]),
                    value=float(schema["default"]),
                )
                strategy_params[param] = float(val)
            elif schema["type"] == "bool":
                val = st.sidebar.checkbox(schema["label"], value=schema["default"])
                strategy_params[param] = bool(val)

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
        "strategy_cls": strategy_cls,
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
            "Quantita": f"{t.get('quantity', 0):.6f}",
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


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def show_backtest_page():
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
                market=config["market"],
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

    st.success(f"Dati caricati: {len(data)} barre ({data.index[0].date()} - {data.index[-1].date()})")

    with st.spinner("Esecuzione backtest..."):
        try:
            strategy_cls = config["strategy_cls"]
            symbol = config["symbol"]
            strategy_params = config["strategy_params"]

            strategy = strategy_cls(symbol=symbol, **strategy_params)

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


def _render_validate_save(code: str, key_suffix: str):
    """Helper riutilizzabile: bottoni Valida + Salva + Download per un blocco di codice."""
    btn_col1, btn_col2 = st.columns(2)

    with btn_col1:
        if st.button("Valida", key=f"validate_{key_suffix}", use_container_width=True):
            if not code or not code.strip():
                st.error("L'editor è vuoto.")
            else:
                try:
                    cls = _validate_code(code)
                    st.success(
                        f"Strategia '{cls.name}' valida! "
                        f"Parametri: {list(cls.param_schema.keys())}"
                    )
                except ValueError as exc:
                    st.error(str(exc))

    with btn_col2:
        if st.button("Salva Strategia", key=f"save_{key_suffix}", type="primary", use_container_width=True):
            if not code or not code.strip():
                st.error("L'editor è vuoto.")
            else:
                try:
                    cls = _validate_code(code)
                    dest = CUSTOM_DIR / f"{cls.__name__}.py"
                    dest.write_text(code, encoding="utf-8")
                    discover()
                    st.success(
                        f"Strategia '{cls.name}' salvata! "
                        "Torna al Backtest per usarla."
                    )
                    st.download_button(
                        "Download .py",
                        data=code,
                        file_name=f"{cls.__name__}.py",
                        mime="text/plain",
                        key=f"download_{key_suffix}",
                    )
                except ValueError as exc:
                    st.error(str(exc))
                except Exception as exc:
                    st.error(f"Errore nel salvataggio: {exc}")


def show_editor_page():
    st.title("Editor Strategie")
    st.caption("Scrivi strategie Python personalizzate. Appaiono subito nel menu Backtest.")

    col_list, col_editor = st.columns([1, 2])

    # ------------------------------------------------------------------
    # Left column: list of saved custom strategies
    # ------------------------------------------------------------------
    with col_list:
        st.subheader("Le tue strategie")

        custom_files = _list_custom_files()

        if not custom_files:
            st.info("Nessuna strategia custom salvata.")
        else:
            for path in custom_files:
                strategy_name = path.stem
                col_name, col_btn = st.columns([3, 1])
                col_name.write(strategy_name)
                if col_btn.button("Elimina", key=f"delete_{strategy_name}"):
                    path.unlink(missing_ok=True)
                    discover()
                    st.rerun()

        st.warning(
            "Le strategie salvate qui persistono finché l'app è in esecuzione. "
            "Per renderle permanenti, scaricale e aggiungile al repository GitHub."
        )

    # ------------------------------------------------------------------
    # Right column: three tabs — Codice / Descrizione AI / Wizard
    # ------------------------------------------------------------------
    with col_editor:
        st.subheader("Nuova Strategia")

        tab_code, tab_ai, tab_wizard = st.tabs(["✏️ Codice", "🤖 Descrizione AI", "🧙 Wizard"])

        # ---- Tab 1: editor manuale ----
        with tab_code:
            st.info(
                "Scrivi la tua strategia. "
                "Usa self.buy(1), self.sell(1), self.close_position(). "
                "I prezzi close sono in self.prices."
            )

            if _ACE_AVAILABLE:
                code_manual = st_ace(
                    value=TEMPLATE,
                    language="python",
                    theme="monokai",
                    height=500,
                    font_size=14,
                    key="strategy_editor",
                )
            else:
                st.info(
                    "streamlit-ace non installato. Uso editor di testo standard. "
                    "Installa con: pip install streamlit-ace"
                )
                code_manual = st.text_area(
                    "Codice strategia",
                    value=TEMPLATE,
                    height=500,
                    key="strategy_editor_fallback",
                )

            _render_validate_save(code_manual, "manual")

        # ---- Tab 2: descrizione libera → AI ----
        with tab_ai:
            st.subheader("Descrivi la tua strategia")
            st.caption(
                "Scrivi in italiano come se stessi spiegando a un trader. "
                "L'AI genera il codice per te."
            )

            description = st.text_area(
                "Strategia",
                placeholder=(
                    "Es: Compra quando l'RSI scende sotto 30 e la media mobile a 50 giorni è in salita. "
                    "Vendi quando l'RSI supera 70 oppure il prezzo scende del 5% dal massimo."
                ),
                height=150,
                key="ai_description",
            )

            if st.button("Genera Codice", type="primary", key="btn_generate_ai"):
                if not description.strip():
                    st.warning("Scrivi prima la descrizione della strategia.")
                else:
                    with st.spinner("L'AI sta generando il codice..."):
                        try:
                            from dashboard.ai_generator import generate_strategy_from_description
                            generated = generate_strategy_from_description(description)
                            st.session_state["generated_code_ai"] = generated
                        except ValueError as exc:
                            st.error(str(exc))
                        except Exception as exc:
                            st.error(f"Errore nella generazione: {exc}")

            if "generated_code_ai" in st.session_state:
                st.subheader("Codice generato")
                st.caption("Puoi modificarlo prima di salvarlo.")

                if _ACE_AVAILABLE:
                    code_ai = st_ace(
                        value=st.session_state["generated_code_ai"],
                        language="python",
                        theme="monokai",
                        height=400,
                        key="ai_editor",
                    )
                else:
                    code_ai = st.text_area(
                        "Codice",
                        value=st.session_state["generated_code_ai"],
                        height=400,
                        key="ai_editor_fallback",
                    )

                _render_validate_save(code_ai, "ai")

        # ---- Tab 3: wizard guidato → AI ----
        with tab_wizard:
            st.subheader("Crea strategia guidata")
            st.caption("Rispondi alle domande e l'AI costruisce la strategia per te.")

            with st.form("wizard_form"):
                wiz_name = st.text_input("Nome della strategia", value="Mia Strategia")

                wiz_indicator = st.selectbox(
                    "Indicatore principale",
                    [
                        "RSI",
                        "SMA (Media Mobile)",
                        "EMA (Media Mobile Esponenziale)",
                        "MACD",
                        "Bollinger Bands",
                        "Stochastic",
                        "ATR",
                        "Personalizzato",
                    ],
                )

                wiz_entry = st.text_area(
                    "Quando COMPRARE?",
                    placeholder=(
                        "Es: quando RSI scende sotto 30\n"
                        "Es: quando il prezzo rompe al rialzo la banda superiore di Bollinger"
                    ),
                    height=100,
                )

                wiz_exit = st.text_area(
                    "Quando VENDERE?",
                    placeholder=(
                        "Es: quando RSI supera 70\n"
                        "Es: quando la media mobile cambia direzione"
                    ),
                    height=100,
                )

                wiz_stop_loss = st.select_slider(
                    "Stop Loss",
                    options=["No stop loss", "1%", "2%", "3%", "5%", "10%"],
                    value="No stop loss",
                )

                wiz_notes = st.text_input(
                    "Note aggiuntive (opzionale)",
                    placeholder="Es: opera solo su timeframe giornaliero, evita i venerdì...",
                )

                submitted = st.form_submit_button("Genera Strategia", type="primary")

            if submitted:
                with st.spinner("L'AI sta costruendo la tua strategia..."):
                    try:
                        from dashboard.ai_generator import generate_strategy_from_wizard
                        answers = {
                            "name": wiz_name,
                            "indicator": wiz_indicator,
                            "entry": wiz_entry,
                            "exit": wiz_exit,
                            "stop_loss": wiz_stop_loss,
                            "notes": wiz_notes,
                        }
                        generated = generate_strategy_from_wizard(answers)
                        st.session_state["generated_code_wizard"] = generated
                    except ValueError as exc:
                        st.error(str(exc))
                    except Exception as exc:
                        st.error(f"Errore: {exc}")

            if "generated_code_wizard" in st.session_state:
                st.subheader("Strategia generata")
                st.caption("Puoi modificarla prima di salvarla.")

                if _ACE_AVAILABLE:
                    code_wizard = st_ace(
                        value=st.session_state["generated_code_wizard"],
                        language="python",
                        theme="monokai",
                        height=400,
                        key="wizard_editor",
                    )
                else:
                    code_wizard = st.text_area(
                        "Codice",
                        value=st.session_state["generated_code_wizard"],
                        height=400,
                        key="wizard_editor_fallback",
                    )

                _render_validate_save(code_wizard, "wizard")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # Always re-discover so custom strategies are picked up on every run
    discover()

    st.sidebar.title("Backtester Pro")
    page = st.sidebar.radio(
        "Navigazione",
        ["Backtest", "Editor Strategie"],
        label_visibility="collapsed",
    )

    if page == "Backtest":
        show_backtest_page()
    elif page == "Editor Strategie":
        show_editor_page()


if __name__ == "__main__":
    main()
