import bot.lazy_logger as logger
import bot.formats.decode as decode
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
            teachers = ", ".join(decode.decode_teachers(
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
                logger.lazy_logger.error(json.dumps(
                    {"type": "error",
                     "teacher": context.user_data['teacher'],
                     "week": context.user_data['week'],
                     }, ensure_ascii=False))

            else:
                error_message = str(e)
                logger.lazy_logger.error(json.dumps(
                    {"type": "error",
                     "teacher": context.user_data['teacher'],
                     "week": context.user_data['week'],
                     }, ensure_ascii=False))
                text += "Ошибка при получении расписания, сообщите об этом администрации в чате " \
                        "https://t.me/mirea_ninja_chat"
                blocks.append(text)
                text = ""

                return blocks

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


def check_same_surnames(teacher_schedule, surname):
    """
    Проверяет имеющихся в JSON преподавателей.
    В случае нахождения однофамильца, но сдругим именем или фамилией заносит в список surnames
    :param teacher_schedule: JSON строка расписания
    :param surname: Строка фильтрации, например фамилия
    :return: surnames - лист ФИО преподавателей
    """
    surnames = []
    for teacher in teacher_schedule:
        if surname in teacher['name']:
            if teacher['name'][-1] != ".":
                teacher['name'] += "."

            surnames.append(teacher['name'])
            surnames = list(set(surnames))

    return surnames


def parse(teacher_schedule, weekday, week_number, teacher, context):
    context.user_data["teacher"] = teacher

    for lesson in teacher_schedule:
        teacher_schedule = lesson["lessons"]

        teacher_schedule = sorted(
            teacher_schedule,
            key=lambda lesson: (
                lesson['weekday'],
                lesson['calls']['num'],
                lesson['group']['name']),
            reverse=False)

        if (weekday != -1):
            teacher_schedule = list(
                filter(
                    lambda lesson: lesson['weekday'] == int(weekday),
                    teacher_schedule))

        teacher_schedule = list(
            filter(
                lambda x: int(week_number) in x['weeks'],
                teacher_schedule))

        return teacher_schedule


def remove_duplicates_merge_groups_with_same_lesson(teacher_schedule):
    remove_index = []

    for i in range(len(teacher_schedule)):
        for j in range(i + 1, len(teacher_schedule)):
            if (
                    teacher_schedule[i]['calls']['num'] == teacher_schedule[j]['calls']['num'] and
                    teacher_schedule[i]['weeks'] == teacher_schedule[j]['weeks'] and
                    teacher_schedule[i]['weekday'] == teacher_schedule[j]['weekday']
            ):
                teacher_schedule[i]["group"]["name"] += ", " + \
                                                        teacher_schedule[j]["group"]["name"]

                remove_index.append(j)

    remove_index = set(remove_index)

    for i in sorted(remove_index, reverse=True):
        del teacher_schedule[i]

    return teacher_schedule


def merge_weeks_numbers(teacher_schedule):
    for i in range(len(teacher_schedule)):
        if teacher_schedule[i]['weeks'] == list(range(1, 18)):
            teacher_schedule[i]['weeks'] = "все"

        elif teacher_schedule[i]['weeks'] == list(range(2, 19, 2)):
            teacher_schedule[i]['weeks'] = "по чётным"

        elif teacher_schedule[i]['weeks'] == list(range(1, 18, 2)):
            teacher_schedule[i]['weeks'] = "по нечётным"

        else:
            teacher_schedule[i]['weeks'] = ", ".join(
                str(week) for week in teacher_schedule[i]['weeks'])

    return teacher_schedule
