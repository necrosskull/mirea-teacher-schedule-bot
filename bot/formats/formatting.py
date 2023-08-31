import itertools
from datetime import datetime
import bot.lazy_logger as logger
import bot.formats.decode as decode
import json


def format_outputs(parsed_schedule, context):
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
    }

    blocks = []
    zipped_teachers = []
    teachers = ""

    if context.user_data["state"] == "get_name":
        teachers = ", ".join(decode.decode_teachers(
            [context.user_data["teacher"]]))

    else:
        teacher_lists = [schedule.get("teachers", []) for schedule in parsed_schedule]
        teacher_names = {teacher.get("name", "") for teacher in itertools.chain(*teacher_lists)}

        teacher_list = list(teacher_names)
        decoded_list = decode.decode_teachers(teacher_list)
        zipped_teachers = list(zip(teacher_list, decoded_list))

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

            if context.user_data["state"] != "get_name":
                if schedule["teachers"]:
                    for teacher in schedule["teachers"]:
                        if teacher["name"]:
                            teachers = ", ".join([name[1] for name in zipped_teachers if name[0] == teacher["name"]])
                        else:
                            teachers = ""
                else:
                    teachers = ""

            groups = schedule["group"]["name"] if schedule["group"] and schedule["group"]["name"] else ""

            time_start = datetime.strptime(
                schedule['calls']['time_start'],
                "%H:%M:%S").strftime("%H:%M")

            time_end = datetime.strptime(
                schedule['calls']['time_end'],
                "%H:%M:%S").strftime("%H:%M")

            formatted_time = f"{time_start} – {time_end}"

            lesson_type = schedule["lesson_type"]["name"] if schedule["lesson_type"] else ""

            text += f'📝 Пара № {schedule["calls"]["num"]} в ⏰ {formatted_time}\n'
            text += f'📝 {schedule["discipline"]["name"]}\n'
            if len(groups) > 0:
                text += f'👥 Группы: {groups}\n'
            text += f'📚 Тип: {lesson_type}\n'
            text += f"👨🏻‍🏫 Преподаватели: {teachers}\n"
            text += f"🏫 Аудитории: {room}\n"
            text += f'📅 Недели: {schedule["weeks"]}\n'
            text += f"📆 День недели: {weekday}\n\n"

            blocks.append(text)
            text = ""

        except Exception as e:
            if context.user_data["state"] == "get_room":
                target_info = {
                    "type": "error",
                    "room": context.user_data['room'],
                    "week": context.user_data['week']

                }
            elif context.user_data["state"] == "get_name":

                target_info = {
                    "type": "error",
                    "teacher": context.user_data['teacher'],
                    "week": context.user_data['week']

                }
            elif context.user_data["state"] == "get_group":

                target_info = {
                    "type": "error",
                    "group": context.user_data['group'],
                    "week": context.user_data['week']

                }

            else:
                target_info = {
                    "type": "error",
                }

            if str(e) != error_message:
                error_message = str(e)
                logger.lazy_logger.error(json.dumps(target_info, ensure_ascii=False))
                text = "Ошибка при получении расписания, сообщите об этом в техподдержку @mirea_help_bot"
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
    name_parts = teacher.split()

    if len(name_parts) > 1:
        last_name = name_parts[0]

        # Для запроса вида "Иванов И.И. или Иванов И.И"
        if name_parts[1][-1] == "." or len(name_parts[1]) > 1 and name_parts[1][-2] == ".":
            initials = name_parts[1]
        else:
            # Для запроса вида "Иванов Иван Иванович и прочих"
            initials = ''.join([part[0] + '.' for part in name_parts[1:3]])

        teacher = last_name + ' ' + initials

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


def parse(teacher_schedule, weekday, week_number, context, teacher=None, room=None, group=None):
    if room:
        context.user_data["room"] = room
        filtered_schedule = teacher_schedule

        filtered_schedule = sorted(
            filtered_schedule,
            key=lambda lesson: (
                lesson['weekday'],
                lesson['calls']['num'],
                lesson['discipline']['name']
            ),
            reverse=False
        )

        if weekday != -1:
            filtered_schedule = list(
                filter(
                    lambda lesson: lesson['weekday'] == int(weekday),
                    filtered_schedule
                )
            )

        filtered_schedule = list(
            filter(
                lambda lesson: int(week_number) in lesson['weeks'],
                filtered_schedule
            )
        )

        return filtered_schedule

    elif group:

        context.user_data["group"] = group

        filtered_schedule = teacher_schedule["lessons"]

        filtered_schedule = sorted(
            filtered_schedule,
            key=lambda lesson: (
                lesson['weekday'],
                lesson['calls']['num'],
                lesson['discipline']['name']
            ),
            reverse=False
        )

        if weekday != -1:
            filtered_schedule = list(
                filter(
                    lambda lesson: lesson['weekday'] == int(weekday),
                    filtered_schedule
                )
            )

        filtered_schedule = list(
            filter(
                lambda lesson: int(week_number) in lesson['weeks'],
                filtered_schedule
            )
        )

        return filtered_schedule

    else:
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

            if weekday != -1:
                teacher_schedule = list(
                    filter(
                        lambda lesson: lesson['weekday'] == int(weekday),
                        teacher_schedule))

            teacher_schedule = list(
                filter(
                    lambda x: int(week_number) in x['weeks'],
                    teacher_schedule))

            return teacher_schedule


def remove_duplicates_merge_groups_with_same_lesson(teacher_schedule, context):
    remove_index = []

    for i in range(len(teacher_schedule)):
        for j in range(i + 1, len(teacher_schedule)):
            if (
                    teacher_schedule[i]['calls']['num'] == teacher_schedule[j]['calls']['num'] and
                    teacher_schedule[i]['weeks'] == teacher_schedule[j]['weeks'] and
                    teacher_schedule[i]['weekday'] == teacher_schedule[j]['weekday']
            ):
                if context.user_data["state"] != "get_room":
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
            teacher_schedule[i]['weeks'] = "Все"

        elif teacher_schedule[i]['weeks'] == list(range(2, 19, 2)):
            teacher_schedule[i]['weeks'] = "По чётным"

        elif teacher_schedule[i]['weeks'] == list(range(1, 18, 2)):
            teacher_schedule[i]['weeks'] = "По нечётным"

        else:
            teacher_schedule[i]['weeks'] = ", ".join(
                str(week) for week in teacher_schedule[i]['weeks'])

    return teacher_schedule


def check_same_rooms(room_schedule, room):
    classes = []
    for rooms in room_schedule:
        if room in rooms['name'].lower():
            class_info = f"{rooms['name']}:{rooms['id']}"
            classes.append(class_info)

    return classes
