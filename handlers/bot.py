import aiogram
import requests
from configs import config
from inline import inline_buttons
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext

bot = aiogram.Bot(token=config.TOKEN)
storage = MemoryStorage()
dp = aiogram.Dispatcher(bot, storage=storage)


# ToDo: resize_keyboard=True markup

class StatesGroup(StatesGroup):
    name = State()
    day = State()
    week = State()


@dp.message_handler(commands=['start'], state='*')
async def start_message(message: aiogram.types.Message):
    # Отправка сообщения: Введите фамилию преподавателя
    await message.answer(text='Введите фамилию преподавателя')


@dp.message_handler(lambda message: message.text not in "/start")
async def get_name(message: aiogram.types.Message) -> None:
    # Получение фамилии преподавателя
    global teacher
    teacher = message.text

    url = f"https://schedule.mirea.ninja/api/schedule/teacher/{teacher}"
    response = requests.get(url)
    teacher_schedule = response.json() if response.status_code == 200 else None
    if teacher_schedule is None:
        await message.reply(message, 'Преподаватель не найден')
        return

    try:
        markup = InlineKeyboardMarkup(row_width=4)
        item1 = InlineKeyboardButton("Понедельник", callback_data='monday')
        item2 = InlineKeyboardButton("Вторник", callback_data='tuesday')
        item3 = InlineKeyboardButton("Среда", callback_data='wednesday')
        item4 = InlineKeyboardButton("Четверг", callback_data='thursday')
        item5 = InlineKeyboardButton("Пятница", callback_data='friday')
        item6 = InlineKeyboardButton("Суббота", callback_data='saturday')
        item7 = InlineKeyboardButton("Назад", callback_data='back')
        markup.add(item1, item2, item3, item4, item5, item6, item7)
    except Exception as e:
        print(f"Error: {e}, \n in inline_buttons")

    # отправка сообщения пользователю диспетчером
    await message.answer('Выберите день недели', reply_markup=markup)
    # Ожидание ответа от пользователя
    await StatesGroup.day.set()


@dp.callback_query_handler(state=StatesGroup.day)
async def get_day(message: aiogram.types.CallbackQuery, state: FSMContext) -> None:
    message.answer('Вы выбрали'+message.callback_query.data)
    global day
    day = aiogram.types.CallbackQuery.data.lower()
    print(day)
    # day = message.text.lower()
    if day in ['monday']:
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
    elif day == 'Назад':
        return start_message(message)  # ToDo: Не работает
    else:
        message.reply(message, 'Неверный ввод', reply_markup=aiogram.types.ReplyKeyboardRemove())
        return

    markup = InlineKeyboardMarkup(row_width=4)
    item1 = InlineKeyboardButton("1", callback_data='1')
    item2 = InlineKeyboardButton("2", callback_data='2')
    item3 = InlineKeyboardButton("3", callback_data='3')
    item4 = InlineKeyboardButton("4", callback_data='4')
    item5 = InlineKeyboardButton("5", callback_data='5')
    item6 = InlineKeyboardButton("6", callback_data='6')
    item7 = InlineKeyboardButton("7", callback_data='7')
    item8 = InlineKeyboardButton("8", callback_data='8')
    item9 = InlineKeyboardButton("9", callback_data='9')
    item10 = InlineKeyboardButton("10", callback_data='10')
    item11 = InlineKeyboardButton("11", callback_data='11')
    item12 = InlineKeyboardButton("12", callback_data='12')
    item13 = InlineKeyboardButton("13", callback_data='13')
    item14 = InlineKeyboardButton("14", callback_data='14')
    item15 = InlineKeyboardButton("15", callback_data='15')
    item16 = InlineKeyboardButton("16", callback_data='16')
    item17 = InlineKeyboardButton("17", callback_data='17')
    item18 = InlineKeyboardButton("Отмена", callback_data='cancel')
    markup.add(item1, item2, item3, item4, item5, item6, item7, item8, item9, item10, item11, item12, item13, item14,
               item15, item16, item17, item18)
    message.reply(message.chat.id, 'Выберите неделю', reply_markup=markup)
    await state.update_data(day=day)


@dp.callback_query_handler(state=StatesGroup.day)
def get_week(message: aiogram.types.CallbackQuery, state: FSMContext) -> None:
    try:
        global weeknum
        weeknum = message.text
        if weeknum == 'отмена' or weeknum == 'Отмена':
            return bot.send_message(message.chat.id, 'Введите фамилию преподавателя',
                                    reply_markup=aiogram.types.ReplyKeyboardRemove())
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
                bot.send_message(message.from_user.id, 'В этот день у преподавателя нет пар',
                                 reply_markup=aiogram.types.ReplyKeyboardRemove())
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
                bot.send_message(message.chat.id, text[i: i + 4096], reply_markup=aiogram.types.ReplyKeyboardRemove())
        else:
            bot.send_message(message.chat.id, 'Такого препода нет')
    except Exception as e:
        print(f"Error: {e}, \n in get_week")
