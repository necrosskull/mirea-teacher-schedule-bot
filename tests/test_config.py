import os
from bot.config import Config, parse_admins


def test_parse_admins_none_and_empty():
    assert parse_admins(None) == []
    assert parse_admins("") == []
    assert parse_admins("   ") == []


def test_parse_admins_valid():
    assert parse_admins("123,456,789") == [123, 456, 789]
    assert parse_admins(" 123 ,  456 ") == [123, 456]
    assert parse_admins("-1001,2002") == [-1001, 2002]


def test_parse_admins_with_invalid_items():
    assert parse_admins("123,abc,456,xyz") == [123, 456]
    assert parse_admins("abc,def") == []


def test_config_instance(monkeypatch):
    monkeypatch.setenv("TOKEN", "test_token_123")
    monkeypatch.setenv("API_URL", "https://schedule-of-mirea.example.com")
    monkeypatch.setenv("ADMINS", "111,222")
    monkeypatch.setenv("DB_PATH", "/tmp/test.db")

    cfg = Config(
        token=os.getenv("TOKEN"),
        api_url=os.getenv("API_URL"),
        admins=parse_admins(os.getenv("ADMINS")),
        db_path=os.getenv("DB_PATH"),
    )
    assert cfg.token == "test_token_123"
    assert cfg.api_url == "https://schedule-of-mirea.example.com"
    assert cfg.admins == [111, 222]
    assert cfg.db_path == "/tmp/test.db"
