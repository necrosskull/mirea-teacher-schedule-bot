def setup(dispatcher):
    import bot.handlers.handlers as handlers
    import bot.handlers.info as info
    import bot.handlers.inline as inline

    handlers.init_handlers(dispatcher)
    info.init_handlers(dispatcher)
    inline.init_handlers(dispatcher)
