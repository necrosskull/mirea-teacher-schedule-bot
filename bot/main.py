import datetime
import logging
from uuid import uuid4
import requests
from InlineStep import EInlineStep
import ImportantDays
from config import TELEGRAM_TOKEN
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, InlineQueryResultArticle, InputTextMessageContent
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
updater = Updater(TELEGRAM_TOKEN, use_context=True)
dispatcher = updater.dispatcher

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

GETNAME, GETDAY, GETWEEK, TEACHER_CLARIFY = range(4)

WEEKDAYS = {
    1: "Понедельник",
    2: "Вторник",
    3: "Среда",
    4: "Четверг",
    5: "Пятница",
    6: "Суббота",
}

WEEKDAYS_KEYBOARD_MARKUP = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(WEEKDAYS[1], callback_data="понедельник"),
            InlineKeyboardButton(WEEKDAYS[2], callback_data="вторник"),
            InlineKeyboardButton(WEEKDAYS[3], callback_data="среда"),
        ],
        [
            InlineKeyboardButton(WEEKDAYS[4], callback_data="четверг"),
            InlineKeyboardButton(WEEKDAYS[5], callback_data="пятница"),
            InlineKeyboardButton(WEEKDAYS[6], callback_data="суббота"),
        ],
        [
            InlineKeyboardButton("Сегодня",callback_data="today"),
            InlineKeyboardButton("Завтра", callback_data="tomorrow")
        ],
        [
            InlineKeyboardButton("Назад", callback_data="back"),
        ],
    ]
)


def fetch_schedule_by_name(teacher_name):
    url = f"https://schedule.mirea.ninja/api/schedule/teacher/{teacher_name}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None


def start(update: Update, context: CallbackContext) -> int:
    context.bot.send_message(chat_id=update.effective_chat.id, text="Введите фамилию преподавателя")

    # Переключаемся в состояние GETNAME (ожидание ввода фамилии)
    return GETNAME


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
            truncated = str(teacher).replace(" ",'')
            truncated_surname = surname.replace(' ','')
            if truncated not in str(surnames).replace(' ','') and truncated_surname in truncated:
                surnames.append(teacher)
    return surnames
def inlinequery(update: Update, context: CallbackContext):
    """
    Обработчик инлайн запросов
    Создает Inline отображение
    """
    query = update.inline_query.query
    if not query:
        return
    query = query.title()
    if " " not in query:
        query+=" "
    teacher_schedule = fetch_schedule_by_name(query)
    if teacher_schedule is None:
        return
    surnames = check_same_surnames(teacher_schedule, query)
    if len(surnames) == 0:
        return
    inline_results = []
    userid = str(update.inline_query.from_user.id)
    for surname in surnames:
        inline_results.append(InlineQueryResultArticle(
            id = surname,
            title=surname,
            description="Нажми, чтобы посмотреть расписание",
            input_message_content=InputTextMessageContent(
                message_text=f"Выбран преподаватель: {surname}!"
            ),
            reply_markup=WEEKDAYS_KEYBOARD_MARKUP

        ))
    update.inline_query.answer(inline_results,cache_time=10,is_personal=True)

def answer_inline_handler(update: Update, context:CallbackContext):
    """
    В случае отработки события ChosenInlineHandler запоминает выбранного преподавателя
    и выставляет текущий шаг Inline запроса на ask_day
    """
    if update.chosen_inline_result is not None:
        context.user_data["teacher"] = update.chosen_inline_result.result_id
        context.user_data["inline_step"] =EInlineStep.ask_day
        return

