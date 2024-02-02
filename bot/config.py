import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
decode_url = os.getenv("decode_url") if os.getenv("decode_url") else None
grafana_token = os.getenv("grafana_token")
ADMINS = list(map(int, os.getenv("ADMINS").split(",")))
api_url = os.getenv("api_url")
