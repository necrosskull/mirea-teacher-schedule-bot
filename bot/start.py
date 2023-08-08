import bot.config as config
import logging
from telegram.ext import Application

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)


def main() -> None:
    """Start the bot."""
    from bot import setup

    application = Application.builder().token(config.TELEGRAM_TOKEN).build()

    setup.setup(application)

    application.run_polling()
