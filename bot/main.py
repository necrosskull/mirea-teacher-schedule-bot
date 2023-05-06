import datetime
import logging
import json
from typing import Any

import requests
from InlineStep import EInlineStep
import ImportantDays
from config import TELEGRAM_TOKEN, cmstoken, grafana_token
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, InlineQueryResultArticle, \
    InputTextMessageContent
from telegram.ext import (
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    Updater,
    InlineQueryHandler,
    ChosenInlineResultHandler
)
import logging_loki


class LazyLogger:
    def __init__(self):
        self.logger = None

    def init_logger(self, grafana_token):
        if grafana_token:
            loki_handler = logging_loki.LokiHandler(
                url="https://loki.grafana.mirea.ninja/loki/api/v1/push",
                auth=("logger", grafana_token),
                tags={"app": "mirea-teacher-schedule-bot", "env": "production"},
                version="1",
            )

            self.logger = logging.getLogger("bot.handlers")
            self.logger.setLevel("INFO")
            self.logger.addHandler(loki_handler)
        else:
            self.logger = logging.getLogger("bot.handlers")
            self.logger.setLevel("INFO")

    def __getattr__(self, attr):
        if not self.logger:
            self.init_logger(grafana_token)
        return getattr(self.logger, attr)


lazy_logger = LazyLogger()

updater = Updater(TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

GETNAME, GETDAY, GETWEEK, TEACHER_CLARIFY, BACK = range(5)


# Handlers
def start(update: Update, context: CallbackContext) -> int:
    """
    Привествие бота при использовании команды /start
    """
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Привет!\nЯ бот, который поможет тебе найти "
             "расписание любого *преподавателя.*\nНапиши мне "
             "его фамилию "
             "в формате:\n*Фамилия* или *Фамилия И.О.* поддерживаются только инициалы!",
        parse_mode="Markdown")

    # Переключаемся в состояние GETNAME (ожидание ввода фамилии)
    return GETNAME


def got_name_handler(update: Update, context: CallbackContext) -> int:
    """
    Реакция бота на получение фамилии преподавателя при состоянии GETNAME
    :param update - Update класс API
    :param context - CallbackContext класс API
    :return: int сигнатура следующего состояния
    """
    inputed_teacher = update.message.text
    lazy_logger.info(json.dumps(
        {"type": "request", "query": inputed_teacher.lower(), **update.message.from_user.to_dict()}, ensure_ascii=False
    )
    )
    if len(inputed_teacher) < 2:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Слишком короткий запрос\nПопробуйте еще раз")
        return GETNAME
    teacher = normalize_teachername(inputed_teacher)

    # Устанавливаем расписание преподавателей в контексте для избежания повторных запросов
    teacher_schedule = fetch_schedule_by_name(teacher)

    if teacher_schedule is None:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Ошибка при поиске\n\nУбедитесь, что вы ввели фамилию преподавателя в формате:\n*Фамилия* или "
                 "*Фамилия И.О.* поддерживаются только инициалы!\n\n"
                 "Если преподаватель присутствует в расписании, попробуйте ещё раз позднее", parse_mode="Markdown")
        return GETNAME

    context.user_data["schedule"] = teacher_schedule
    available_teachers = check_same_surnames(teacher_schedule, teacher)

    if len(available_teachers) > 1:
        context.user_data["available_teachers"] = available_teachers
        return send_teacher_clarity(update, context, True)

    elif len(available_teachers) == 0:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Ошибка при определении ФИО преподавателя. Повторите попытку, изменив запрос.\n" +
                 "Например введите только фамилию преподавателя."
        )
        return GETNAME

    else:
        context.user_data["available_teachers"] = None
        context.user_data['teacher'] = available_teachers[0]
        return send_week_selector(update, context, True)


def got_teacher_clarification_handler(update: Update, context: CallbackContext):
    """
    Реакция бота на получение фамилии преподавателя при уточнении, при состоянии TEACHER_CLARIFY
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """
    chosed_teacher = update.callback_query.data
    context.user_data['teacher'] = chosed_teacher
    clarified_schedule = fetch_schedule_by_name(chosed_teacher)
    context.user_data['schedule'] = clarified_schedule
    if chosed_teacher == "back":
        return resend_name_input(update, context)
    return send_week_selector(update, context)


