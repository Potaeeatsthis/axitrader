"""Telegram stock-AI bot entrypoint."""
import logging
import os
import sys

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.handlers import (
    add_cmd,
    analyze_cmd,
    brief_cmd,
    chat_handler,
    holdings_cmd,
    model_cmd,
    news_cmd,
    remove_cmd,
    start,
    whoami_cmd,
)
from bot.scheduler import setup_morning_brief

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


REQUIRED_ENV = ["TELEGRAM_BOT_TOKEN", "ANTHROPIC_API_KEY"]


def _check_env() -> None:
    missing = [v for v in REQUIRED_ENV if not os.environ.get(v)]
    if missing:
        logger.error(
            "Missing required environment variable(s): %s. "
            "Set them in Railway → Variables, then redeploy.",
            ", ".join(missing),
        )
        sys.exit(1)


def main() -> None:
    _check_env()
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(CommandHandler("whoami", whoami_cmd))
    app.add_handler(CommandHandler("model", model_cmd))
    app.add_handler(CommandHandler("holdings", holdings_cmd))
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CommandHandler("remove", remove_cmd))
    app.add_handler(CommandHandler("analyze", analyze_cmd))
    app.add_handler(CommandHandler("news", news_cmd))
    app.add_handler(CommandHandler("brief", brief_cmd))

    # Free-form chat
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))

    # Scheduled morning brief
    setup_morning_brief(app)

    logger.info("Bot starting...")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
