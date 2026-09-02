import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.fetch.models import (
    LessonBells,
    LessonSchedule,
    ScheduleData,
    SearchItem,
)
from bot.repository.schedule_cache_repository import ScheduleCacheRepository
from bot.service.schedule_service import ScheduleService


@pytest.fixture
def cache_repo():
    return ScheduleCacheRepository()


@pytest.mark.asyncio
async def test_cache_repository_crud_and_expiration(cache_repo: ScheduleCacheRepository):
    key = "test:schedule:1"
    payload = '{"data": [{"subject": "Физика"}]}'

    # 1. Non-existent key
    res = await cache_repo.get_payload(key)
    assert res is None

    # 2. Set with 2 seconds TTL
    saved = await cache_repo.set_payload(key, payload, ttl_seconds=2)
    assert saved is True

    # 3. Read fresh
    fresh = await cache_repo.get_payload(key, allow_expired=False)
    assert fresh is not None
    assert fresh[0] == payload
    assert fresh[1] is False  # not expired

    # 4. Wait for expiration
    await asyncio.sleep(2.1)

    # 5. Read expired without allow_expired -> None
    expired_disallowed = await cache_repo.get_payload(key, allow_expired=False)
    assert expired_disallowed is None

    # 6. Read expired with allow_expired=True -> (payload, True)
    expired_allowed = await cache_repo.get_payload(key, allow_expired=True)
    assert expired_allowed is not None
    assert expired_allowed[0] == payload
    assert expired_allowed[1] is True  # is expired

    # 7. Delete expired
    deleted_count = await cache_repo.delete_expired()
    assert deleted_count == 1

    # After deletion, even allow_expired=True returns None
    assert await cache_repo.get_payload(key, allow_expired=True) is None


@pytest.mark.asyncio
async def test_cache_repository_exceptions():
    with patch("bot.repository.schedule_cache_repository.fetchone", AsyncMock(side_effect=Exception("DB fail"))):
        repo = ScheduleCacheRepository()
        assert await repo.get_payload("k") is None
        assert await repo.delete_expired() == 0

    with patch("bot.repository.schedule_cache_repository.execute", AsyncMock(side_effect=Exception("DB fail"))):
        repo = ScheduleCacheRepository()
        assert await repo.set_payload("k", "p", 100) is False


@pytest.mark.asyncio
async def test_schedule_service_l1_and_l2_cache(cache_repo: ScheduleCacheRepository):
    mock_api = MagicMock()
    mock_api.get_schedule = AsyncMock()

    item = SearchItem(type="teacher", uid=10, name="Карпов")
    lesson = LessonSchedule(
        dates=["01-09-2025"],
        lesson_bells=LessonBells(number=1),
        subject="Математический анализ",
    )
    schedule = ScheduleData(data=[lesson])
    mock_api.get_schedule.return_value = schedule

    service = ScheduleService(
        api_client=mock_api,
        cache_repo=cache_repo,
        schedule_ttl=3600,
        memory_ttl=60,
    )

    # 1. First call: cache miss -> calls API
    s1 = await service.get_schedule(item)
    assert s1 is not None
    assert s1.data[0].subject == "Математический анализ"
    assert mock_api.get_schedule.call_count == 1

    # 2. Second call: L1 in-memory hit -> does NOT call API
    s2 = await service.get_schedule(item)
    assert s2 is not None
    assert mock_api.get_schedule.call_count == 1  # unchanged!

    # 3. Clear L1 memory -> L2 SQLite hit -> does NOT call API
    service._memory_cache.clear()
    s3 = await service.get_schedule(item)
    assert s3 is not None
    assert s3.data[0].subject == "Математический анализ"
    assert mock_api.get_schedule.call_count == 1  # still unchanged!


@pytest.mark.asyncio
async def test_schedule_service_stale_fallback(cache_repo: ScheduleCacheRepository):
    mock_api = MagicMock()
    item = SearchItem(type="group", uid=20, name="ИКБО-20-23")
    lesson = LessonSchedule(
        dates=["01-09-2025"],
        lesson_bells=LessonBells(number=1),
        subject="Базы данных",
    )
    schedule = ScheduleData(data=[lesson])

    # Initial success with very short TTL
    mock_api.get_schedule = AsyncMock(return_value=schedule)
    service = ScheduleService(
        api_client=mock_api,
        cache_repo=cache_repo,
        schedule_ttl=1,  # 1 second TTL
        memory_ttl=0.1,
    )

    await service.get_schedule(item)
    assert mock_api.get_schedule.call_count == 1

    # Wait for expiration
    await asyncio.sleep(1.2)
    service._memory_cache.clear()

    # Now live API fails (e.g. 500 error / server maintenance)
    mock_api.get_schedule.return_value = None

    # Should gracefully return stale data from L2 cache!
    stale_sched = await service.get_schedule(item)
    assert stale_sched is not None
    assert stale_sched.data[0].subject == "Базы данных"
    assert mock_api.get_schedule.call_count == 2


@pytest.mark.asyncio
async def test_schedule_service_search_caching(cache_repo: ScheduleCacheRepository):
    mock_api = MagicMock()
    mock_api.search = AsyncMock()

    items = [SearchItem(type="teacher", uid=1, name="Афанасьев")]
    mock_api.search.return_value = items

    service = ScheduleService(
        api_client=mock_api,
        cache_repo=cache_repo,
        search_ttl=3600,
        memory_ttl=60,
    )

    # Empty query
    assert await service.search("") == []
    assert mock_api.search.call_count == 0

    # First search -> API hit
    res1 = await service.search("  Афанасьев  ")
    assert len(res1) == 1
    assert mock_api.search.call_count == 1

    # Second search with different case/spaces -> L1 Memory hit
    res2 = await service.search("афанасьев")
    assert len(res2) == 1
    assert mock_api.search.call_count == 1

    # L2 SQLite hit
    service._memory_cache.clear()
    res3 = await service.search("Афанасьев")
    assert len(res3) == 1
    assert mock_api.search.call_count == 1

    # Stale fallback for search
    service._search_ttl = 1
    service._memory_ttl = 0.1
    # Save with short TTL
    await cache_repo.set_payload("search:афанасьев", '[{"type": "teacher", "uid": 1, "name": "Афанасьев"}]', ttl_seconds=1)
    await asyncio.sleep(1.2)
    service._memory_cache.clear()
    mock_api.search.return_value = None  # API fails

    res_stale = await service.search("афанасьев")
    assert res_stale is not None
    assert len(res_stale) == 1
