def setup(dispatcher):
    import bot.handlers.handlers as handlers
    import bot.handlers.info as info
    import bot.handlers.inline as inline
    from bot.db.sqlite import ScheduleBot, db

    db.connect()
    db.create_tables([ScheduleBot])
    db.close()

    handlers.init_handlers(dispatcher)
    info.init_handlers(dispatcher)
    inline.init_handlers(dispatcher)
