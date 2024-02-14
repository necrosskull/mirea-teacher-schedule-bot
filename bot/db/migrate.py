import os

from peewee import SqliteDatabase, TextField
from playhouse.migrate import SqliteMigrator, migrate

db = SqliteDatabase(os.path.join(os.path.dirname(__file__), "data/bot.db"))


def migrate_db():
    migrator = SqliteMigrator(db)

    favorite_field = TextField(null=True)
    migrate(migrator.add_column("schedulebot", "favorite", favorite_field))


migrate_db()
