import json
import os
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import config


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


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not _is_authorized(self):
            _json_response(self, 401, {"ok": False, "error": "unauthorized"})
            return

        request_url = urlparse(self.path)
        query = parse_qs(request_url.query)
        mode = query.get("mode", ["daily"])[0].lower()
        intraday = mode != "daily"

        try:
            import scanner

            scanner.configure_scan_mode(intraday)
            result = scanner.run_scan_once()
            payload = {
                "ok": True,
                "mode": scanner.SCAN_MODE,
                "timestamp_wib": datetime.now(config.JAKARTA_TZ).isoformat(),
                "path": request_url.path,
                "result": result,
            }
        except Exception as exc:
            payload = {
                "ok": False,
                "error": str(exc),
                "traceback": traceback.format_exc(),
                "mode": "intraday" if intraday else "daily",
                "path": request_url.path,
            }

        _json_response(self, 200, payload)
