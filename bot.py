import telebot
import requests
from telebot import types
import config
bot = telebot.TeleBot(config.token)

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, 'Введите фамилию преподавателя')

@bot.message_handler(content_types=['text'])


def get_name(message):
    global teacher
    teacher = message.text
    if len(teacher) < 4:
        bot.reply_to(message, 'Фамилия слишком короткая')
        return
    url = f"https://schedule.mirea.ninja/api/schedule/teacher/{teacher}"
    response = requests.get(url)
    teacher_schedule = response.json() if response.status_code == 200 else None


    if teacher_schedule is None:
        bot.reply_to(message, 'Преподаватель не найден')
        return bot.send_message(message.chat.id, 'Введите фамилию преподавателя')

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    item1 = types.KeyboardButton("Понедельник")
    item2 = types.KeyboardButton("Вторник")
    item3 = types.KeyboardButton("Среда")
    item4 = types.KeyboardButton("Четверг")
    item5 = types.KeyboardButton("Пятница")
    item6 = types.KeyboardButton("Суббота")
    item7 = types.KeyboardButton("Назад")
    markup.add(item1, item2, item3, item4, item5, item6 ,item7)

    bot.send_message(message.chat.id, 'Выберите день недели', reply_markup=markup)



    bot.register_next_step_handler(message, get_day)

def get_day(message):
    global day
    day = message.text

    if day == 'пн' or day == 'Пн' or day == 'понедельник' or day == 'Понедельник' or day == '1':
        day = '1'
    elif day == 'вт' or day == 'Вт' or day == 'вторник' or day == 'Вторник' or day == '2':
        day = '2'
    elif day == 'ср' or day == 'Ср' or day == 'среда' or day == 'Среда' or day == '3':
        day = '3'
    elif day == 'чт' or day == 'Чт' or day == 'четверг' or day == 'Четверг' or day == '4':
        day = '4'
    elif day == 'пт' or day == 'Пт' or day == 'пятница' or day == 'Пятница' or day == '5':
        day = '5'
    elif day == 'сб' or day == 'Сб' or day == 'суббота' or day == 'Суббота' or day == '6':
        day = '6'
    elif day == 'назад' or day == 'Назад':
        return bot.send_message(message.chat.id, 'Введите фамилию преподавателя',reply_markup = types.ReplyKeyboardRemove())
    else:
        bot.reply_to(message, 'Неверный ввод',reply_markup = types.ReplyKeyboardRemove())
        return bot.send_message(message.chat.id, 'Введите фамилию преподавателя')
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=4)
    item1 = types.KeyboardButton("1")
    item2 = types.KeyboardButton("2")
    item3 = types.KeyboardButton("3")
    item4 = types.KeyboardButton("4")
    item5 = types.KeyboardButton("5")
    item6 = types.KeyboardButton("6")
    item7 = types.KeyboardButton("7")
    item8 = types.KeyboardButton("8")
    item9 = types.KeyboardButton("9")
    item10 = types.KeyboardButton("10")
    item11 = types.KeyboardButton("11")
    item12 = types.KeyboardButton("12")
    item13 = types.KeyboardButton("13")
    item14 = types.KeyboardButton("14")
    item15 = types.KeyboardButton("15")
    item16 = types.KeyboardButton("16")
    item17 = types.KeyboardButton("17")
    item18 = types.KeyboardButton("Отмена")


    markup.add(item1, item2, item3, item4, item5, item6, item7, item8, item9, item10, item11, item12, item13, item14, item15, item16 ,item17 ,item18)

    bot.send_message(message.chat.id, 'Выберите неделю', reply_markup=markup)


    bot.register_next_step_handler(message, get_week)



def get_week(message):
    global weeknum
    weeknum = message.text
    if weeknum == 'отмена' or weeknum == 'Отмена':
        return bot.send_message(message.chat.id, 'Введите фамилию преподавателя',reply_markup = types.ReplyKeyboardRemove())
    if weeknum.isdigit() == False:
        bot.reply_to(message, 'Номер недели должен быть числом')
        return bot.send_message(message.chat.id, 'Введите фамилию преподавателя')

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
            bot.send_message(message.from_user.id, 'В этот день у преподавателя нет пар',reply_markup = types.ReplyKeyboardRemove())
            return bot.send_message(message.chat.id, 'Введите фамилию преподавателя')

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
            bot.send_message(message.chat.id, text[i: i + 4096],reply_markup = types.ReplyKeyboardRemove())
    else:
        bot.send_message(message.chat.id, 'Такого препода нет')


bot.polling()
