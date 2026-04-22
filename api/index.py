import json
import os
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import config
from telegram import send_telegram

logger = config.get_logger(__name__)


def _json_response(handler, status_code, payload):
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _is_authorized(handler):
    cron_secret = os.getenv("CRON_SECRET", "").strip()
    if not cron_secret:
        return True

    auth_header = handler.headers.get("authorization", "").strip()
    return auth_header == f"Bearer {cron_secret}"


def _runtime_health():
    bot_token_set = bool(os.getenv("BOT_TOKEN", "").strip())
    chat_id_set = bool(os.getenv("CHAT_ID", "").strip())
    cron_secret_set = bool(os.getenv("CRON_SECRET", "").strip())

    cache_status = {
        "cache_dir": str(config.CACHE_DIR),
        "yfinance_cache_dir": str(config.YFINANCE_CACHE_DIR),
        "state_file": str(config.STATE_FILE),
        "cache_dir_exists": config.CACHE_DIR.exists(),
        "yfinance_cache_dir_exists": config.YFINANCE_CACHE_DIR.exists(),
        "state_file_exists": config.STATE_FILE.exists(),
        "cache_writable": False,
    }

    for attempt in range(1, 4):
        try:
            config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            probe_file = config.CACHE_DIR / ".healthcheck"
            probe_file.write_text("ok", encoding="utf-8")
            cache_status["cache_writable"] = probe_file.read_text(encoding="utf-8") == "ok"
            probe_file.unlink(missing_ok=True)
            break
        except Exception as exc:
            logger.warning("Health cache probe gagal pada percobaan %s/3: %s", attempt, exc)
            cache_status["cache_writable"] = False
            if attempt < 3:
                continue

    return {
        "bot_token_set": bot_token_set,
        "chat_id_set": chat_id_set,
        "cron_secret_set": cron_secret_set,
        "cache": cache_status,
        "runtime": {
            "mode": os.getenv("VERCEL_ENV", "local"),
            "timezone": str(config.JAKARTA_TZ),
        },
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not _is_authorized(self):
            _json_response(self, 401, {"ok": False, "error": "unauthorized"})
            return

        request_url = urlparse(self.path)
        query = parse_qs(request_url.query)
        action = query.get("action", ["scan"])[0].lower()

        if action == "health":
            payload = {
                "ok": True,
                "action": "health",
                "timestamp_wib": datetime.now(config.JAKARTA_TZ).isoformat(),
                "path": request_url.path,
                "status": _runtime_health(),
            }
            _json_response(self, 200, payload)
            return

        if action == "test-telegram":
            bot_token_set = bool(os.getenv("BOT_TOKEN", "").strip())
            chat_id_set = bool(os.getenv("CHAT_ID", "").strip())
            message = (
                "OK Test Telegram dari Vercel berhasil.\n"
                f"Waktu: {datetime.now(config.JAKARTA_TZ).strftime('%Y-%m-%d %H:%M:%S WIB')}"
            )
            telegram_ok = send_telegram(message)
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "action": "test-telegram",
                    "telegram_sent": telegram_ok,
                    "bot_token_set": bot_token_set,
                    "chat_id_set": chat_id_set,
                    "timestamp_wib": datetime.now(config.JAKARTA_TZ).isoformat(),
                    "path": request_url.path,
                },
            )
            return

        mode = query.get("mode", ["daily"])[0].lower()
        intraday = mode != "daily"
        notify_mode = query.get("notify", ["changes"])[0].lower()
        bootstrap = query.get("bootstrap", ["1"])[0].lower() not in {"0", "false", "no"}

        try:
            import scanner

            scanner.configure_scan_mode(intraday)
            result = scanner.run_scan_once(notify_mode=notify_mode, bootstrap_on_first_run=bootstrap)
            payload = {
                "ok": True,
                "mode": scanner.SCAN_MODE,
                "timestamp_wib": datetime.now(config.JAKARTA_TZ).isoformat(),
                "path": request_url.path,
                "notify_mode": notify_mode,
                "bootstrap": bootstrap,
                "result": result,
            }
        except Exception as exc:
            payload = {
                "ok": False,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "mode": "intraday" if intraday else "daily",
                "notify_mode": notify_mode,
                "bootstrap": bootstrap,
                "path": request_url.path,
            }

        _json_response(self, 200, payload)
