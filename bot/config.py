import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
cmstoken = os.getenv("cmstoken")
grafana_token = os.getenv("grafana_token")