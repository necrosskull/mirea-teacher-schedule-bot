import bot.config as config
import logging
from telegram.ext import Updater

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)


def main() -> None:
    """Start the bot."""
    from bot import setup

    updater = Updater(config.TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    setup.setup(dispatcher)
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
