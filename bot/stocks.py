"""Stock data + holdings persistence. yfinance handles SET (.BK), US, HK, etc."""
import json
import os
from pathlib import Path
from typing import Any

import yfinance as yf

HOLDINGS_FILE = Path(os.environ.get("HOLDINGS_FILE", "/data/holdings.json"))


def normalize_symbol(s: str) -> str:
    return s.strip().upper()


# ─── Holdings storage ────────────────────────────────────────────────────────

def get_holdings() -> dict[str, float]:
    if not HOLDINGS_FILE.exists():
        return {}
    try:
        return json.loads(HOLDINGS_FILE.read_text())
    except Exception:
        return {}


def save_holdings(holdings: dict[str, float]) -> None:
    HOLDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    HOLDINGS_FILE.write_text(json.dumps(holdings, indent=2))


# ─── Market data ─────────────────────────────────────────────────────────────

def get_quote(symbol: str) -> dict[str, Any]:
    """Live price + day change. Fast — uses fast_info."""
    t = yf.Ticker(symbol)
    fi = t.fast_info
    price = float(fi["last_price"])
    prev = float(fi["previous_close"])
    change_pct = (price - prev) / prev * 100 if prev else 0.0
    return {
        "symbol": symbol,
        "price": price,
        "previous_close": prev,
        "change_pct": change_pct,
        "currency": getattr(fi, "currency", "USD"),
    }


def _rsi(closes, period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    delta = closes.diff().dropna()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    if loss.iloc[-1] == 0:
        return 100.0
    rs = gain.iloc[-1] / loss.iloc[-1]
    return round(100 - 100 / (1 + rs), 1)


def get_summary(symbol: str) -> dict[str, Any]:
    """Compact summary for Claude to reason over. Skips None values when formatted."""
    t = yf.Ticker(symbol)
    info: dict = {}
    try:
        info = t.info or {}
    except Exception:
        pass

    quote = get_quote(symbol)
    hist = t.history(period="3mo")

    out: dict[str, Any] = {
        "symbol": symbol,
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": quote["currency"],
        "price": round(quote["price"], 2),
        "change_pct_today": round(quote["change_pct"], 2),
        "market_cap": info.get("marketCap"),
        "pe_trailing": info.get("trailingPE"),
        "pe_forward": info.get("forwardPE"),
        "dividend_yield_pct": (info.get("dividendYield") or 0) * 100 or None,
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "analyst_recommendation": info.get("recommendationKey"),
        "analyst_target_mean": info.get("targetMeanPrice"),
    }

    if len(hist) > 0:
        closes = hist["Close"]
        out["return_3mo_pct"] = round((closes.iloc[-1] / closes.iloc[0] - 1) * 100, 2)
        if len(closes) >= 20:
            out["sma_20"] = round(float(closes.tail(20).mean()), 2)
        if len(closes) >= 50:
            out["sma_50"] = round(float(closes.tail(50).mean()), 2)
        rsi = _rsi(closes)
        if rsi is not None:
            out["rsi_14"] = rsi

    return out


def fmt_summary(s: dict[str, Any]) -> str:
    """Format a summary dict as indented text for prompt context."""
    lines = []
    for k, v in s.items():
        if v is None or v == "":
            continue
        if isinstance(v, float):
            lines.append(f"  {k}: {v:,.2f}")
        elif isinstance(v, int) and v > 1_000_000:
            lines.append(f"  {k}: {v:,}")
        else:
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)
