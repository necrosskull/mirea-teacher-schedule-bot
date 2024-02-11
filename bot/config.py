import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def parse_admins(admins_string):
    return [int(admin) for admin in admins_string.split(",")]


@dataclass
class Config:
    token: str = os.getenv("TOKEN")
    api_url: str = os.getenv("API_URL")
    admins: list = field(default_factory=lambda: parse_admins(os.getenv("ADMINS")))


settings = Config()
