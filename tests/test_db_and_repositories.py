import pytest
from aiogram.types import User

from bot.db.migrate import migrate_db
from bot.db.sqlite import init_db
from bot.fetch.models import SearchItem
from bot.repository import UserRepository, UserStateRepository
import bot.db.database as legacy_db


@pytest.mark.asyncio
async def test_init_and_migrate_db(temp_db):
    await init_db(temp_db)
    await migrate_db()


@pytest.mark.asyncio
async def test_user_repository_crud(user_repo: UserRepository, sample_user: User):
    # Upsert new user
    await user_repo.upsert_user(sample_user)

    all_ids = await user_repo.get_all_user_ids()
    assert sample_user.id in all_ids
    assert await user_repo.count_all_users() == 1

    # Update user details
    updated_user = User(
        id=sample_user.id,
        is_bot=False,
        first_name="Иван Updated",
        last_name="Иванов",
        username="ivanov_new",
    )
    await user_repo.upsert_user(updated_user)
    assert await user_repo.count_all_users() == 1


@pytest.mark.asyncio
async def test_user_repository_favorite(user_repo: UserRepository, sample_user: User):
    await user_repo.upsert_user(sample_user)
    assert await user_repo.get_favorite(sample_user.id) is None
    assert await user_repo.count_users_with_favorite() == 0

    await user_repo.set_favorite(sample_user.id, "ИКБО-20-23")
    assert await user_repo.get_favorite(sample_user.id) == "ИКБО-20-23"
    assert await user_repo.count_users_with_favorite() == 1


@pytest.mark.asyncio
async def test_user_repository_notifications(user_repo: UserRepository, sample_user: User):
    await user_repo.upsert_user(sample_user)
    assert await user_repo.count_users_with_notifications() == 0

    item = SearchItem(type="teacher", uid=101, name="Карпов")
    await user_repo.set_notification(sample_user.id, "08:30", item)
    assert await user_repo.count_users_with_notifications() == 1

    # Check get_notification_users_by_time
    users_830 = await user_repo.get_notification_users_by_time("08:30")
    assert len(users_830) == 1
    assert users_830[0].id == sample_user.id
    assert users_830[0].notify_name == "Карпов"

    users_900 = await user_repo.get_notification_users_by_time("09:00")
    assert len(users_900) == 0

    # Check get_due_notification_users
    due_users = await user_repo.get_due_notification_users("08:35", "2025-09-01")
    assert len(due_users) == 1

    # Mark sent
    marked = await user_repo.mark_notification_sent(sample_user.id, "2025-09-01")
    assert marked is True

    # After mark sent, should not be due for same delivery_date
    due_after = await user_repo.get_due_notification_users("08:35", "2025-09-01")
    assert len(due_after) == 0

    # But due for next day
    due_next_day = await user_repo.get_due_notification_users("08:35", "2025-09-02")
    assert len(due_next_day) == 1

    # Disable notification
    await user_repo.disable_notification(sample_user.id)
    assert await user_repo.count_users_with_notifications() == 0


@pytest.mark.asyncio
async def test_user_repository_delete_user(user_repo: UserRepository, sample_user: User):
    await user_repo.upsert_user(sample_user)
    assert await user_repo.count_all_users() == 1

    await user_repo.delete_user(sample_user.id)
    assert await user_repo.count_all_users() == 0
    assert await user_repo.get_all_user_ids() == []


@pytest.mark.asyncio
async def test_user_state_repository(user_state_repo: UserStateRepository):
    # None when empty
    state = await user_state_repo.load_payload(99999)
    assert state is None

    # Save and load
    await user_state_repo.save_payload(99999, '{"step": 1}')
    loaded = await user_state_repo.load_payload(99999)
    assert loaded == '{"step": 1}'

    # Update payload
    await user_state_repo.save_payload(99999, '{"step": 2}')
    updated = await user_state_repo.load_payload(99999)
    assert updated == '{"step": 2}'


@pytest.mark.asyncio
async def test_legacy_database_module(sample_user: User):
    # Test that legacy functions in bot/db/database.py work without error
    await legacy_db.insert_new_user(sample_user)
    await legacy_db.add_favorite(sample_user.id, "ИКБО-01-21")
    fav = await legacy_db.get_user_favorites(sample_user.id)
    assert fav == "ИКБО-01-21"

    item = SearchItem(type="teacher", uid=55, name="Петров")
    await legacy_db.set_notification(sample_user.id, "09:15", item)
    notify_users = await legacy_db.get_notification_users_by_time("09:15")
    assert len(notify_users) == 1

    ids = await legacy_db.get_all_user_ids()
    assert sample_user.id in ids

    await legacy_db.disable_notification(sample_user.id)
    await legacy_db.delete_user(sample_user.id)
    ids_after = await legacy_db.get_all_user_ids()
    assert sample_user.id not in ids_after


@pytest.mark.asyncio
async def test_user_repository_item_requests(user_repo: UserRepository):
    # Empty initially
    assert await user_repo.get_top_requested_items("teacher") == []

    # Record 2 requests for T1, 1 for T2, 3 for T3
    await user_repo.record_item_request("teacher", 1, "T1")
    await user_repo.record_item_request("teacher", 1, "T1")
    await user_repo.record_item_request("teacher", 2, "T2")
    await user_repo.record_item_request("teacher", 3, "T3")
    await user_repo.record_item_request("teacher", 3, "T3")
    await user_repo.record_item_request("teacher", 3, "T3")

    top = await user_repo.get_top_requested_items("teacher", limit=2)
    assert len(top) == 2
    assert top[0] == ("T3", 3)
    assert top[1] == ("T1", 2)

