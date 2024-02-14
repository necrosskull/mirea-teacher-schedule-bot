from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from bot.fetch.models import SearchItem
from bot.fetch.schedule import get_lessons
from bot.handlers import construct as construct
from bot.handlers import states as st
from bot.parse.formating import format_outputs
from bot.parse.semester import (
    get_dates_for_week,
    get_week_and_weekday,
)


async def send_item_clarity(
    update: Update, context: ContextTypes.DEFAULT_TYPE, firsttime=False
):
    schedule_items = context.user_data["available_items"]
    few_teachers_markup = construct.construct_item_markup(schedule_items)
    if firsttime:
        message = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="ℹ️ Выберите расписание:",
            reply_markup=few_teachers_markup,
        )
        context.user_data["message_id"] = message.message_id

    else:
        await update.callback_query.edit_message_text(
            text="ℹ️ Выберите расписание:", reply_markup=few_teachers_markup
        )

    return st.ITEM_CLARIFY


async def send_week_selector(
    update: Update, context: ContextTypes.DEFAULT_TYPE, firsttime=False
):
    selected_item: SearchItem = context.user_data["item"]
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
        message = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=construct.construct_weeks_markup(),
        )
        context.user_data["message_id"] = message.message_id

    else:
        await update.callback_query.edit_message_text(
            text=text, reply_markup=construct.construct_weeks_markup()
        )

    return st.GETWEEK


async def send_day_selector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected_item: SearchItem = context.user_data["item"]
    week = context.user_data["week"]
    schedule = context.user_data["schedule"]

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

    await update.callback_query.edit_message_text(
        text=text,
        reply_markup=workdays,
    )

    return st.GETDAY


async def send_result(
    update: Update, context: ContextTypes.DEFAULT_TYPE, show_week=False
):
    schedule_data = context.user_data["schedule"]

    date = context.user_data.get("date", None)
    week = context.user_data.get("week", None)

    if week:
        week = int(week)
    else:
        week, _ = get_week_and_weekday(date)

    dates_list = []

    if show_week:
        dates_list = get_dates_for_week(week)
    else:
        dates_list = [datetime.strptime(str(date), "%Y-%m-%d").date()]

    lessons = get_lessons(schedule_data, dates_list)

    if len(lessons) == 0:
        await update.callback_query.answer(text="В этот день пар нет.", show_alert=True)
        return st.GETWEEK

    blocks_of_text = format_outputs(lessons, context)

    return await telegram_delivery_optimisation(
        update, context, blocks_of_text, show_week=show_week
    )


async def telegram_delivery_optimisation(
    update: Update, context: ContextTypes.DEFAULT_TYPE, blocks: list, show_week=False
):
    week = context.user_data.get("week", None)
    date = context.user_data.get("date", None)

    if week is None:
        week, _ = get_week_and_weekday(date)

    schedule = context.user_data["schedule"]

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
                if update.callback_query.inline_message_id:
                    await update.callback_query.answer(
                        text="Слишком длинное расписание, пожалуйста, воспользуйтесь личными сообщениями бота или "
                        "выберите конкретный день недели",
                        show_alert=True,
                    )
                    break

                await update.callback_query.edit_message_text(chunk)
                first = False

            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id, text=chunk
                )

            chunk = block

    if chunk:
        if first:
            await update.callback_query.edit_message_text(chunk, reply_markup=workdays)

        else:
            message = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=chunk,
                reply_markup=workdays,
            )
            context.user_data["message_id"] = message.message_id

    return st.GETDAY


async def resend_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer(text="Введите новый запрос.", show_alert=True)
