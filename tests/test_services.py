from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import User

from bot.fetch.models import (
    LessonBells,
    LessonSchedule,
    ScheduleData,
    SearchItem,
)
from bot.fetch.schedule import get_lessons as fetch_get_lessons
from bot.service import NotificationService, ScheduleService, StateService, UserService


@pytest.mark.asyncio
async def test_user_service_crud_and_counts(user_service: UserService, sample_user: User):
    await user_service.ensure_user(sample_user)
    assert await user_service.count_all_users() == 1
    assert await user_service.get_all_user_ids() == [sample_user.id]

    # Favorite
    await user_service.set_favorite(sample_user.id, "ИКБО-20-23")
    assert await user_service.get_favorite(sample_user.id) == "ИКБО-20-23"
    assert await user_service.count_users_with_favorite() == 1

    # Notifications count initially 0
    assert await user_service.count_users_with_notifications() == 0

    # Request stats
    await user_service.record_item_request("group", 1, "ИКБО-20-23")
    top_groups = await user_service.get_top_requested_items("group")
    assert len(top_groups) == 1
    assert top_groups[0] == ("ИКБО-20-23", 1)

    # Delete
    await user_service.delete_user(sample_user.id)
    assert await user_service.count_all_users() == 0



@pytest.mark.asyncio
async def test_user_service_exception_handling():
    broken_repo = MagicMock()
    broken_repo.upsert_user = AsyncMock(side_effect=Exception("DB boom"))
    broken_repo.set_favorite = AsyncMock(side_effect=Exception("DB boom"))
    broken_repo.get_favorite = AsyncMock(side_effect=Exception("DB boom"))
    broken_repo.get_all_user_ids = AsyncMock(side_effect=Exception("DB boom"))
    broken_repo.count_all_users = AsyncMock(side_effect=Exception("DB boom"))
    broken_repo.count_users_with_favorite = AsyncMock(side_effect=Exception("DB boom"))
    broken_repo.count_users_with_notifications = AsyncMock(side_effect=Exception("DB boom"))
    broken_repo.delete_user = AsyncMock(side_effect=Exception("DB boom"))

    svc = UserService(broken_repo)
    user = User(id=1, is_bot=False, first_name="Test")

    # None of these should raise uncaught exceptions
    await svc.ensure_user(user)
    await svc.set_favorite(1, "fav")
    assert await svc.get_favorite(1) is None
    assert await svc.get_all_user_ids() == []
    assert await svc.count_all_users() == 0
    assert await svc.count_users_with_favorite() == 0
    assert await svc.count_users_with_notifications() == 0
    await svc.delete_user(1)


@pytest.mark.asyncio
async def test_notification_service_flow(
    notification_service: NotificationService,
    user_repo,
    sample_user: User,
):
    await user_repo.upsert_user(sample_user)
    item = SearchItem(type="teacher", uid=100, name="Преподаватель")

    await notification_service.set_notification(sample_user.id, "08:00", item)
    due = await notification_service.get_due_notification_users("08:10", "2025-09-01")
    assert len(due) == 1
    assert due[0].id == sample_user.id

    marked = await notification_service.mark_notification_sent(sample_user.id, "2025-09-01")
    assert marked is True

    await notification_service.disable_notification(sample_user.id)
    due_after_disable = await notification_service.get_due_notification_users("08:10", "2025-09-01")
    assert len(due_after_disable) == 0


@pytest.mark.asyncio
async def test_notification_service_exceptions():
    broken_repo = MagicMock()
    broken_repo.set_notification = AsyncMock(side_effect=Exception("DB error"))
    broken_repo.disable_notification = AsyncMock(side_effect=Exception("DB error"))
    broken_repo.get_due_notification_users = AsyncMock(side_effect=Exception("DB error"))
    broken_repo.mark_notification_sent = AsyncMock(side_effect=Exception("DB error"))

    svc = NotificationService(broken_repo)
    item = SearchItem(type="group", uid=1, name="G")

    await svc.set_notification(1, "08:00", item)
    await svc.disable_notification(1)
    assert await svc.get_due_notification_users("08:00", "2025-09-01") == []
    assert await svc.mark_notification_sent(1, "2025-09-01") is False


@pytest.mark.asyncio
async def test_state_service_flow(state_service: StateService):
    await state_service.save_payload(1, '{"foo": "bar"}')
    res = await state_service.load_payload(1)
    assert res == '{"foo": "bar"}'


@pytest.mark.asyncio
async def test_schedule_service_search_and_get(mock_api_client, user_repo):
    schedule_service = ScheduleService(mock_api_client, user_repo=user_repo)
    mock_api_client.search.return_value = [SearchItem(type="teacher", uid=1, name="T")]
    res = await schedule_service.search("query")
    assert len(res) == 1

    item = SearchItem(type="teacher", uid=1, name="T")
    mock_api_client.get_schedule.return_value = ScheduleData(data=[])
    sched = await schedule_service.get_schedule(item)
    assert sched.data == []

    # Verify request was recorded
    top = await user_repo.get_top_requested_items("teacher")
    assert len(top) == 1
    assert top[0] == ("T", 1)



def test_schedule_service_get_lessons_sorting_and_filtering():
    l1 = LessonSchedule(
        dates=["01-09-2025"],
        lesson_bells=LessonBells(number=2, start_time="10:40", end_time="12:10"),
        subject="Вторая пара",
    )
    l2 = LessonSchedule(
        dates=["01-09-2025", "02-09-2025"],
        lesson_bells=LessonBells(number=1, start_time="09:00", end_time="10:30"),
        subject="Первая пара",
    )
    schedule = ScheduleData(data=[l1, l2])

    svc = ScheduleService(MagicMock())

    # All lessons without date filter: 3 instances, sorted by (date, number)
    all_lessons = svc.get_lessons(schedule)
    assert len(all_lessons) == 3
    assert all_lessons[0].subject == "Первая пара"
    assert all_lessons[0].dates == date(2025, 9, 1)
    assert all_lessons[1].subject == "Вторая пара"
    assert all_lessons[1].dates == date(2025, 9, 1)
    assert all_lessons[2].subject == "Первая пара"
    assert all_lessons[2].dates == date(2025, 9, 2)

    # Filtered by date: only 2025-09-02
    filtered = svc.get_lessons(schedule, dates=[date(2025, 9, 2)])
    assert len(filtered) == 1
    assert filtered[0].dates == date(2025, 9, 2)

    # Check fetch_get_lessons produces identical results
    fetch_res = fetch_get_lessons(schedule, dates=[date(2025, 9, 2)])
    assert len(fetch_res) == 1

    # Check dates_summary
    summary = svc.get_dates_summary(schedule)
    assert "2025-09-01" in summary
    assert "2025-09-02" in summary
    assert len(summary["2025-09-01"]) == 2

    assert fetch_res[0].subject == "Первая пара"
