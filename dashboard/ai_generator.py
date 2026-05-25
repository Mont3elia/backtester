import anthropic
import streamlit as st

SYSTEM_PROMPT = """Sei un esperto di trading algoritmico. Generi strategie Python per un backtester.

INTERFACCIA BaseStrategy (OBBLIGATORIA):
```python
from strategies.base_strategy import BaseStrategy

class NomeStrategia(BaseStrategy):
    name = "Nome Visualizzato"
    description = "Descrizione breve"
    param_schema = {
        "param": {"type": "int"|"float"|"bool", "default": val, "min": val, "max": val, "label": "..."}
    }

    def on_bar(self, bar, portfolio):
        # bar: pd.Series con open, high, low, close, volume
        # self.prices: lista dei close visti finora (si aggiorna automaticamente)
        # self.symbol: simbolo tradato
        # self.NomeParam: parametri da param_schema accessibili direttamente
        # portfolio.positions: dict {symbol: Position}
        # portfolio.cash: liquidità

        self.buy(1)        # compra 1 unità
        self.sell(1)       # vendi 1 unità
        self.close_position()  # chiudi posizione corrente
```

INDICATORI DISPONIBILI (già importabili):
```python
from indicators.trend import sma, ema, wma, macd, adx
from indicators.oscillators import rsi, stochastic, cci, williams_r
from indicators.volatility import bollinger_bands, atr, historical_volatility
# Tutte accettano pd.Series, restituiscono pd.Series
# sma(series, period), ema(series, period)
# rsi(series, period=14)
# macd(series, fast=12, slow=26, signal=9) -> (macd_line, signal_line, histogram)
# bollinger_bands(series, period=20, std_dev=2) -> (upper, middle, lower)
# atr(high, low, close, period=14)
```

REGOLE IMPORTANTI:
- Usa self.prices per i calcoli (è una lista Python, converti con pd.Series(self.prices) per gli indicatori)
- Controlla sempre len(self.prices) >= periodo_minimo prima di calcolare
- Per verificare se sei in posizione: portfolio.positions.get(self.symbol)
- Non usare mai dati futuri (no look-ahead bias)
- Genera SOLO il codice Python, niente spiegazioni, niente markdown, niente ```python
- Il codice deve essere completo e immediatamente eseguibile"""


def get_api_key() -> str | None:
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return None


def _strip_markdown(code: str) -> str:
    """Rimuove eventuali blocchi markdown se Claude li aggiunge."""
    code = code.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        # Rimuovi la prima riga (```python o ```) e l'ultima (```)
        start = 1
        end = len(lines)
        if lines[-1].strip() == "```":
            end = len(lines) - 1
        code = "\n".join(lines[start:end])
    return code.strip()


def generate_strategy_from_description(description: str) -> str:
    """Genera codice strategia da descrizione libera in italiano."""
    api_key = get_api_key()
    if not api_key:
        raise ValueError(
            "API key Anthropic non configurata. Vai nelle impostazioni dell'app su "
            "Streamlit Cloud → Secrets e aggiungi ANTHROPIC_API_KEY."
        )

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""L'utente vuole questa strategia di trading:

{description}

Genera il codice Python completo della strategia seguendo esattamente l'interfaccia BaseStrategy descritta."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    return _strip_markdown(message.content[0].text)


def generate_strategy_from_wizard(answers: dict) -> str:
    """Genera codice strategia dalle risposte del wizard."""
    api_key = get_api_key()
    if not api_key:
        raise ValueError(
            "API key Anthropic non configurata. Vai nelle impostazioni dell'app su "
            "Streamlit Cloud → Secrets e aggiungi ANTHROPIC_API_KEY."
        )

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""L'utente ha risposto a un wizard per creare una strategia. Ecco le risposte:

Nome strategia: {answers.get('name', 'Mia Strategia')}
Indicatore principale: {answers.get('indicator', 'SMA')}
Condizione di ACQUISTO: {answers.get('entry', '')}
Condizione di VENDITA: {answers.get('exit', '')}
Stop loss: {answers.get('stop_loss', 'No')}
Note aggiuntive: {answers.get('notes', 'Nessuna')}

Genera il codice Python completo della strategia."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    return _strip_markdown(message.content[0].text)
