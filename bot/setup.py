def setup(application):
    import bot.handlers.handlers as handlers
    import bot.handlers.info as info
    import bot.handlers.inline as inline
    import bot.handlers.events as events
    from bot.db.sqlite import ScheduleBot, db

    db.connect()
    db.create_tables([ScheduleBot])
    db.close()

    handlers.init_handlers(application)
    info.init_handlers(application)
    events.init_handlers(application)
    inline.init_handlers(application)