def got_week_handler(update: Update, context: CallbackContext) -> Any | None:
    """
    Реакция бота на получение информации о выбранной недели в состоянии GETWEEK
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """
    selected_button = update.callback_query.data
    if selected_button == "back":
        if context.user_data['available_teachers'] != None:
            return send_teacher_clarity(update, context)
        else:
            return resend_name_input(update, context)

    elif selected_button == "today" or selected_button == "tomorrow":
        today = datetime.date.today().weekday()
        req = requests.get("https://schedule.mirea.ninja/api/schedule/current_week").json()
        week = req["week"]
        if selected_button == "tomorrow":
            if today == 6:
                week += 1  # Корректировка недели, в случае если происходит переход недели
            today = (datetime.date.today() + datetime.timedelta(days=1)).weekday()
        if today == 6:
            update.callback_query.answer("В выбранный день пар нет")
            return GETWEEK
        today += 1  # Корректировка дня с 0=пн на 1=пн
        context.user_data["week"] = week
        context.user_data["day"] = today
        return send_result(update, context)

    else:
        selected_week = int(selected_button)
        context.user_data["week"] = selected_week
        return send_day_selector(update, context)


def got_day_handler(update: Update, context: CallbackContext):
    """
    Реакция бота на выбор дня недели, предоставленный пользователю, в состоянии GETDAY
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Int код шага
    """

    selected_button = update.callback_query.data
    if selected_button == "chill":
        update.callback_query.answer(text="В этот день пар нет.", show_alert=True)
        return GETDAY
    if selected_button == "back":
        return send_week_selector(update, context)
    selected_day = -1
    if selected_button != "week":
        selected_day = int(selected_button)
    context.user_data["day"] = selected_day
    try:
        return send_result(update, context)
    except Exception as e:
        update.callback_query.answer(text="Вы уже выбрали этот день", show_alert=False)

    return GETDAY


# End Handlers
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


def fetch_schedule_by_name(teacher_name):
    """
    Получение информации о расписании через API Mirea Ninja
    @param teacher_name: Имя преподавателя
    @return: JSON расписание или None если преподаватель не найден
    """
    url = f"https://schedule.mirea.ninja/api/schedule/teacher/{teacher_name}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None


def send_week_selector(update: Update, context: CallbackContext, firsttime=False):
    """
    Отправка селектора недели. По умолчанию изменяет предыдущее сообщение, но при firsttime=True отправляет в виде нового сообщения
    @param update: Update class of API
    @param context: CallbackContext of API
    @param firsttime: Впервые ли производится общение с пользователем
    @return: Статус следующего шага - GETWEEK
    """
    teacher = ", ".join(decode_teachers([context.user_data["teacher"]]))
    if firsttime:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Выбран преподаватель: {teacher}\n" +
                 f"Выберите неделю",
            reply_markup=construct_weeks_markup()
        )

    else:
        update.callback_query.edit_message_text(
            text=f"Выбран преподаватель: {teacher}\n" +
                 f"Выберите неделю",
            reply_markup=construct_weeks_markup()
        )

    return GETWEEK


def resend_name_input(update: Update, context: CallbackContext):
    """
    Просит ввести имя преподавателя заново
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Статус следующего шага - GETNAME
    """
    update.callback_query.answer(text="Введите новую фамилию", show_alert=True)


def send_teacher_clarity(update: Update, context: CallbackContext, firsttime=False):
    """
    Отправляет список обнаруженных преподавателей. В случае если общение с пользователем не впервые - редактирует сообщение, иначе отправляет новое.
    @param update: Update class of API
    @param context: CallbackContext of API
    @param firsttime: Впервые ли производится общение с пользователем
    @return: Статус следующего шага - TEACHER_CLARIFY
    """
    available_teachers = context.user_data["available_teachers"]
    few_teachers_markup = prepare_teacher_markup(available_teachers)
    if firsttime:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Выберите преподвателя",
            reply_markup=few_teachers_markup
        )
    else:
        update.callback_query.edit_message_text(
            text="Выберите преподвателя",
            reply_markup=few_teachers_markup
        )
    return TEACHER_CLARIFY


