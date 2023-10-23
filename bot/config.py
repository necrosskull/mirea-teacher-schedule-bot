import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
cmstoken = os.getenv("cmstoken")
grafana_token = os.getenv("grafana_token")
ADMINS = list(map(int, os.getenv("ADMINS").split(",")))
api_url = os.getenv("api_url") if "http" in os.getenv("api_url") else "https://" + os.getenv("api_url")
