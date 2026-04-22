import os
import unittest
from unittest.mock import patch

import api.index as api_index


class ApiPayloadTests(unittest.TestCase):
    def test_health_payload_reports_components(self):
        with (
            patch.object(api_index, "_runtime_health", return_value={
                "bot_token_set": True,
                "chat_id_set": True,
                "cron_secret_set": True,
                "cache": {
                    "cache_dir": "/tmp/cache",
                    "yfinance_cache_dir": "/tmp/cache/yfinance",
                    "state_file": "/tmp/cache/state.json",
                    "cache_dir_exists": True,
                    "yfinance_cache_dir_exists": True,
                    "state_file_exists": True,
                    "cache_writable": True,
                },
                "runtime": {
                    "mode": "production",
                    "timezone": "Asia/Jakarta",
                },
            }),
            patch.dict(os.environ, {"BOT_TOKEN": "x", "CHAT_ID": "y", "CRON_SECRET": "z", "VERCEL_ENV": "production"}, clear=False),
        ):
            payload = api_index.build_health_payload("/api")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "health")
        self.assertEqual(payload["path"], "/api")
        self.assertIn("status", payload)
        self.assertTrue(payload["status"]["bot_token_set"])
        self.assertTrue(payload["status"]["chat_id_set"])
        self.assertTrue(payload["status"]["cron_secret_set"])
        self.assertIn("cache", payload["status"])
        self.assertIn("runtime", payload["status"])

    def test_test_telegram_payload_returns_status(self):
        with patch.object(api_index, "send_telegram", return_value=True) as send_mock:
            with patch.dict(os.environ, {"BOT_TOKEN": "token", "CHAT_ID": "chat"}, clear=False):
                payload = api_index.build_test_telegram_payload("/api")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["action"], "test-telegram")
        self.assertTrue(payload["telegram_sent"])
        self.assertTrue(payload["bot_token_set"])
        self.assertTrue(payload["chat_id_set"])
        self.assertEqual(payload["path"], "/api")
        send_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
