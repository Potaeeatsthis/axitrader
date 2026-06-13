"""Telegram command + message handlers."""
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .analyzer import analyze_stock, chat_about_stocks
from .news import get_news_for_symbol
from .scheduler import build_morning_brief
from .settings import MODEL_ALIASES, get_model, set_model
from .stocks import (
    get_holdings,
    get_quote,
    normalize_symbol,
    save_holdings,
)

logger = logging.getLogger(__name__)


WELCOME = """👋 *Stock AI Bot*

I track your stocks, summarize news, and help you think through buy/sell calls.

*Commands*
/holdings — show your portfolio
/add SYMBOL SHARES — add a holding (e.g. `/add PTT.BK 1000`)
/remove SYMBOL — remove a holding
/analyze SYMBOL — analysis on any stock (e.g. `/analyze AAPL`)
/news SYMBOL — recent headlines
/brief — get today's morning brief now
/model — show or switch the Claude model
/whoami — show your chat ID (for setup)

Or just *chat* — try:
• "should I buy more AAPL?"
• "PTTEP เป็นยังไงบ้างวันนี้"
• "compare DELTA vs ADVANC"

_I provide analysis, not personalized advice. Final calls are yours._
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME, parse_mode=ParseMode.MARKDOWN)


async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show or switch the active Claude model."""
    if not context.args:
        current = get_model()
        lines = [
            "🧠 *Active model*",
            f"`{current}`",
            "",
            "*Switch with* `/model <name>`",
            "",
            "*Aliases*",
        ]
        tier_notes = {
            "opus":   "deepest analysis, slowest, most expensive",
            "sonnet": "balanced — recommended default",
            "haiku":  "fastest + cheapest, lighter analysis",
        }
        for alias, full in MODEL_ALIASES.items():
            note = tier_notes.get(alias, "")
            marker = "→" if full == current else " "
            lines.append(f"{marker} `{alias}` → `{full}`  _({note})_")
        lines.append("")
        lines.append("Tip: `/model haiku` for cheap briefs, `/model opus` for deeper takes.")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
        return

    name = context.args[0]
    try:
        resolved = set_model(name)
        await update.message.reply_text(
            f"✅ Switched to `{resolved}`", parse_mode=ParseMode.MARKDOWN
        )
    except ValueError:
        valid = ", ".join(f"`{a}`" for a in MODEL_ALIASES)
        await update.message.reply_text(
            f"❌ Unknown model `{name}`.\nTry one of: {valid}",
            parse_mode=ParseMode.MARKDOWN,
        )


async def whoami_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"Your chat ID: `{chat_id}`\n\n"
        f"Set `OWNER_CHAT_ID={chat_id}` in Railway env vars to enable the daily brief.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def holdings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    holdings = get_holdings()
    if not holdings:
        await update.message.reply_text(
            "No holdings yet. Add some with `/add SYMBOL SHARES`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = ["📊 *Your Holdings*\n"]
    total_value = 0.0
    for sym, shares in holdings.items():
        try:
            q = get_quote(sym)
            value = q["price"] * shares
            total_value += value
            arrow = "🟢" if q["change_pct"] >= 0 else "🔴"
            lines.append(
                f"{arrow} `{sym}` — {shares:g} @ {q['price']:.2f} "
                f"({q['change_pct']:+.2f}%) → {value:,.0f}"
            )
        except Exception as e:
            lines.append(f"⚠️ `{sym}` — fetch error ({e})")

    lines.append(f"\n*Total: {total_value:,.0f}*")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/add SYMBOL SHARES`\nExample: `/add PTT.BK 1000`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    symbol = normalize_symbol(context.args[0])
    try:
        shares = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Shares must be a number.")
        return

    holdings = get_holdings()
    holdings[symbol] = shares
    save_holdings(holdings)

    try:
        q = get_quote(symbol)
        await update.message.reply_text(
            f"✅ Added `{symbol}` × {shares:g} (current: {q['price']:.2f} {q['currency']})",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        await update.message.reply_text(
            f"✅ Added `{symbol}` × {shares:g}\n"
            f"⚠️ Couldn't fetch a price — double-check the symbol "
            f"(Thai stocks need `.BK`, e.g. `PTT.BK`).",
            parse_mode=ParseMode.MARKDOWN,
        )


async def remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: `/remove SYMBOL`", parse_mode=ParseMode.MARKDOWN)
        return

    symbol = normalize_symbol(context.args[0])
    holdings = get_holdings()
    if symbol in holdings:
        del holdings[symbol]
        save_holdings(holdings)
        await update.message.reply_text(f"🗑 Removed `{symbol}`", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(
            f"`{symbol}` not in holdings.", parse_mode=ParseMode.MARKDOWN
        )


async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "Usage: `/analyze SYMBOL`\nExample: `/analyze AAPL`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    symbol = normalize_symbol(context.args[0])
    await update.message.chat.send_action("typing")
    msg = await update.message.reply_text(f"🔍 Analyzing `{symbol}`...", parse_mode=ParseMode.MARKDOWN)

    try:
        analysis = await analyze_stock(symbol)
        await msg.edit_text(analysis, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception as e:
        logger.exception("analyze failed")
        await msg.edit_text(f"❌ Couldn't analyze {symbol}: {e}")


async def news_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: `/news SYMBOL`", parse_mode=ParseMode.MARKDOWN)
        return

    symbol = normalize_symbol(context.args[0])
    items = get_news_for_symbol(symbol, limit=5)
    if not items:
        await update.message.reply_text(f"No recent news for {symbol}.")
        return

    lines = [f"📰 *News — {symbol}*\n"]
    for n in items:
        # Escape Markdown special chars in title minimally
        title = n["title"].replace("[", "(").replace("]", ")")
        lines.append(f"• [{title}]({n['link']})\n  _{n['publisher']} · {n['ago']}_")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


async def brief_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.chat.send_action("typing")
    msg = await update.message.reply_text("📋 Building morning brief...")
    try:
        brief = await build_morning_brief()
        await msg.edit_text(brief, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    except Exception as e:
        logger.exception("brief failed")
        await msg.edit_text(f"❌ Brief failed: {e}")


async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    await update.message.chat.send_action("typing")
    try:
        reply = await chat_about_stocks(text)
        await update.message.reply_text(
            reply, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
        )
    except Exception as e:
        logger.exception("chat failed")
        await update.message.reply_text(f"❌ Error: {e}")
