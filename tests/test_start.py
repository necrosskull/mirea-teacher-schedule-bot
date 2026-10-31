from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.config import settings
from bot.start import main, run


@pytest.mark.asyncio
async def test_run_bot(monkeypatch, temp_db):
    monkeypatch.setattr(settings, "token", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    monkeypatch.setattr(settings, "supabase_url", "https://supabase.example.com")
    monkeypatch.setattr(settings, "supabase_key", "sb_publishable_test")

    with (
        patch("bot.setup.setup", AsyncMock()),
        patch("dishka.integrations.aiogram.setup_dishka", MagicMock()),
        patch("aiogram.Dispatcher.start_polling", AsyncMock()) as mock_polling,
        patch("bot.handlers.notification.notification_worker", AsyncMock()) as mock_worker,
        patch("uvicorn.Server.serve", AsyncMock()) as mock_serve,
    ):
        await run()
        mock_polling.assert_called_once()
        mock_serve.assert_called_once()


@pytest.mark.asyncio
async def test_run_requires_schedule_backend(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_key", "")

    with pytest.raises(RuntimeError, match="SUPABASE_URL"):
        await run()


def test_main_bot(monkeypatch):
    with patch("bot.start.run", AsyncMock()) as mock_run:
        main()
        mock_run.assert_called_once()