def inline_dispatcher(update: Update, context: CallbackContext):
    """
    Обработка вызовов в чатах на основании Callback вызова
    """
    if "inline_step" not in context.user_data:
        deny_inline_usage(update)
        return
    status = context.user_data["inline_step"]
    if status==EInlineStep.completed or status==EInlineStep.ask_teacher:
        deny_inline_usage(update)
        return
    if status==EInlineStep.ask_day:
        context.user_data["teacher_schedule"] = fetch_schedule_by_name(context.user_data["teacher"])
        target = get_day(update,context)
        if target==GETWEEK:
            context.user_data["inline_step"]=EInlineStep.ask_week
        elif target==GETDAY or target==ConversationHandler.END:
            return
        else:
            update.callback_query.edit_message_text("Вызовите бота снова, указав нужного преподавателя")
            context.user_data["inline_step"]=EInlineStep.ask_teacher
        return
    if status==EInlineStep.ask_week:
        target = week_selected_handler(update,context)
        if target==GETDAY:
            context.user_data["inline_step"]=EInlineStep.ask_day
        elif target != GETWEEK:
            context.user_data["inline_step"]=EInlineStep.completed
        return

def deny_inline_usage(update: Update):
    """
    Показывает предупреждение пользователю, если он не может использовать имеющийся Inline вызов
    """
    update.callback_query.answer(text="Вы не можете использовать это меню, т.к. его вызвал другой человек",show_alert=True)
    return

def teacher_clarify(update: Update, context:CallbackContext)->int:
    """
    Обработчик нажатия кнопки с ФИО преподавателя
    :param update: объект из telegram.update
    :param context: контекст callback события
    :return: код дальнейшего шага (GETDAY || GETNAME)
    """
    chosed_teacher = update.callback_query.data
    query = update.callback_query
    if chosed_teacher=="back":
        query.edit_message_text("Введите фамилию преподавателя")
        return GETNAME
    context.user_data["teacher"]=chosed_teacher.split('.')[0]
    query.edit_message_text(
        text="Выберите день недели",
        reply_markup=WEEKDAYS_KEYBOARD_MARKUP,
    )
    return GETDAY


def prepare_teacher_markup(teachers):
    """
    Конструирует клавиатуру доступных преподавателей однофамильцев
    :param teachers: лист преподавателей
    """
    btns = []
    for teacher in teachers:
        btns = btns + [[InlineKeyboardButton(teacher, callback_data=teacher)]]
    btns= btns + [[(InlineKeyboardButton("Назад", callback_data="back"))]]
    TEACHER_CLARIFY_MARKUP = InlineKeyboardMarkup(btns)
    return TEACHER_CLARIFY_MARKUP


def get_name(update: Update, context: CallbackContext) -> int:
    teacher = update.message.text
    teacher = teacher.title()
    if " " not in teacher:
        teacher+=" "
    # Устанавливаем расписание преподавателей в контексте для избежания повторных запросов
    teacher_schedule = fetch_schedule_by_name(teacher)

    if teacher_schedule is None:
        update.message.reply_text("Преподаватель не найден\nПопробуйте еще раз")
        return GETNAME

    context.user_data["teacher_schedule"] = teacher_schedule

    # Определяем наличие однофамильцев, при их наличии предоставляем выбор
    # иначе сохраняем в контексте фамилию преподавателя.
    # `user_data` - это словарь, который можно использовать для хранения любых данных.
    # Для каждого обновления от одного и того же пользователя он будет одинаковым.
    context.user_data["available_teachers"] = check_same_surnames(teacher_schedule,teacher)
    if len(context.user_data["available_teachers"])>1:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Выберите преподавателя",
            reply_markup=prepare_teacher_markup(context.user_data["available_teachers"]),
        )
        return TEACHER_CLARIFY
    elif len(context.user_data["available_teachers"])==0:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Ошибка при определении ФИО. Повторите ввод изменив запрос, например введя фамилию вместо ФИО"
        )
        return GETNAME
    else:
        context.user_data["teacher"]=context.user_data["available_teachers"][0]
    # Устанавливаем фамилию преподавателя в контексте.
    # `user_data` - это словарь, который можно использовать для хранения любых данных.
    # Для каждого обновления от одного и того же пользователя он будет одинаковым.

    # Отправляем клавиатуру с выбором дня недели
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Введите день недели",
        reply_markup=WEEKDAYS_KEYBOARD_MARKUP,
    )

    # Устанавливаем состояние в GETDAY (ожидание ввода дня недели)
    return GETDAY

