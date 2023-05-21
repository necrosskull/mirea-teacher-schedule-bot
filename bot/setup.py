def setup(dispatcher):
    import bot.handlers as handlers
    import bot.info as info
    import bot.inline as inline

    handlers.init_handlers(dispatcher)
    info.init_handlers(dispatcher)
    inline.init_handlers(dispatcher)
