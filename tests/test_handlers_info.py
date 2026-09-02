from unittest.mock import AsyncMock

import pytest
from aiogram.types import Message

from bot.handlers.info import about, start


@pytest.mark.asyncio
async def test_start_handler():
    msg = AsyncMock(spec=Message)
    msg.answer = AsyncMock()

    await start(msg)
    msg.answer.assert_called_once()
    called_text = msg.answer.call_args[1]["text"]
    assert "MIREA Teacher Schedule Bot" or "Привет!" in called_text
    assert "/notify" in called_text
    assert "/save" in called_text


@pytest.mark.asyncio
async def test_about_handler():
    msg = AsyncMock(spec=Message)
    msg.answer = AsyncMock()

    await about(msg)
    msg.answer.assert_called_once()
    called_text = msg.answer.call_args[1]["text"]
    assert "necrosskull" in called_text
    assert "github.com" in called_text


@pytest.mark.asyncio
async def test_open_app_handler():
    from bot.config import settings
    from bot.handlers.info import open_app

    settings.webapp_url = "https://example.com/app"

    msg = AsyncMock(spec=Message)
    msg.answer = AsyncMock()

    await open_app(msg)
    msg.answer.assert_called_once()
    kwargs = msg.answer.call_args[1]
    assert "Mini App" in kwargs["text"]
    assert kwargs["reply_markup"] is not None

