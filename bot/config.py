import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def parse_admins(admins_string: str | None) -> list[int]:
    if not admins_string:
        return []
    result = []
    for admin in admins_string.split(","):
        cleaned = admin.strip()
        if cleaned.isdigit() or (cleaned.startswith("-") and cleaned[1:].isdigit()):
            result.append(int(cleaned))
    return result


@dataclass
class Config:
    token: str = os.getenv("TOKEN", "")
    api_url: str = os.getenv("API_URL", "")
    admins: list[int] = field(default_factory=lambda: parse_admins(os.getenv("ADMINS")))
    db_path: str = os.getenv(
        "DB_PATH",
        os.path.join(os.path.dirname(__file__), "db/data/bot.db"),
    )
    schedule_cache_ttl_seconds: int = int(os.getenv("SCHEDULE_CACHE_TTL_SECONDS", "14400"))
    search_cache_ttl_seconds: int = int(os.getenv("SEARCH_CACHE_TTL_SECONDS", "3600"))
    memory_cache_ttl_seconds: int = int(os.getenv("MEMORY_CACHE_TTL_SECONDS", "900"))
    webapp_url: str = os.getenv("WEBAPP_URL", "")
    webapp_host: str = os.getenv("WEBAPP_HOST", "0.0.0.0")
    webapp_port: int = int(os.getenv("WEBAPP_PORT", "8000"))




settings = Config()

