import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl, unquote

from bot.config import settings
from bot.logs.lazy_logger import lazy_logger


def validate_telegram_init_data(
    init_data: str, bot_token: str | None = None, max_age_seconds: int = 86400
) -> dict | None:
    """
    Validate Telegram WebApp initData string using HMAC-SHA256.
    Returns user dict on success, None on invalid data.
    """
    token = bot_token or settings.token
    if not init_data or not token:
        return None

    try:
        parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in parsed_data:
            return None

        received_hash = parsed_data.pop("hash")

        # Check auth_date for replay attack prevention
        if "auth_date" in parsed_data:
            auth_date = int(parsed_data["auth_date"])
            if time.time() - auth_date > max_age_seconds:
                lazy_logger.logger.warning("Telegram initData expired")
                return None

        # Sort keys alphabetically and format string
        data_check_string = "\n".join(
            f"{key}={parsed_data[key]}" for key in sorted(parsed_data.keys())
        )

        # secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
        secret_key = hmac.new(
            b"WebAppData", token.encode("utf-8"), hashlib.sha256
        ).digest()

        # calculated_hash = HMAC_SHA256(key=secret_key, msg=data_check_string)
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            lazy_logger.logger.warning("Telegram initData hash mismatch")
            return None

        # Extract user
        user_json = parsed_data.get("user")
        if user_json:
            return json.loads(user_json)

        return parsed_data
    except Exception as e:
        lazy_logger.logger.warning(f"Error validating telegram initData: {e}")
        return None
