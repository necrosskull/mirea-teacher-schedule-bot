import logging

from telegram.ext import Application

import bot.config as config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> None:
    """Start the bot."""
    from bot import setup

    application = (
        Application.builder()
        .token(config.TELEGRAM_TOKEN)
        .post_init(post_init=post_init)
        .build()
    )

    setup.setup(application)

    application.run_polling()


async def post_init(application: Application) -> None:
    application.bot_data["maintenance_mode"] = False
