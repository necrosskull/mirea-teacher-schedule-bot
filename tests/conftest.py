import os
import tempfile
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Chat, Message, User

from bot.config import settings
from bot.db.sqlite import init_db
from bot.fetch.models import (
    Campus,
    Classroom,
    LessonBells,
    LessonSchedule,
    ScheduleData,
    SearchItem,
    Teacher,
)
from bot.repository import UserRepository, UserStateRepository
from bot.service import NotificationService, ScheduleService, StateService, UserService


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    """Create an isolated temporary SQLite database for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    monkeypatch.setattr(settings, "db_path", db_path)

    import bot.db.sqlite as sqlite_mod
    import bot.db.database as db_mod
    import bot.db.migrate as migrate_mod

    monkeypatch.setattr(sqlite_mod, "DB_PATH", db_path)
    monkeypatch.setattr(sqlite_mod, "get_db_path", lambda: db_path)
    if hasattr(db_mod, "DB_PATH"):
        monkeypatch.setattr(db_mod, "DB_PATH", db_path)
    if hasattr(migrate_mod, "DB_PATH"):
        monkeypatch.setattr(migrate_mod, "DB_PATH", db_path)

    import asyncio
    asyncio.run(init_db(db_path))

    yield db_path

    try:
        os.remove(db_path)
    except OSError:
        pass


@pytest.fixture
def user_repo():
    return UserRepository()


@pytest.fixture
def user_state_repo():
    return UserStateRepository()


@pytest.fixture
def user_service(user_repo):
    return UserService(user_repo)


@pytest.fixture
def notification_service(user_repo):
    return NotificationService(user_repo)


@pytest.fixture
def state_service(user_state_repo):
    return StateService(user_state_repo)


@pytest.fixture
def mock_api_client():
    client = MagicMock()
    client.search = AsyncMock()
    client.get_schedule = AsyncMock()
    return client


@pytest.fixture
def schedule_service(mock_api_client):
    return ScheduleService(mock_api_client)


@pytest.fixture
def sample_user():
    return User(
        id=12345,
        is_bot=False,
        first_name="Иван",
        last_name="Иванов",
        username="ivanov",
    )


@pytest.fixture
def sample_search_item():
    return SearchItem(type="teacher", uid=101, name="Карпов Д.А.")


@pytest.fixture
def sample_group_item():
    return SearchItem(type="group", uid=202, name="ИКБО-20-23")


@pytest.fixture
def sample_schedule():
    lesson = LessonSchedule(
        classrooms=[
            Classroom(
                name="А-101",
                campus=Campus(name="Вернадского 78", short_name="В-78"),
            )
        ],
        dates=["01-09-2025", "08-09-2025"],
        groups=["ИКБО-20-23"],
        lesson_bells=LessonBells(number=1, start_time="09:00", end_time="10:30"),
        lesson_type="lecture",
        subject="Математический анализ",
        teachers=[Teacher(name="Карпов Д.А.")],
        type="lesson",
    )
    return ScheduleData(data=[lesson])


@pytest.fixture
def mock_bot():
    bot = AsyncMock(spec=Bot)
    bot.send_message = AsyncMock()
    bot.edit_message_text = AsyncMock()
    return bot


@pytest.fixture
def mock_fsm_context():
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=12345, user_id=12345)
    return FSMContext(storage=storage, key=key)


def unwrap(handler):
    """Retrieve the original function unwrapped from Dishka's @inject."""
    return getattr(handler, "__dishka_orig_func__", handler)