def send_day_selector(update: Update, context: CallbackContext):
    """
    Отправляет селектор дня недели с указанием дней, когда преподаватель не имеет пар.
    @param update: Update class of API
    @param context: CallbackContext of API
    @return: Статус следующего шага - GETDAY
    """
    teacher = ", ".join(decode_teachers([context.user_data["teacher"]]))
    week = context.user_data["week"]
    schedule = context.user_data["schedule"]
    teacher_workdays = construct_teacher_workdays(teacher, week, schedule)
    update.callback_query.edit_message_text(
        text=f"Выбран преподаватель: {teacher} \n" +
             f"Выбрана неделя: {week} \n" +
             f"Выберите день",
        reply_markup=teacher_workdays
    )
    return GETDAY


def send_result(update: Update, context: CallbackContext):
    """
    Выводит результат пользователю.
    В user_data["week"] и user_data["day"] должны быть заполнены перед вызовом!
    Если user_data["week"]=-1 - выводится вся неделя
    """
    week = context.user_data["week"]
    weekday = context.user_data["day"]
    schedule_data = context.user_data["schedule"]
    teacher_surname = context.user_data["teacher"]

    parsed_schedule = parse(schedule_data, weekday, week, teacher_surname)
    parsed_schedule = remove_duplicates_merge_groups_with_same_lesson(parsed_schedule)
    parsed_schedule = merge_weeks_numbers(parsed_schedule)
    if len(parsed_schedule) == 0:
        update.callback_query.answer(text="В этот день пар нет.", show_alert=True)
        return GETWEEK
    # Отправляем расписание преподавателя
    blocks_of_text = format_outputs(parsed_schedule)

    return telegram_delivery_optimisation(blocks_of_text, update, context)


def check_same_surnames(teacher_schedule, surname):
    """
    Проверяет имеющихся в JSON преподавателей.
    В случае нахождения однофамильца, но сдругим именем или фамилией заносит в список surnames
    :param teacher_schedule: JSON строка расписания
    :param surname: Строка фильтрации, например фамилия
    :return: surnames - лист ФИО преподавателей
    """
    surnames = []
    schedules = teacher_schedule["schedules"]
    for schedule in schedules:
        teachers = schedule["lesson"]["teachers"]
        for teacher in teachers:
            truncated = str(teacher).replace(" ", '')
            truncated_surname = surname.replace(' ', '')
            if truncated not in str(surnames).replace(' ', '') and truncated_surname in truncated:
                surnames.append(teacher)
    return surnames


def construct_teacher_workdays(teacher: str, week: int, schedule: list):
    """
    Создает Inline клавиатуру с днями недели, когда у преподавателя есть пары.
    В случае если у преподавателя есть пары, то колбэк кнопки равен дню недели
    В случае если пар нет, то колбэк кнопки равен 'chill'
    @param teacher: Имя преподавателя
    @param week: Номер недели
    @param schedule: Расписание в JSON
    @return: InlineKeyboard со стилизованными кнопками
    """
    founded_days = []
    for lesson in schedule['schedules']:
        if week in lesson['lesson']['weeks']:
            if lesson['weekday'] not in founded_days:
                founded_days.append(lesson['weekday'])

    no_work_indicator = "🏖️"
    weekdays = {
        1: "ПН",
        2: "ВТ",
        3: "СР",
        4: "ЧТ",
        5: "ПТ",
        6: "СБ",
    }
    ready_markup = InlineKeyboardMarkup([])
    row_list = []
    for i in range(1, 7):
        sign = ""
        callback = i
        if i not in founded_days:
            sign = "⛔"
            callback = "chill"
        row_list.append(InlineKeyboardButton(text=f"{sign}{weekdays[i]}{sign}", callback_data=callback))
        if i % 3 == 0:
            ready_markup.inline_keyboard.append(row_list)
            row_list = []
    if founded_days:  # добавляем кнопку "На неделю" только если есть пары на неделе
        row_list.append(InlineKeyboardButton(text="На неделю", callback_data="week"))
        ready_markup.inline_keyboard.append(row_list)
    row_list = []
    row_list.append(InlineKeyboardButton(text="Назад", callback_data="back"))
    ready_markup.inline_keyboard.append(row_list)
    return ready_markup


