async def setup(dispatcher):
    import bot.handlers.events as events
    import bot.handlers.favorite as favorite
    import bot.handlers.handler as handler
    import bot.handlers.info as info
    import bot.handlers.inline as inline
    import bot.handlers.notification as notification
    from bot.handlers.context import bot_data
    from bot.db.sqlite import init_db

    await init_db()

    bot_data["maintenance_mode"] = False
    bot_data["maintenance_message"] = None

    info.init_handlers(dispatcher)
    events.init_handlers(dispatcher)
    favorite.init_handlers(dispatcher)
    handler.init_handlers(dispatcher)
    inline.init_handlers(dispatcher)
    notification.init_handlers(dispatcher)
