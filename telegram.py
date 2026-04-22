import json
import os

import requests

import config


def send_telegram(msg):
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    chat_id = os.getenv("CHAT_ID", "").strip()

    if not bot_token or not chat_id:
        print("Telegram config missing. Isi BOT_TOKEN dan CHAT_ID di file .env")
        return False

    url = f"{config.TELEGRAM_API_URL}/bot{bot_token}/sendMessage"

    try:
        response = requests.post(
            url,
            data={"chat_id": chat_id, "text": msg},
            timeout=config.REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        payload = response.json()
        if not payload.get("ok"):
            print(f"Telegram API error: {payload}")
            return False

        return True
    except requests.Timeout:
        print("Telegram error: request timeout")
    except requests.RequestException as exc:
        print(f"Telegram error: {exc}")
    except ValueError:
        print("Telegram error: response bukan JSON yang valid")

    return False


def load_last_signal_state():
    if not config.STATE_FILE.exists():
        return {}

    try:
        return json.loads(config.STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_last_signal_state(state):
    config.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
