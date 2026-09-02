import json

from bot.fetch.models import Lesson
from bot.logs.lazy_logger import lazy_logger
from bot.parse.semester import get_week_and_weekday


def format_outputs(lessons: list[Lesson], user_data: dict):
    """
    Format the parsed schedule into human-readable text blocks.

    Parameters:
    - parsed_schedule (list): List of dictionaries representing parsed schedule data.
    - context (object): Context object containing user-specific data.

    Returns:
    - blocks (list): List of formatted text blocks.

    """
    text = ""

    WEEKDAYS = {
        1: "Понедельник",
        2: "Вторник",
        3: "Среда",
        4: "Четверг",
        5: "Пятница",
        6: "Суббота",
        7: "Воскресенье",
    }

    MONTHS = {
        1: "Января",
        2: "Февраля",
        3: "Марта",
        4: "Апреля",
        5: "Мая",
        6: "Июня",
        7: "Июля",
        8: "Августа",
        9: "Сентября",
        10: "Октября",
        11: "Ноября",
        12: "Декабря",
    }

    blocks = []
    error_message = None

    for lesson in lessons:
        try:
            week, weekday = get_week_and_weekday(lesson.dates)
            raw_type = (lesson.lesson_type or "").lower()
            match raw_type:
                case "lecture":
                    lesson_type = "Лекция"
                case "laboratorywork":
                    lesson_type = "Лабораторная"
                case "practice":
                    lesson_type = "Практика"
                case "individualwork":
                    lesson_type = "Сам. работа"
                case "exam":
                    lesson_type = "Экзамен"
                case "consultation":
                    lesson_type = "Консультация"
                case "coursework":
                    lesson_type = "Курс. раб."
                case "courseproject":
                    lesson_type = "Курс. проект"
                case "credit":
                    lesson_type = "Зачет"
                case _:
                    lesson_type = "Неизвестно"

            formatted_time = (
                f"{lesson.lesson_bells.start_time} – {lesson.lesson_bells.end_time}"
            )

            groups = ", ".join(lesson.groups) if lesson.groups else ""
            teachers = (
                ", ".join(teacher.name for teacher in lesson.teachers if teacher and teacher.name)
                if lesson.teachers
                else ""
            )
            campus = (
                f"({lesson.classrooms[0].campus.short_name})"
                if lesson.classrooms and lesson.classrooms[0].campus and lesson.classrooms[0].campus.short_name
                else ""
            )
            room = (
                lesson.classrooms[0].name
                if lesson.classrooms and lesson.classrooms[0].name
                else ""
            )

            weekday_name = WEEKDAYS.get(weekday, "Неизвестно")
            month_name = MONTHS.get(lesson.dates.month, "")

            text += f"📝 Пара № {lesson.lesson_bells.number} в ⏰ {formatted_time}\n"
            text += f"📝 {lesson.subject}\n"
            text += f"📚 {lesson_type}\n"
            if len(groups) > 0:
                text += f"👥 Группы: {groups}\n"
            if len(teachers) > 0:
                text += f"👨🏻‍🏫 Преподаватели: {teachers}\n"
            if room or campus:
                text += f"🏫 Аудитории: {room} {campus}".rstrip() + "\n"
            text += f"📅 Неделя: {week}\n"
            text += f"🗓️ {lesson.dates.day} {month_name} ({weekday_name})\n\n"

            blocks.append(text)
            text = ""

        except Exception as e:
            text = ""
            item_raw = user_data.get("item") if isinstance(user_data, dict) else None
            item_dump = (
                item_raw.model_dump()
                if hasattr(item_raw, "model_dump")
                else str(item_raw)
            )
            target_info = {
                "type": "error",
                "item": item_dump,
                "error": str(e),
            }

            if str(e) != error_message:
                error_message = str(e)
                lazy_logger.logger.error(json.dumps(target_info, ensure_ascii=False))
                blocks.append("Ошибка при получении расписания")

            continue

    return blocks

