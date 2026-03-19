from datetime import date

from bot.api_client import ScheduleApiClient
from bot.fetch.models import Lesson, LessonSchedule, ScheduleData, SearchItem


class ScheduleService:
    def __init__(self, api_client: ScheduleApiClient):
        self._api_client = api_client

    async def search(self, query: str) -> list[SearchItem] | None:
        return await self._api_client.search(query)

    async def get_schedule(self, item: SearchItem) -> ScheduleData | None:
        return await self._api_client.get_schedule(item)

    def get_lessons(self, schedule: ScheduleData, dates: list[date] | None = None) -> list[Lesson]:
        lessons_list = []
        for item in schedule.data:
            if isinstance(item, LessonSchedule):
                for schedule_date in item.dates:
                    if dates:
                        if schedule_date in dates:
                            lesson = item.model_copy()
                            lessons_list.append(
                                Lesson(
                                    dates=schedule_date,
                                    **lesson.model_dump(exclude={"dates"}),
                                )
                            )
                    else:
                        lesson = item.model_copy()
                        lessons_list.append(
                            Lesson(
                                dates=schedule_date,
                                **lesson.model_dump(exclude={"dates"}),
                            )
                        )

        lessons_list.sort(key=lambda x: (x.dates, x.lesson_bells.number))
        return lessons_list