def construct_weeks_markup():
    """
    Создает KeyboardMarkup со списком недель, а также подставляет эмодзи
    если текущий день соответствует некоторой памятной дате+-интервал
    """
    req =  requests.get("https://schedule.mirea.ninja/api/schedule/current_week").json()
    current_week = req["week"]
    week_indicator="●"
    today = datetime.date.today()
    for day in ImportantDays.important_days:
        if abs((day[ImportantDays.DATE]-today).days)<=day[ImportantDays.INTERVAL]:
            week_indicator=day[ImportantDays.SIGN]

    reply_mark = InlineKeyboardMarkup([])
    button_list = []
    for i in range(1,18):
        tmp_sign = ""
        if current_week==i:
            tmp_sign=week_indicator
        button_list.append(InlineKeyboardButton(text=f"{tmp_sign}{i}{tmp_sign}", callback_data=i))
        if i%4==0 or i==17:
            reply_mark.inline_keyboard.append(button_list)
            button_list=[]
    backspace = []
    backspace.append(InlineKeyboardButton(text="Назад",callback_data="back"))
    reply_mark.inline_keyboard.append(backspace)
    return reply_mark


def get_day(update: Update, context: CallbackContext):
    req = requests.get("https://schedule.mirea.ninja/api/schedule/current_week").json()
    cur_week = req["week"]
    context.user_data["week"] = cur_week
    WEEKS_KEYBOARD_MARKUP=construct_weeks_markup()
    context.user_data["week_keyboard"] = WEEKS_KEYBOARD_MARKUP
    day = update.callback_query.data
    query = update.callback_query
    for key, value in WEEKDAYS.items():
        if day == value.lower():
            # Устанавливаем день недели в контексте
            context.user_data["day"] = key

            # Отправляем клавиатуру с выбором номера недели
            query.edit_message_text(
                text="Выберите неделю\nТекущая неделя: " + str(cur_week),
                reply_markup=WEEKS_KEYBOARD_MARKUP,
            )
            # Устанавливаем состояние в GETWEEK (ожидание ввода номера недели)
            return GETWEEK

    if day == "back":
        query.edit_message_text(
            text="Введите фамилию преподавателя",
        )
        return GETNAME
    elif day=="today" or day=="tomorrow":
        today = datetime.date.today().weekday()
        week = cur_week
        if day=="tomorrow":
            if today==6:
                week+=1 #Корректировка недели, в случае если происходит переход недели
            today=(datetime.date.today()+datetime.timedelta(days=1)).weekday()
        if today==6:
            update.callback_query.answer("В выбранный день пар нет")
            return GETDAY
        today+=1 #Корректировка дня с 0=пн на 1=пн
        context.user_data["week"]=week
        context.user_data["day"]=today
        return show_result(update,context)
    else:
        query.edit_message_text(
            text="Неверный ввод",
        )
        return GETDAY


def week_selected_handler(update: Update, context: CallbackContext):
    """
    Обработчик нажатия на кнопку недели.
    """
    selected = update.callback_query.data
    if selected=="back":
        update.callback_query.edit_message_text(
            text="Введите день недели",
            reply_markup=WEEKDAYS_KEYBOARD_MARKUP
        )
        return GETDAY
    selected_week = int(selected)
    context.user_data["week"] = selected_week
    return show_result(update,context)

def show_result(update: Update, context: CallbackContext):
    """
    Выводит результат пользователю.
    В user_data["week"] и user_data["day"] должны быть заполнены перед вызовом!
    """
    week = context.user_data["week"]
    weekday = context.user_data["day"]
    schedule_data = context.user_data["teacher_schedule"]
    teacher_surname = context.user_data["teacher"]

    parsed_schedule = parse(schedule_data, weekday, week, teacher_surname)
    parsed_schedule = remove_duplicates_merge_groups_with_same_lesson(parsed_schedule)
    parsed_schedule = merge_weeks_numbers(parsed_schedule)

    is_having_schedule = have_teacher_lessons(parsed_schedule, update, context)

    if not is_having_schedule:
        return GETDAY

    # Отправляем расписание преподавателя
    text = format_outputs(parsed_schedule)

    return for_telegram(text, update)

