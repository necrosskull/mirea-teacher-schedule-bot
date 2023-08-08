from peewee import *

db = SqliteDatabase('db/data/bot.db')


class ScheduleBot(Model):
    id = PrimaryKeyField(unique=True)
    username = TextField(null=True)
    first_name = TextField(null=True)
    last_name = TextField(null=True)

    class Meta:
        database = db
