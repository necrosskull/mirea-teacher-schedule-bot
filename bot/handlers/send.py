import datetime as dt

from aiogram import Bot

from aiogram.types import CallbackQuery, Message

from bot.fetch.models import SearchItem
from bot.fetch.schedule import get_lessons
from bot.handlers import construct as construct
from bot.handlers import states as st
from bot.parse.formating import format_outputs
from bot.parse.semester import (
    get_dates_for_week,
    get_week_and_weekday,
)


def _register_message_id(user_data: dict, message_id: int):
    message_ids = user_data.get("message_ids", [])
    if message_id not in message_ids:
        message_ids.append(message_id)

    if len(message_ids) > 30:
        message_ids = message_ids[-30:]

    user_data["message_ids"] = message_ids
    user_data["message_id"] = message_id


async def _edit_callback_message(
    callback: CallbackQuery,
    text: str,
    reply_markup=None,
):
    if callback.inline_message_id:
        await callback.bot.edit_message_text(
            text=text,
            inline_message_id=callback.inline_message_id,
            reply_markup=reply_markup,
        )
    elif callback.message:
        await callback.message.edit_text(text=text, reply_markup=reply_markup)


async def send_item_clarity(
    event: Message | CallbackQuery,
    bot: Bot,
    user_data: dict,
    firsttime=False,
    chat_id: int | None = None,
):
    schedule_items = user_data["available_items"]
    few_teachers_markup = construct.construct_item_markup(schedule_items)

    if firsttime:
        if chat_id is None:
            return st.ITEM_CLARIFY

        message = await bot.send_message(
            chat_id=chat_id,
            text="ℹ️ Выберите расписание:",
            reply_markup=few_teachers_markup,
        )
        _register_message_id(user_data, message.message_id)

    else:
        await _edit_callback_message(
            event,
            text="ℹ️ Выберите расписание:", reply_markup=few_teachers_markup
        )

    return st.ITEM_CLARIFY


async def send_week_selector(
    event: Message | CallbackQuery,
    bot: Bot,
    user_data: dict,
    firsttime=False,
    chat_id: int | None = None,
):
    selected_item: SearchItem = user_data["item"]
    type_text = ""
    if len(selected_item.name) > 0:
        match selected_item.type:
            case "teacher":
                type_text = f"ℹ️ Расписание преподавателя: {selected_item.name}"
            case "classroom":
                type_text = f"ℹ️ Расписание аудитории: {selected_item.name}"
            case "group":
                type_text = f"ℹ️ Расписание группы: {selected_item.name}"

    text = f"{type_text}\n🗓️ Выберите неделю:"

    if firsttime:
        if chat_id is None:
            return st.GETWEEK

        message = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=construct.construct_weeks_markup(),
        )
        _register_message_id(user_data, message.message_id)

    else:
        await _edit_callback_message(
            event,
            text=text,
            reply_markup=construct.construct_weeks_markup(),
        )

    return st.GETWEEK


async def send_day_selector(callback: CallbackQuery, user_data: dict):
    selected_item: SearchItem = user_data["item"]
    week = user_data["week"]
    schedule = user_data["schedule"]

    workdays = construct.construct_workdays(week, schedule)



    type_text = ""
    if len(selected_item.name) > 0:
        match selected_item.type:
            case "teacher":
                type_text = f"ℹ️ Расписание преподавателя: {selected_item.name}"
            case "classroom":
                type_text = f"ℹ️ Расписание аудитории: {selected_item.name}"
            case "group":
                type_text = f"ℹ️ Расписание группы: {selected_item.name}"

    text = f"{type_text}\n🗓️ Выбрана неделя: {week}\n📅 Выберите день:"

    await _edit_callback_message(callback, text=text, reply_markup=workdays)

    return st.GETDAY


async def send_result(
    callback: CallbackQuery,
    bot: Bot,
    user_data: dict,
    show_week=False,
):
    schedule_data = user_data["schedule"]

    target_date = user_data.get("date", None)
    week = user_data.get("week", None)

    if week:
        week = int(week)
    else:
        week, _ = get_week_and_weekday(target_date)

    dates_list = []

    if show_week:
        dates_list = get_dates_for_week(week)
    elif isinstance(target_date, dt.datetime):
        dates_list = [target_date.date()]
    elif isinstance(target_date, dt.date):
        dates_list = [target_date]
    elif target_date:
        try:
            dates_list = [dt.datetime.strptime(str(target_date), "%Y-%m-%d").date()]
        except ValueError:
            dates_list = []
    else:
        dates_list = []




    lessons = get_lessons(schedule_data, dates_list)

    if len(lessons) == 0:
        await callback.answer(text="В этот день пар нет.", show_alert=True)
        return st.GETWEEK

    blocks_of_text = format_outputs(lessons, user_data)

    return await telegram_delivery_optimisation(
        callback, bot, user_data, blocks_of_text, show_week=show_week
    )


async def telegram_delivery_optimisation(
    callback: CallbackQuery,
    bot: Bot,
    user_data: dict,
    blocks: list,
    show_week=False,
):
    week = user_data.get("week", None)
    date = user_data.get("date", None)

    if week is None:
        week, _ = get_week_and_weekday(date)

    schedule = user_data["schedule"]

    if show_week:
        workdays = construct.construct_workdays(week, schedule)
    else:
        workdays = construct.construct_workdays(week, schedule, selected_date=date)

    chunk = ""
    first = True
    for block in blocks:
        if len(chunk) + len(block) <= 4096:
            chunk += block

        else:
            if first:
                if callback.inline_message_id:
                    await callback.answer(
                        text="Слишком длинное расписание, пожалуйста, воспользуйтесь личными сообщениями бота или "
                        "выберите конкретный день недели",
                        show_alert=True,
                    )
                    break

                await _edit_callback_message(callback, chunk)
                first = False

            else:
                if callback.message:
                    await bot.send_message(chat_id=callback.message.chat.id, text=chunk)

            chunk = block

    if chunk:
        if first:
            await _edit_callback_message(callback, chunk, reply_markup=workdays)

        else:
            if callback.message:
                message = await bot.send_message(
                    chat_id=callback.message.chat.id,
                    text=chunk,
                    reply_markup=workdays,
                )
                _register_message_id(user_data, message.message_id)

    return st.GETDAY


async def resend_name_input(callback: CallbackQuery):
    await callback.answer(text="Введите новый запрос.", show_alert=True)
