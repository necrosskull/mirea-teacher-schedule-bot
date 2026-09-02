from datetime import date

from bot.api_client import ScheduleApiClient
from bot.fetch.models import Lesson, LessonSchedule, ScheduleData, SearchItem


async def get_schedule(target: SearchItem) -> ScheduleData | None:
    return await ScheduleApiClient().get_schedule(target)


def get_lessons(user_data: ScheduleData, dates: list[date] | None = None) -> list[Lesson]:
    lessons_list = []
    for item in user_data.data:
        if isinstance(item, LessonSchedule) and item.dates:
            for schedule_date in item.dates:
                if dates is None or schedule_date in dates:
                    lesson = item.model_copy()
                    lessons_list.append(
                        Lesson(dates=schedule_date, **lesson.model_dump(exclude={"dates"}))
                    )

    lessons_list.sort(key=lambda x: (x.dates, x.lesson_bells.number))
    return lessons_list

