from datetime import date
import json
import time

from bot.api_client import ScheduleApiClient
from bot.config import settings
from bot.fetch.models import Lesson, LessonSchedule, ScheduleData, SearchItem
from bot.logs.lazy_logger import lazy_logger
from bot.repository.schedule_cache_repository import ScheduleCacheRepository
from bot.repository.user_repository import UserRepository


class ScheduleService:
    def __init__(
        self,
        api_client: ScheduleApiClient,
        cache_repo: ScheduleCacheRepository | None = None,
        user_repo: UserRepository | None = None,
        schedule_ttl: int | None = None,
        search_ttl: int | None = None,
        memory_ttl: int | None = None,
    ):
        self._api_client = api_client
        self._cache_repo = cache_repo
        self._user_repo = user_repo

        self._schedule_ttl = (
            schedule_ttl
            if schedule_ttl is not None
            else settings.schedule_cache_ttl_seconds
        )
        self._search_ttl = (
            search_ttl if search_ttl is not None else settings.search_cache_ttl_seconds
        )
        self._memory_ttl = (
            memory_ttl if memory_ttl is not None else settings.memory_cache_ttl_seconds
        )
        self._memory_cache: dict[str, tuple[float, any]] = {}

    def _get_from_memory(self, cache_key: str) -> any | None:
        if cache_key in self._memory_cache:
            expire_ts, data = self._memory_cache[cache_key]
            if time.monotonic() < expire_ts:
                return data
            del self._memory_cache[cache_key]
        return None

    def _save_to_memory(
        self, cache_key: str, data: any, ttl_seconds: int | None = None
    ) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._memory_ttl
        self._memory_cache[cache_key] = (time.monotonic() + ttl, data)

    async def search(self, query: str) -> list[SearchItem] | None:
        norm_query = query.strip().lower()
        if not norm_query:
            return []

        cache_key = f"search:{norm_query}"

        # 1. Check L1 Memory Cache
        mem_data = self._get_from_memory(cache_key)
        if mem_data is not None:
            return mem_data

        # 2. Check L2 SQLite Cache (fresh only)
        if self._cache_repo:
            cached = await self._cache_repo.get_payload(cache_key, allow_expired=False)
            if cached:
                payload_str, _ = cached
                try:
                    raw_list = json.loads(payload_str)
                    items = [SearchItem(**x) for x in raw_list]
                    self._save_to_memory(cache_key, items)
                    return items
                except Exception as e:
                    lazy_logger.logger.warning(
                        f"Failed to parse search cache for '{cache_key}': {e}"
                    )

        # 3. Live API request
        items = await self._api_client.search(query)
        if items is not None:
            self._save_to_memory(cache_key, items)
            if self._cache_repo:
                serialized = json.dumps([x.model_dump() for x in items], ensure_ascii=False)
                await self._cache_repo.set_payload(cache_key, serialized, self._search_ttl)
            return items

        # 4. Fallback to stale L2 cache on API failure
        if self._cache_repo:
            cached = await self._cache_repo.get_payload(cache_key, allow_expired=True)
            if cached:
                payload_str, _ = cached
                try:
                    raw_list = json.loads(payload_str)
                    items = [SearchItem(**x) for x in raw_list]
                    lazy_logger.logger.info(f"API unavailable. Using stale search cache for '{query}'")
                    return items
                except Exception:
                    pass

        return None

    async def get_schedule(self, item: SearchItem) -> ScheduleData | None:
        if self._user_repo and item.name:
            try:
                await self._user_repo.record_item_request(
                    item.type, int(item.uid), item.name
                )
            except Exception:
                pass

        cache_key = f"schedule:{item.type}:{item.uid}"

        # 1. Check L1 Memory Cache
        mem_data = self._get_from_memory(cache_key)
        if mem_data is not None:
            return mem_data


        # 2. Check L2 SQLite Cache (fresh only)
        if self._cache_repo:
            cached = await self._cache_repo.get_payload(cache_key, allow_expired=False)
            if cached:
                payload_str, _ = cached
                try:
                    schedule = ScheduleData.model_validate_json(payload_str)
                    self._save_to_memory(cache_key, schedule)
                    return schedule
                except Exception as e:
                    lazy_logger.logger.warning(
                        f"Failed to parse schedule cache for '{cache_key}': {e}"
                    )

        # 3. Live API request
        schedule = await self._api_client.get_schedule(item)
        if schedule is not None:
            self._save_to_memory(cache_key, schedule)
            if self._cache_repo:
                serialized = schedule.model_dump_json()
                await self._cache_repo.set_payload(cache_key, serialized, self._schedule_ttl)
            return schedule

        # 4. Fallback to stale L2 cache on API failure
        if self._cache_repo:
            cached = await self._cache_repo.get_payload(cache_key, allow_expired=True)
            if cached:
                payload_str, _ = cached
                try:
                    schedule = ScheduleData.model_validate_json(payload_str)
                    lazy_logger.logger.warning(
                        f"API unavailable. Serving stale schedule cache for {item.type}:{item.uid}"
                    )
                    return schedule
                except Exception:
                    pass

        return None

    def get_lessons(
        self, schedule: ScheduleData, dates: list[date] | None = None
    ) -> list[Lesson]:
        lessons_list = []
        for item in schedule.data:
            if isinstance(item, LessonSchedule) and item.dates:
                for schedule_date in item.dates:
                    if dates is None or schedule_date in dates:
                        lesson = item.model_copy()
                        lessons_list.append(
                            Lesson(
                                dates=schedule_date,
                                **lesson.model_dump(exclude={"dates"}),
                            )
                        )

        lessons_list.sort(key=lambda x: (x.dates, x.lesson_bells.number))
        return lessons_list
