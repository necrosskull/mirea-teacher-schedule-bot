import logging

from telegram.ext import Application

from bot.config import settings

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> None:
    """Start the bot."""
    from bot import setup

    application = (
        Application.builder()
        .token(settings.token)
        .post_init(post_init=post_init)
        .build()
    )

    setup.setup(application)

    application.run_polling()


async def post_init(application: Application) -> None:
    application.bot_data["maintenance_mode"] = False
