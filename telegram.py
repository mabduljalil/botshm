import json
import os
import time

import requests

import config

logger = config.get_logger(__name__)


def send_telegram(msg):
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    chat_id = os.getenv("CHAT_ID", "").strip()

    if not bot_token or not chat_id:
        logger.error("Telegram config missing. Isi BOT_TOKEN dan CHAT_ID di file .env")
        return False

    url = f"{config.TELEGRAM_API_URL}/bot{bot_token}/sendMessage"

    for attempt in range(1, 4):
        try:
            response = requests.post(
                url,
                data={"chat_id": chat_id, "text": msg},
                timeout=config.REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            payload = response.json()
            if not payload.get("ok"):
                logger.error("Telegram API error: %s", payload)
                return False

            return True
        except requests.Timeout:
            logger.warning("Telegram timeout pada percobaan %s/3", attempt)
        except requests.RequestException as exc:
            logger.warning("Telegram request error pada percobaan %s/3: %s", attempt, exc)
        except ValueError:
            logger.error("Telegram error: response bukan JSON yang valid")
            return False

        if attempt < 3:
            time.sleep(attempt)

    return False


def load_last_signal_state():
    if not config.STATE_FILE.exists():
        return {}

    try:
        return json.loads(config.STATE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Gagal membaca state terakhir: %s", exc)
        return {}


def save_last_signal_state(state):
    config.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
