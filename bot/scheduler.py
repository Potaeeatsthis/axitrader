"""Daily morning brief — sent to OWNER_CHAT_ID at configured time."""
import logging
import os
from datetime import time
from zoneinfo import ZoneInfo

from telegram.ext import Application, ContextTypes

from .analyzer import SYSTEM, extract_text, get_client_for
from .news import get_news_bundle
from .settings import get_model
from .stocks import fmt_summary, get_holdings, get_summary

logger = logging.getLogger(__name__)

BRIEF_TIMEZONE = ZoneInfo(os.environ.get("BRIEF_TIMEZONE", "Asia/Bangkok"))
BRIEF_HOUR = int(os.environ.get("BRIEF_HOUR", "8"))
BRIEF_MINUTE = int(os.environ.get("BRIEF_MINUTE", "0"))
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", "0") or "0")


async def build_morning_brief() -> str:
    holdings = get_holdings()
    if not holdings:
        return "📋 *Morning Brief*\n\nNo holdings tracked yet. Use `/add SYMBOL SHARES` to start."

    summaries = {}
    for sym in holdings:
        try:
            summaries[sym] = get_summary(sym)
        except Exception as e:
            logger.warning("summary failed for %s: %s", sym, e)

    news = get_news_bundle(list(holdings.keys()), per_symbol=3)

    blocks = []
    for sym, s in summaries.items():
        shares = holdings.get(sym, 0)
        news_lines = "\n".join(
            f"  - {n['title']} ({n['ago']})" for n in news.get(sym, [])
        ) or "  (no recent news)"
        blocks.append(
            f"**{sym}** (holding: {shares} shares)\n{fmt_summary(s)}\nNews:\n{news_lines}"
        )

    context_block = "\n\n".join(blocks)

    prompt = f"""Build a morning brief for the user's portfolio.

{context_block}

Format:
📋 *Morning Brief — [today's date]*

For each holding (2-4 lines each):
- Current state: price, day change, position vs 52w range.
- One news item *if material*, else a technical note (RSI extreme, near SMA crossover, near 52w high/low).
- "Watch:" line — what could move it.

End with one *Portfolio note* (1-2 lines): concentration, sector tilt, anything that stands out.

No buy/sell verdicts. Scannable on mobile. Close with the standard disclaimer.
"""
    model = get_model()
    msg = await get_client_for(model).messages.create(
        model=model,
        max_tokens=2000,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return extract_text(msg)


async def _send_brief(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not OWNER_CHAT_ID:
        logger.warning("OWNER_CHAT_ID not set — skipping scheduled brief")
        return
    try:
        brief = await build_morning_brief()
        await context.bot.send_message(
            chat_id=OWNER_CHAT_ID,
            text=brief,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.exception("scheduled brief failed")
        try:
            await context.bot.send_message(
                chat_id=OWNER_CHAT_ID, text=f"⚠️ Morning brief failed: {e}"
            )
        except Exception:
            pass


def setup_morning_brief(app: Application) -> None:
    if not OWNER_CHAT_ID:
        logger.warning("OWNER_CHAT_ID not set — morning brief disabled")
        return

    app.job_queue.run_daily(
        _send_brief,
        time=time(BRIEF_HOUR, BRIEF_MINUTE, tzinfo=BRIEF_TIMEZONE),
        name="morning_brief",
    )
    logger.info(
        "Morning brief scheduled at %02d:%02d %s",
        BRIEF_HOUR, BRIEF_MINUTE, BRIEF_TIMEZONE,
    )
