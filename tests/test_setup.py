import pytest
from aiogram import Dispatcher

from bot.handlers.context import bot_data
from bot.setup import setup


@pytest.mark.asyncio
async def test_setup_dispatcher(temp_db):
    dp = Dispatcher()
    await setup(dp)
    assert bot_data["maintenance_mode"] is False
    assert bot_data["maintenance_message"] is None
    # Verify sub-routers are attached
    assert len(dp.sub_routers) >= 5
