from decode import decode_teachers
from lazy_logger import lazy_logger
import json


def format_outputs(parsed_schedule, context):
    from datetime import datetime
    text = ""
    WEEKDAYS = {
        1: "Понедельник",
        2: "Вторник",
        3: "Среда",
        4: "Четверг",
        5: "Пятница",
        6: "Суббота",
    }

    blocks = []

    for schedule in parsed_schedule:

        error_message = None

        try:
            room = schedule["room"]["name"] if schedule["room"] is not None else ""
            campus = schedule["room"]["campus"]["short_name"] if schedule["room"] and schedule["room"]["campus"] else ""

            if campus != "":
                room = f"{room} ({campus})"

            else:
                room = f"{room}"

            weekday = WEEKDAYS[schedule["weekday"]]
            teachers = ", ".join(decode_teachers(
                [context.user_data["teacher"]]))

            time_start = datetime.strptime(
                schedule['calls']['time_start'],
                "%H:%M:%S").strftime("%H:%M")

            time_end = datetime.strptime(
                schedule['calls']['time_end'],
                "%H:%M:%S").strftime("%H:%M")

            formatted_time = f"{time_start} – {time_end}"

            type = schedule["lesson_type"]["name"] if schedule["lesson_type"] else ""

            text += f'📝 Пара № {schedule["calls"]["num"]} в ⏰ {formatted_time}\n'
            text += f'📝 {schedule["discipline"]["name"]}\n'
            text += f'👥 Группы: {schedule["group"]["name"]}\n'
            text += f'📚 Тип: {type}\n'
            text += f"👨🏻‍🏫 Преподаватели: {teachers}\n"
            text += f"🏫 Аудитории: {room}\n"
            text += f'📅 Недели: {schedule["weeks"]}\n'
            text += f"📆 День недели: {weekday}\n\n"

            blocks.append(text)
            text = ""

        except Exception as e:

            if str(e) == error_message:
                lazy_logger.error(json.dumps(
                    {"type": "error",
                     "teacher": context.user_data['teacher'],
                     "week": context.user_data['week'],
                     }, ensure_ascii=False))

            else:
                error_message = str(e)
                lazy_logger.error(json.dumps(
                    {"type": "error",
                     "teacher": context.user_data['teacher'],
                     "week": context.user_data['week'],
                     }, ensure_ascii=False))
                text += "Ошибка при получении расписания, сообщите об этом администрации в чате " \
                        "https://t.me/mirea_ninja_chat"
                blocks.append(text)
                text = ""

    return blocks


def normalize_teachername(raw_teacher_name: str):
    """
    Нормализация фамилии для уточнения.
    @param raw_teacher_name: Ввод пользователя
    @return: Фамилия начинаяющая с большой буквы и с пробелом в конце
    """
    teacher = raw_teacher_name.title()

    if " " not in teacher:
        teacher += " "

    return teacher
