"""News headlines via yfinance. Handles both old and new yf news schemas."""
from datetime import datetime, timezone

import yfinance as yf


def _ago(ts: int) -> str:
    if not ts:
        return ""
    delta = datetime.now(timezone.utc) - datetime.fromtimestamp(ts, tz=timezone.utc)
    total = delta.total_seconds()
    if total < 3600:
        return f"{int(total // 60)}m ago"
    if total < 86400:
        return f"{int(total // 3600)}h ago"
    return f"{int(total // 86400)}d ago"


def _parse_ts(value) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
        except Exception:
            return 0
    return 0


def get_news_for_symbol(symbol: str, limit: int = 5) -> list[dict]:
    try:
        raw = yf.Ticker(symbol).news or []
    except Exception:
        return []

    out: list[dict] = []
    for item in raw[:limit]:
        # yfinance ≥ 0.2.40 nests content; older versions flat
        content = item.get("content", item)
        title = content.get("title", "")
        link = (content.get("canonicalUrl") or {}).get("url") or content.get("link", "")
        provider = (content.get("provider") or {}).get("displayName") or item.get("publisher", "")
        ts = _parse_ts(content.get("pubDate") or item.get("providerPublishTime"))

        if title and link:
            out.append({
                "title": title,
                "link": link,
                "publisher": provider,
                "ts": ts,
                "ago": _ago(ts),
            })
    return out


def get_news_bundle(symbols: list[str], per_symbol: int = 3) -> dict[str, list[dict]]:
    return {s: get_news_for_symbol(s, per_symbol) for s in symbols}