def parse(teacher_schedule, weekday, week_number, teacher):
    teacher_schedule = teacher_schedule["schedules"]
    teacher_schedule = list(filter(lambda x: teacher in str(x["lesson"]["teachers"]), teacher_schedule))
    teacher_schedule = sorted(teacher_schedule, key=lambda x: x["weekday"])
    teacher_schedule = sorted(teacher_schedule, key=lambda x: x["group"])
    teacher_schedule = list(filter(lambda x: x["weekday"] == int(weekday), teacher_schedule))
    teacher_schedule = list(filter(lambda x: int(week_number) in x["lesson"]["weeks"], teacher_schedule))
    teacher_schedule = sorted(teacher_schedule, key=lambda x: x["lesson"]["time_start"])
    teacher_schedule = sorted(teacher_schedule, key=lambda x: x["lesson"]["time_end"])

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


def have_teacher_lessons(teacher_schedule, update: Update, context: CallbackContext):
    if not teacher_schedule:
        query = update.callback_query

        #Костыль
        #Исправление исключения отправки точно такого-же сообщения
        query.edit_message_text(
            text="Обработка...",
            reply_markup=WEEKDAYS_KEYBOARD_MARKUP,
            )

        query.edit_message_text(
            text="В этот день нет пар \n\nВведите день недели",
            reply_markup=WEEKDAYS_KEYBOARD_MARKUP,
            )
        return False

    return True


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

    for schedule in schedules:
        room = ", ".join(schedule["lesson"]["rooms"])
        teachers = ", ".join(schedule["lesson"]["teachers"])
        weekday = WEEKDAYS[schedule["weekday"]]

        text += f'📝 Пара № {schedule["lesson_number"] + 1} в ⏰ {schedule["lesson"]["time_start"]}–{schedule["lesson"]["time_end"]}\n'
        text += f'📝 {schedule["lesson"]["name"]}\n'
        text += f'👥 Группы: {schedule["group"]}\n'
        text += f'📚 Тип: {schedule["lesson"]["types"]}\n'
        text += f"👨🏻‍🏫 Преподаватели: {teachers}\n"
        text += f"🏫 Аудитории: {room}\n"
        text += f'📅 Недели: {schedule["lesson"]["weeks"]}\n'
        text += f"📆 День недели: {weekday}\n\n"

    return text


def for_telegram(text, update: Update):
    text_len = len(text)
    query = update.callback_query
    for i in range(0, text_len, 4096):
        query.edit_message_text(text[i : i + 4096])
    return ConversationHandler.END


def main():
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start, run_async=True),
            MessageHandler(Filters.text & ~Filters.command, get_name, run_async=True),
        ],
        states={
            GETNAME: [MessageHandler(Filters.text & ~Filters.command, get_name, run_async=True)],
            GETDAY: [CallbackQueryHandler(get_day, run_async=True)],
            GETWEEK: [CallbackQueryHandler(week_selected_handler, run_async=True)],
            TEACHER_CLARIFY: [CallbackQueryHandler(teacher_clarify, run_async=True)],
        },
        fallbacks=[
            CommandHandler("start", start, run_async=True),
            MessageHandler(Filters.text & ~Filters.command, get_name, run_async=True),
        ],
    )

    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(InlineQueryHandler(inlinequery, run_async=True))
    dispatcher.add_handler(ChosenInlineResultHandler(answer_inline_handler, run_async=True))
    dispatcher.add_handler(CallbackQueryHandler(inline_dispatcher, run_async=True))
    updater.start_polling()


if __name__ == "__main__":
    main()
