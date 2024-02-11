import logging


class LazyLogger:
    def __init__(self):
        self.logger = logging.getLogger("bot.handlers")
        self.logger.setLevel("INFO")


lazy_logger = LazyLogger()
