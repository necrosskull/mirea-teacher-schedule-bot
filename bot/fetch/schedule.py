from datetime import date

import httpx

from bot.config import settings
from bot.fetch.models import Lesson, LessonSchedule, ScheduleData, SearchItem


async def get_schedule(target: SearchItem) -> ScheduleData | None:
    base_url = f"{settings.api_url}/api/v1/schedule/{target.type}/{target.uid}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(base_url)
            response.raise_for_status()
            json_response = response.json()

        except httpx.RequestError:
            return None

        return ScheduleData(**json_response)


def get_lessons(user_data: ScheduleData, dates: list[date] = None) -> list[Lesson]:
    lessons_list = []
    for item in user_data.data:
        if isinstance(item, LessonSchedule):
            for date in item.dates:
                if dates:
                    if date in dates:
                        lesson = item.model_copy()
                        lessons_list.append(
                            Lesson(dates=date, **lesson.model_dump(exclude={"dates"}))
                        )
                else:
                    lesson = item.model_copy()
                    lessons_list.append(
                        Lesson(dates=date, **lesson.model_dump(exclude={"dates"}))
                    )

    lessons_list.sort(key=lambda x: (x.dates, x.lesson_bells.number))
    return lessons_list
