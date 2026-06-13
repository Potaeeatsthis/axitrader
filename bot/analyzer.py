"""Claude-powered analysis. Uses Anthropic SDK async client."""
import os
import re

from anthropic import AsyncAnthropic

from .news import get_news_for_symbol
from .settings import get_model
from .stocks import fmt_summary, get_holdings, get_summary

_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    """Lazy singleton. Raises a clear error if the API key is missing."""
    global _client
    if _client is None:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it in Railway → Variables."
            )
        _client = AsyncAnthropic(api_key=key)
    return _client

SYSTEM = """You are a stock-analysis assistant for a personal investor based in Thailand.

Style:
- Concise, direct, no fluff. Markdown OK. Bullets where helpful.
- Bilingual: if the user writes in Thai, answer in Thai. Otherwise English.
- Numbers matter. Anchor claims in the data you're given.
- Use Thai stock context where relevant (SET index, .BK tickers).

What you DO:
- Summarize fundamentals, technicals, news, and analyst views from the provided data.
- Lay out the case FOR and the case AGAINST a position.
- Flag risks plainly. Note when data is missing, stale, or conflicting.
- Suggest things to *watch* (catalysts, levels) instead of issuing verdicts.

What you DO NOT do:
- Issue personalized "you should buy/sell" trade calls. Never tell the user to trade.
- Pretend to predict the future. Use hedged language: "could", "may", "signals suggest".
- Pad. If the answer is one paragraph, keep it one paragraph.

Always close with: _Not financial advice — your call._
"""

# Tokens that look like tickers but aren't
_STOPWORDS = {
    "AND", "OR", "THE", "BUY", "SELL", "HOLD", "ME", "MY", "TO", "FOR", "ON",
    "IN", "OF", "AT", "IS", "IT", "BE", "DO", "GO", "VS", "SHOULD", "WHAT",
    "HOW", "WHY", "WHEN", "WHERE", "OK", "ETF", "IPO", "PE", "EPS", "USD",
    "THB", "USA", "US", "EU", "UK", "AI", "ML", "API", "CEO", "CFO", "CTO",
    "Q1", "Q2", "Q3", "Q4", "YTD", "YOY", "QOQ", "ASAP", "FYI", "TLDR",
}

_TICKER_RE = re.compile(r"\b[A-Z]{2,6}(?:\.[A-Z]{2})?\b")


def _detect_tickers(text: str, max_n: int = 4) -> list[str]:
    candidates = _TICKER_RE.findall(text.upper())
    tickers = [c for c in candidates if c not in _STOPWORDS]
    return list(dict.fromkeys(tickers))[:max_n]


def _build_data_block(symbol: str) -> str:
    s = get_summary(symbol)
    news = get_news_for_symbol(symbol, limit=3)
    news_str = "\n".join(f"  - {n['title']} ({n['ago']})" for n in news) or "  (no recent news)"
    return f"**{symbol}**\n{fmt_summary(s)}\nNews:\n{news_str}"


async def analyze_stock(symbol: str) -> str:
    summary = get_summary(symbol)
    news = get_news_for_symbol(symbol, limit=5)
    news_block = "\n".join(
        f"- {n['title']} ({n['publisher']}, {n['ago']})" for n in news
    ) or "No recent news fetched."

    prompt = f"""Analyze this stock.

Data:
{fmt_summary(summary)}

Recent news:
{news_block}

Structure your response as:
1. *Snapshot* — 2-3 lines: what it is, current state.
2. *Bull case* — 2-3 bullets.
3. *Bear case* — 2-3 bullets.
4. *Technical read* — where price sits vs SMAs, RSI signal.
5. *What to watch* — catalysts, levels, upcoming events.
"""
    msg = await get_client().messages.create(
        model=get_model(),
        max_tokens=1500,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


async def chat_about_stocks(text: str) -> str:
    tickers = _detect_tickers(text)

    data_blocks: list[str] = []
    for t in tickers:
        try:
            data_blocks.append(_build_data_block(t))
        except Exception:
            # Probably not a real ticker — skip
            continue

    holdings = get_holdings()
    holdings_note = ""
    if holdings:
        relevant = {k: v for k, v in holdings.items() if k in tickers}
        if relevant:
            holdings_note = f"\n\nUser currently holds: {relevant}"
        else:
            holdings_note = f"\n\n(User's portfolio: {list(holdings.keys())} — none of the asked tickers are held.)"

    context_block = (
        "\n\n".join(data_blocks)
        if data_blocks
        else "(No specific tickers resolved — answer from general knowledge and note any uncertainty.)"
    )

    prompt = f"""User says: "{text}"
{holdings_note}

Relevant market data fetched just now:
{context_block}
"""
    msg = await get_client().messages.create(
        model=get_model(),
        max_tokens=1200,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text
