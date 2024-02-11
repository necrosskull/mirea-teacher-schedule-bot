def setup(application):
    import bot.handlers.events as events
    import bot.handlers.handler as handler
    import bot.handlers.info as info
    import bot.handlers.inline as inline
    from bot.db.sqlite import ScheduleBot, db

    db.connect()
    db.create_tables([ScheduleBot])
    db.close()

    info.init_handlers(application)
    events.init_handlers(application)
    handler.init_handlers(application)
    inline.init_handlers(application)
