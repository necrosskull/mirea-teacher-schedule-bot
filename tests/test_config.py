import os
from pathlib import Path

import bot.config
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
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.example.com")
    monkeypatch.setenv("SUPABASE_KEY", "sb_publishable_test")
    monkeypatch.setenv("SCHEDULE_ORGANIZATION_ID", "mirea")
    monkeypatch.setenv("ADMINS", "111,222")
    monkeypatch.setenv("DB_PATH", "/tmp/test.db")

    cfg = Config(
        token=os.getenv("TOKEN"),
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_key=os.getenv("SUPABASE_KEY"),
        organization_id=os.getenv("SCHEDULE_ORGANIZATION_ID"),
        admins=parse_admins(os.getenv("ADMINS")),
        db_path=os.getenv("DB_PATH"),
    )
    assert cfg.token == "test_token_123"
    assert cfg.supabase_url == "https://supabase.example.com"
    assert cfg.supabase_key == "sb_publishable_test"
    assert cfg.organization_id == "mirea"
    assert cfg.admins == [111, 222]
    assert cfg.db_path == "/tmp/test.db"


def test_config_reads_supabase_settings_from_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.example.com")
    monkeypatch.setenv("SUPABASE_KEY", "sb_publishable_from_env")

    cfg = Config(
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_key=os.getenv("SUPABASE_KEY"),
    )
    assert cfg.supabase_url == "https://supabase.example.com"
    assert cfg.supabase_key == "sb_publishable_from_env"
    assert cfg.has_schedule_backend is True


def test_config_has_no_embedded_supabase_credentials():
    cfg = Config()
    assert not hasattr(cfg, "api_url")
    # Credentials must come from .env, never from source code.
    config_source = Path(bot.config.__file__).read_text(encoding="utf-8")
    assert "sb_publishable_" not in config_source
    assert "supabase.co" not in config_source


def test_has_schedule_backend_requires_both_values():
    assert Config(supabase_url="https://x", supabase_key="k").has_schedule_backend
    assert not Config(supabase_url="", supabase_key="k").has_schedule_backend
    assert not Config(supabase_url="https://x", supabase_key="").has_schedule_backend