def decode_teachers(rawNames):
    """
    Декодирует ФИО преподавателей используя API CMS
    :param rawNames: список необработанных ФИО
    """
    headers = {
        "Authorization": f"Bearer {cmstoken}"}
    params = {"rawNames": ",".join(rawNames)}

    response = requests.get("https://cms.mirea.ninja/api/get-full-teacher-name", headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()

        decoded_names = []
        for names in data:
            if len(names["possibleFullNames"]) == 1:
                decomposed_name = names["possibleFullNames"][0]
                name = []
                if surname := decomposed_name.get("lastName"):
                    name.append(surname)
                if first_name := decomposed_name.get("firstName"):
                    name.append(first_name)
                if middle_name := decomposed_name.get("middleName"):
                    name.append(middle_name)
                name = " ".join(name)
            else:
                name = names["rawName"]
            decoded_names.append(name)

        decoded_names = decoded_names
    else:
        decoded_names = rawNames
    return decoded_names


def prepare_teacher_markup(teachers):
    """
    Конструирует клавиатуру доступных преподавателей однофамильцев
    :param teachers: лист преподавателей
    """
    rawNames = teachers
    decoded_names = decode_teachers(rawNames)

    btns = []

    for rawName, decoded_name in zip(rawNames, decoded_names):
        btns = btns + [[InlineKeyboardButton(decoded_name, callback_data=rawName)]]
    btns = btns + [[(InlineKeyboardButton("Назад", callback_data="back"))]]
    TEACHER_CLARIFY_MARKUP = InlineKeyboardMarkup(btns)
    return TEACHER_CLARIFY_MARKUP


def construct_weeks_markup():
    """
    Создает KeyboardMarkup со списком недель, а также подставляет эмодзи
    если текущий день соответствует некоторой памятной дате+-интервал
    """
    req = requests.get("https://schedule.mirea.ninja/api/schedule/current_week").json()
    current_week = req["week"]
    week_indicator = "●"
    today = datetime.date.today()
    for day in ImportantDays.important_days:
        if abs((day[ImportantDays.DATE] - today).days) <= day[ImportantDays.INTERVAL]:
            week_indicator = day[ImportantDays.SIGN]

    reply_mark = InlineKeyboardMarkup([])
    button_list = []
    for i in range(1, 18):
        tmp_sign = ""
        if current_week == i:
            tmp_sign = week_indicator
        button_list.append(InlineKeyboardButton(text=f"{tmp_sign}{i}{tmp_sign}", callback_data=i))
        if i % 4 == 0 or i == 17:
            reply_mark.inline_keyboard.append(button_list)
            button_list = []
    backspace = []
    backspace.append(InlineKeyboardButton(text="Сегодня", callback_data="today"))
    backspace.append(InlineKeyboardButton(text="Завтра", callback_data="tomorrow"))
    reply_mark.inline_keyboard.append(backspace)
    backspace = []
    backspace.append(InlineKeyboardButton(text="Назад", callback_data="back"))
    reply_mark.inline_keyboard.append(backspace)
    return reply_mark


def parse(teacher_schedule, weekday, week_number, teacher):
    teacher_schedule = teacher_schedule["schedules"]
    teacher_schedule = list(filter(lambda x: teacher in str(x["lesson"]["teachers"]), teacher_schedule))
    teacher_schedule = sorted(teacher_schedule, key=lambda x: x["group"])
    if (weekday != -1):
        teacher_schedule = list(filter(lambda x: x["weekday"] == int(weekday), teacher_schedule))
    teacher_schedule = list(filter(lambda x: int(week_number) in x["lesson"]["weeks"], teacher_schedule))
    teacher_schedule = sorted(teacher_schedule, key=lambda x: x["lesson"]["time_start"])
    teacher_schedule = sorted(teacher_schedule, key=lambda x: x["lesson"]["time_end"])
    teacher_schedule = sorted(teacher_schedule, key=lambda x: x["weekday"])
    return teacher_schedule


def remove_duplicates_merge_groups_with_same_lesson(teacher_schedule):
    remove_index = []
    for i in range(len(teacher_schedule)):
        for j in range(i + 1, len(teacher_schedule)):
            if (
                    teacher_schedule[i]["weekday"] == teacher_schedule[j]["weekday"]
                    and teacher_schedule[i]["lesson"]["name"] == teacher_schedule[j]["lesson"]["name"]
                    and teacher_schedule[i]["lesson"]["weeks"] == teacher_schedule[j]["lesson"]["weeks"]
                    and teacher_schedule[i]["lesson"]["time_start"] == teacher_schedule[j]["lesson"]["time_start"]
            ):
                teacher_schedule[i]["group"] += ", " + teacher_schedule[j]["group"]
                remove_index.append(j)

    remove_index = set(remove_index)
    for i in sorted(remove_index, reverse=True):
        del teacher_schedule[i]
    return teacher_schedule


def merge_weeks_numbers(teacher_schedule):
    for i in range(len(teacher_schedule)):
        weeks = teacher_schedule[i]["lesson"]["weeks"]
        if weeks == list(range(1, 18)):
            weeks = "все"
        elif weeks == list(range(2, 18, 2)):
            weeks = "по чётным"
        elif weeks == list(range(1, 18, 2)):
            weeks = "по нечётным"
        else:
            weeks = ", ".join(str(week) for week in weeks)
        teacher_schedule[i]["lesson"]["weeks"] = weeks
    return teacher_schedule


def format_outputs(schedules):
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
    for schedule in schedules:
        room = ", ".join(schedule["lesson"]["rooms"])
        teachers = schedule["lesson"]["teachers"]
        weekday = WEEKDAYS[schedule["weekday"]]
        teachers = ", ".join(decode_teachers(teachers))

        text += f'📝 Пара № {schedule["lesson_number"] + 1} в ⏰ {schedule["lesson"]["time_start"]} – {schedule["lesson"]["time_end"]}\n'
        text += f'📝 {schedule["lesson"]["name"]}\n'
        text += f'👥 Группы: {schedule["group"]}\n'
        text += f'📚 Тип: {schedule["lesson"]["types"]}\n'
        text += f"👨🏻‍🏫 Преподаватели: {teachers}\n"
        text += f"🏫 Аудитории: {room}\n"
        text += f'📅 Недели: {schedule["lesson"]["weeks"]}\n'
        text += f"📆 День недели: {weekday}\n\n"
        blocks.append(text)
        text = ""

    return blocks


def telegram_delivery_optimisation(blocks: list, update: Update, context: CallbackContext):
    teacher = context.user_data["teacher"]
    context.user_data["schedule"] = fetch_schedule_by_name(context.user_data["teacher"])
    schedule = context.user_data["schedule"]
    week = context.user_data["week"]
    teacher_workdays = construct_teacher_workdays(teacher, week, schedule)

    chunk = ""
    first = True
    for block in blocks:
        if len(chunk) + len(block) <= 4096:
            chunk += block
        else:
            if first:
                if update.callback_query.inline_message_id:
                    update.callback_query.answer(
                        text="Слишком длинное расписание, пожалуйста, воспользуйтесь личными сообщениями бота или "
                             "выберите конкретный день недели",
                        show_alert=True)
                    break
                update.callback_query.edit_message_text(chunk)
                first = False
            else:
                context.bot.send_message(chat_id=update.effective_chat.id, text=chunk)
            chunk = block

    if chunk:
        if first:
            update.callback_query.edit_message_text(chunk, reply_markup=teacher_workdays)
        else:
            context.bot.send_message(chat_id=update.effective_chat.id, text=chunk, reply_markup=teacher_workdays)

    return GETDAY


# def got_back_handler(update: Update, context: CallbackContext):
#     query = update.callback_query.data
#     if query == "back":
#         # Заново получаем расписание, т.к. список недель был заменён на строки "По чётным", "По нечётным" и т.д.
#         context.user_data["schedule"] = fetch_schedule_by_name(context.user_data["teacher"])
#
#         return send_week_selector(update, context)


def inlinequery(update: Update, context: CallbackContext):
    """
    Обработчик инлайн запросов
    Создает Inline отображение
    """
    query = update.inline_query.query
    if not query:
        return
    if len(query) < 3:
        return
    lazy_logger.info(json.dumps(
        {"type": "query",
         "queryId": update.inline_query.id,
         "query": query.lower(),
         **update.inline_query.from_user.to_dict()}, ensure_ascii=False))
    query = query.title()
    if " " not in query:
        query += " "
    teacher_schedule = fetch_schedule_by_name(query)
    if teacher_schedule is None:
        return
    surnames = check_same_surnames(teacher_schedule, query)
    if len(surnames) == 0:
        return
    inline_results = []
    decoded_surnames = decode_teachers(surnames)
    userid = str(update.inline_query.from_user.id)
    for surname, decoded_surname in zip(surnames, decoded_surnames):
        inline_results.append(InlineQueryResultArticle(
            id=surname,
            title=decoded_surname,
            description="Нажми, чтобы посмотреть расписание",
            input_message_content=InputTextMessageContent(
                message_text=f"Выбран преподаватель: {decoded_surname}!"
            ),
            reply_markup=construct_weeks_markup(),

        ))
    update.inline_query.answer(inline_results, cache_time=10, is_personal=True)


def answer_inline_handler(update: Update, context: CallbackContext):
    """
    В случае отработки события ChosenInlineHandler запоминает выбранного преподавателя
    и выставляет текущий шаг Inline запроса на ask_day
    """
    if update.chosen_inline_result is not None:
        context.user_data["teacher"] = update.chosen_inline_result.result_id
        context.user_data["inline_step"] = EInlineStep.ask_week
        context.user_data["inline_message_id"] = update.chosen_inline_result.inline_message_id
        return


def inline_dispatcher(update: Update, context: CallbackContext):
    """
    Обработка вызовов в чатах на основании Callback вызова
    """
    if "inline_step" not in context.user_data:
        deny_inline_usage(update)
        return
    # Если Id сообщения в котором мы нажимаем на кнопки не совпадает с тем, что было сохранено в контексте при вызове
    # меню, то отказываем в обработке
    if update.callback_query.inline_message_id and update.callback_query.inline_message_id != context.user_data[
        "inline_message_id"]:
        deny_inline_usage(update)
        return
    status = context.user_data["inline_step"]
    if status == EInlineStep.completed or status == EInlineStep.ask_teacher:
        deny_inline_usage(update)
        return
    if status == EInlineStep.ask_week:
        context.user_data['available_teachers'] = None
        context.user_data["schedule"] = fetch_schedule_by_name(context.user_data["teacher"])
        target = got_week_handler(update, context)
        if target == GETDAY:
            context.user_data["inline_step"] = EInlineStep.ask_day
        elif target == BACK:
            context.user_data["inline_step"] = EInlineStep.ask_day
    if status == EInlineStep.ask_day:
        target = got_day_handler(update, context)
        if target == GETWEEK:
            context.user_data["schedule"] = fetch_schedule_by_name(context.user_data["teacher"])
            context.user_data["inline_step"] = EInlineStep.ask_week
        elif target == BACK:
            context.user_data["inline_step"] = EInlineStep.ask_day
        return


def deny_inline_usage(update: Update):
    """
    Показывает предупреждение пользователю, если он не может использовать имеющийся Inline вызов
    """
    update.callback_query.answer(text="Вы не можете использовать это меню, т.к. оно не относится к вашему запросу",
                                 show_alert=True)
    return


def main():
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start, run_async=True),
            MessageHandler(Filters.text & ~Filters.command, got_name_handler, run_async=True),
        ],
        states={
            GETNAME: [MessageHandler(Filters.text & ~Filters.command, got_name_handler, run_async=True)],
            GETDAY: [CallbackQueryHandler(got_day_handler, run_async=True)],
            GETWEEK: [CallbackQueryHandler(got_week_handler, run_async=True)],
            TEACHER_CLARIFY: [CallbackQueryHandler(got_teacher_clarification_handler, run_async=True)],
            # BACK: [CallbackQueryHandler(got_back_handler, run_async=True)],
        },
        fallbacks=[
            CommandHandler("start", start, run_async=True),
            MessageHandler(Filters.text & ~Filters.command, got_name_handler, run_async=True),
        ],
    )

    dispatcher.add_handler(conv_handler)

    dispatcher.add_handler(InlineQueryHandler(inlinequery, run_async=True))
    dispatcher.add_handler(ChosenInlineResultHandler(answer_inline_handler, run_async=True))
    dispatcher.add_handler(CallbackQueryHandler(inline_dispatcher, run_async=True))

    dispatcher.add_handler(CommandHandler("help", start, run_async=True))
    updater.start_polling()


if __name__ == "__main__":
    main()
