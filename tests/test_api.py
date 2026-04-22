import json
import os
import unittest
from io import BytesIO
from unittest.mock import patch

import api.index as api_index


class FakeHandler:
    def __init__(self, path, headers=None):
        self.path = path
        self.headers = headers or {}
        self.wfile = BytesIO()
        self.status_code = None
        self.response_headers = []

    def send_response(self, code):
        self.status_code = code

    def send_header(self, key, value):
        self.response_headers.append((key, value))

    def end_headers(self):
        pass


class ApiDoGetTests(unittest.TestCase):
    def test_health_do_get_returns_compact_status(self):
        fake_handler = FakeHandler("/api?action=health")

        with patch.object(api_index, "_runtime_health", return_value={
            "ready": True,
            "summary": {
                "telegram": True,
                "cache": True,
                "cron_secret": False,
                "runtime": "production",
            },
            "components": {
                "telegram": {"bot_token": True, "chat_id": True},
                "cache": {"dir": "/tmp/cache", "writable": True, "state_file": True, "yfinance": True},
                "runtime": {"mode": "production", "timezone": "Asia/Jakarta"},
            },
        }):
            api_index.handler.do_GET(fake_handler)

        payload = json.loads(fake_handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(fake_handler.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "health")
        self.assertTrue(payload["status"]["ready"])
        self.assertTrue(payload["status"]["summary"]["telegram"])
        self.assertIn("components", payload["status"])

    def test_test_telegram_do_get_calls_sender(self):
        fake_handler = FakeHandler("/api?action=test-telegram")

        with (
            patch.object(api_index, "send_telegram", return_value=True) as send_mock,
            patch.dict(os.environ, {"BOT_TOKEN": "token", "CHAT_ID": "chat"}, clear=False),
        ):
            api_index.handler.do_GET(fake_handler)

        payload = json.loads(fake_handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(fake_handler.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "test-telegram")
        self.assertTrue(payload["telegram_sent"])
        send_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
