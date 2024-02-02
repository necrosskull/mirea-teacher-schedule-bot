import logging

import logging_loki

import bot.config as config


class LazyLogger:
    def __init__(self):
        self.logger = None

    def init_logger(self, grafana_token):
        if grafana_token:
            loki_handler = logging_loki.LokiHandler(
                url="https://loki.grafana.mirea.ninja/loki/api/v1/push",
                auth=("logger", grafana_token),
                tags={"app": "mirea-teacher-schedule-bot", "env": "production"},
                version="1",
            )

            self.logger = logging.getLogger("bot.handlers")
            self.logger.setLevel("INFO")
            self.logger.addHandler(loki_handler)
        else:
            self.logger = logging.getLogger("bot.handlers")
            self.logger.setLevel("INFO")

    def __getattr__(self, attr):
        if not self.logger:
            self.init_logger(config.grafana_token)
        return getattr(self.logger, attr)


lazy_logger = LazyLogger()
