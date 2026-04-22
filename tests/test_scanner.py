import unittest
from unittest.mock import patch

import scanner


def make_item(
    ticker,
    price,
    setup,
    regime,
    score,
    confidence,
    rsi=55.0,
    adx=20.0,
    volume_ratio=1.0,
    atr_pct=3.0,
    support_20=100.0,
    resistance_20=120.0,
    reasons="above ema20",
    buy_signal=False,
):
    return {
        "ticker": ticker,
        "price": price,
        "setup": setup,
        "market_regime": regime,
        "score": score,
        "confidence": confidence,
        "rsi": rsi,
        "adx": adx,
        "volume_ratio": volume_ratio,
        "atr_pct": atr_pct,
        "support_20": support_20,
        "resistance_20": resistance_20,
        "reasons": reasons,
        "buy_signal": buy_signal,
    }


class ScannerChangeFlowTests(unittest.TestCase):
    def setUp(self):
        self.stocks_patch = patch.object(scanner.config, "STOCKS", ["AAA.JK", "BBB.JK"])
        self.stocks_patch.start()
        self.addCleanup(self.stocks_patch.stop)

    def _run_scan(self, current_items, previous_state=None, bootstrap=True):
        current_map = {item["ticker"]: item for item in current_items}

        def fake_analyze(ticker):
            return current_map[ticker]

        save_calls = []
        telegram_calls = []

        with (
            patch.object(scanner, "analyze", side_effect=fake_analyze),
            patch.object(scanner, "get_trading_time", return_value="HOLD / WAIT"),
            patch.object(scanner, "load_last_signal_state", return_value=previous_state or {}),
            patch.object(scanner, "save_last_signal_state", side_effect=lambda state: save_calls.append(state)),
            patch.object(scanner, "send_telegram", side_effect=lambda msg: telegram_calls.append(msg) or True),
        ):
            result = scanner.run_scan_once(bootstrap_on_first_run=bootstrap)

        return result, save_calls, telegram_calls

    def test_bootstrap_saves_state_without_sending(self):
        current_items = [
            make_item("AAA.JK", 100, "WATCHLIST", "BULLISH", 80, 80),
            make_item("BBB.JK", 200, "AVOID", "SIDEWAYS", 10, 10),
        ]

        result, save_calls, telegram_calls = self._run_scan(current_items, previous_state={}, bootstrap=True)

        self.assertEqual(result["status"], "bootstrapped")
        self.assertFalse(result["telegram_sent"])
        self.assertEqual(len(save_calls), 1)
        self.assertEqual(save_calls[0]["bootstrap"], True)
        self.assertEqual(len(telegram_calls), 0)

    def test_unchanged_state_does_not_send(self):
        current_items = [
            make_item("AAA.JK", 100, "WATCHLIST", "BULLISH", 80, 80),
            make_item("BBB.JK", 200, "AVOID", "SIDEWAYS", 10, 10),
        ]
        previous_state = {
            "tickers": {item["ticker"]: scanner.build_ticker_state(item) for item in current_items},
            "updated_at": "2026-04-22T00:00:00+07:00",
        }

        result, save_calls, telegram_calls = self._run_scan(current_items, previous_state=previous_state, bootstrap=False)

        self.assertEqual(result["status"], "unchanged")
        self.assertFalse(result["telegram_sent"])
        self.assertEqual(len(save_calls), 0)
        self.assertEqual(len(telegram_calls), 0)

    def test_changed_state_sends_message(self):
        previous_items = [
            make_item("AAA.JK", 100, "WATCHLIST", "BULLISH", 80, 80),
            make_item("BBB.JK", 200, "AVOID", "SIDEWAYS", 10, 10),
        ]
        current_items = [
            make_item("AAA.JK", 101, "WATCHLIST", "BULLISH", 82, 82),
            make_item("BBB.JK", 200, "AVOID", "SIDEWAYS", 10, 10),
        ]
        previous_state = {
            "tickers": {item["ticker"]: scanner.build_ticker_state(item) for item in previous_items},
            "updated_at": "2026-04-22T00:00:00+07:00",
        }

        result, save_calls, telegram_calls = self._run_scan(current_items, previous_state=previous_state, bootstrap=False)

        self.assertEqual(result["status"], "sent")
        self.assertTrue(result["telegram_sent"])
        self.assertEqual(result["changed_count"], 1)
        self.assertIn("AAA.JK", result["changed_tickers"])
        self.assertEqual(len(save_calls), 1)
        self.assertEqual(len(telegram_calls), 1)


if __name__ == "__main__":
    unittest.main()
