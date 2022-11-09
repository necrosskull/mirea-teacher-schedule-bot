

if __name__ == '__main__':
    from handlers import bot
    import aiogram
    aiogram.executor.start_polling(bot.dp, skip_updates=True)