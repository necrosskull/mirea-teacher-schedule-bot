import logging
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters, ConversationHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
import requests
import config
updater = Updater(config.token, use_context=True)
dispatcher = updater.dispatcher

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',level=logging.INFO)

GETNAME, GETDAY, GETWEEK = range(3)

def start(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Введиите фамилию преподавателя")

def get_name(update: Update, context: CallbackContext):
    global teacher
    teacher = update.message.text

    if len(teacher) < 4:
        update.message.reply_text('Фамилия должна быть больше 3 символов')
        return GETNAME

    url = f"https://schedule.mirea.ninja/api/schedule/teacher/{teacher}"
    response = requests.get(url)
    teacher_schedule = response.json() if response.status_code == 200 else None

    if teacher_schedule is None:
        update.message.reply_text('Преподаватель не найден')
        update.message.reply_text('Попробуйте еще раз')
        return GETNAME

    context.bot.send_message(chat_id=update.effective_chat.id, text="Введите день недели", reply_markup=ReplyKeyboardMarkup(
        [['Понедельник', 'Вторник'], ['Среда', 'Четверг'], ['Пятница', 'Суббота'], ['Назад']], resize_keyboard=True, one_time_keyboard=True))
    return GETDAY

def get_day(update: Update, context: CallbackContext):
    global day
    day = update.message.text.lower()

    if day == 'назад':
        context.bot.send_message(chat_id=update.effective_chat.id, text="Введите фамилию преподавателя", reply_markup=ReplyKeyboardRemove())
        return GETNAME

    if day in ['понедельник']:
        day = '1'
    elif day in ['вторник']:
        day = '2'
    elif day in ['среда']:
        day = '3'
    elif day in ['четверг']:
        day = '4'
    elif day in ['пятница']:
        day = '5'
    elif day in ['суббота']:
        day = '6'
    elif day in ['воскресенье']:
        day = '7'

    context.bot.send_message(chat_id=update.effective_chat.id, text="Выберите неделю", reply_markup=ReplyKeyboardMarkup(
        [['1', '2', '3','4'], ['5', '6', '7','8'], ['9', '10', '11','12'],['13', '14', '15','16','17'] , ['Назад']], resize_keyboard=True, one_time_keyboard=True))

    return GETWEEK

def get_week(update: Update, context: CallbackContext):
    global weeknum
    weeknum = update.message.text.lower()

    if weeknum == 'назад':
        context.bot.send_message(chat_id=update.effective_chat.id, text="Введите день недели",
                                 reply_markup=ReplyKeyboardMarkup(
                                     [['Понедельник', 'Вторник'], ['Среда', 'Четверг'], ['Пятница', 'Суббота'],
                                      ['Назад']], resize_keyboard=True, one_time_keyboard=True))
        return GETDAY

    if weeknum.isdigit() == False:
        update.message.reply_text('Неверный ввод', reply_markup=ReplyKeyboardRemove())
        context.bot.send_message(chat_id=update.effective_chat.id, text="Выберите неделю",
                                 reply_markup=ReplyKeyboardMarkup(
                                     [['1', '2', '3', '4'], ['5', '6', '7', '8'], ['9', '10', '11', '12'],
                                      ['13', '14', '15', '16', '17'], ['Назад']], resize_keyboard=True,
                                     one_time_keyboard=True))
        return GETWEEK

    url = f"https://schedule.mirea.ninja/api/schedule/teacher/{teacher}"
    response = requests.get(url)
    teacher_schedule = response.json() if response.status_code == 200 else None

    if teacher_schedule:
        text = ""

        weekdays = {
            1: "Понедельник",
            2: "Вторник",
            3: "Среда",
            4: "Четверг",
            5: "Пятница",
            6: "Суббота",
        }

        teacher_schedule = teacher_schedule["schedules"]
        teacher_schedule = sorted(teacher_schedule, key=lambda x: x["weekday"])
        teacher_schedule = sorted(teacher_schedule, key=lambda x: x["group"])
        teacher_schedule = list(filter(lambda x: x["weekday"] == int(day), teacher_schedule))
        teacher_schedule = list(filter(lambda x: int(weeknum) in x["lesson"]["weeks"], teacher_schedule))
        teacher_schedule = sorted(teacher_schedule, key=lambda x: x["lesson"]["time_start"])
        teacher_schedule = sorted(teacher_schedule, key=lambda x: x["lesson"]["time_end"])

        remove_index = []
        for i in range(len(teacher_schedule)):
            for j in range(i + 1, len(teacher_schedule)):
                if (
                        teacher_schedule[i]["weekday"] == teacher_schedule[j]["weekday"]
                        and teacher_schedule[i]["lesson"]["name"]
                        == teacher_schedule[j]["lesson"]["name"]
                        and teacher_schedule[i]["lesson"]["weeks"]
                        == teacher_schedule[j]["lesson"]["weeks"]
                        and teacher_schedule[i]["lesson"]["time_start"]
                        == teacher_schedule[j]["lesson"]["time_start"]

                ):
                    teacher_schedule[i]["group"] += ", " + teacher_schedule[j]["group"]
                    remove_index.append(j)

        remove_index = set(remove_index)
        for i in sorted(remove_index, reverse=True):
            del teacher_schedule[i]

        if not teacher_schedule:
            update.message.reply_text('В этот день нет пар', reply_markup=ReplyKeyboardRemove())
            context.bot.send_message(chat_id=update.effective_chat.id, text="Введите день недели",
                                     reply_markup=ReplyKeyboardMarkup(
                                         [['Понедельник', 'Вторник'], ['Среда', 'Четверг'], ['Пятница', 'Суббота'],
                                          ['Назад']], resize_keyboard=True, one_time_keyboard=True))
            return GETDAY

        i = 0
        while i < len(teacher_schedule) - 1:
            if (
                    teacher_schedule[i]["weekday"] == teacher_schedule[i + 1]["weekday"]
                    and teacher_schedule[i]["group"] == teacher_schedule[i + 1]["group"]
                    and teacher_schedule[i]["lesson"]["time_start"]
                    == teacher_schedule[i + 1]["lesson"]["time_start"]
            ):
                teacher_schedule[i]["lesson"]["weeks"] += teacher_schedule[i + 1]["lesson"][
                    "weeks"
                ]
                teacher_schedule[i]["lesson"]["weeks"] = sorted(
                    teacher_schedule[i]["lesson"]["weeks"]
                )
                teacher_schedule.pop(i + 1)
            else:
                i += 1

        for schedule in teacher_schedule:

            if schedule["lesson"]["weeks"] == list(range(1, 18)):
                weeks = "все"
            elif schedule["lesson"]["weeks"] == list(range(2, 18, 2)):
                weeks = "по чётным"
            elif schedule["lesson"]["weeks"] == list(range(1, 18, 2)):
                weeks = "по нечётным"
            else:
                weeks = ", ".join(str(week) for week in schedule["lesson"]["weeks"])

            room = ", ".join(schedule["lesson"]["rooms"])
            teachers = ", ".join(schedule["lesson"]["teachers"])
            weekday = weekdays[schedule["weekday"]]
            text += f'📝 Пара № {schedule["lesson_number"] + 1} в ⏰ {schedule["lesson"]["time_start"]}–{schedule["lesson"]["time_end"]}\n'
            text += f'📝 {schedule["lesson"]["name"]}\n'
            text += f'👥 Группы: {schedule["group"]}\n'
            text += f'📚 Тип: {schedule["lesson"]["types"]}\n'
            text += f"👨🏻‍🏫 Преподаватели: {teachers}\n"
            text += f"🏫 Аудитории: {room}\n"
            text += f"📅 Недели: {weeks}\n"
            text += f"📆 День недели: {weekday}\n\n"

        text_len = len(text)

        for i in range(0, text_len, 4096):
            update.message.reply_text(text[i : i + 4096], reply_markup=ReplyKeyboardRemove())
    else:
        update.message.reply_text('Преподаватель не найден')
        return context.bot.send_message(chat_id=update.effective_chat.id, text="Введите фамилию преподавателя")
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[MessageHandler(Filters.text, get_name)],
    states={
        GETNAME: [MessageHandler(Filters.text, get_name)],
        GETDAY: [MessageHandler(Filters.text, get_day)],
        GETWEEK: [MessageHandler(Filters.text, get_week)],
    },
    fallbacks=[MessageHandler(Filters.text, get_week)]
)

start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

dispatcher.add_handler(conv_handler)

updater.start_polling()
