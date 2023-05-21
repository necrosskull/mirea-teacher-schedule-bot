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
