import argparse

import config
import scanner
from backtest import run_backtest

logger = config.get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Signal saham dan backtest sederhana")
    parser.add_argument("--backtest", action="store_true", help="jalankan backtest sederhana")
    parser.add_argument("--loop", action="store_true", help="jalankan scan otomatis berulang")
    parser.add_argument("--once", action="store_true", help="jalankan scan sekali saja")
    parser.add_argument("--intraday", action="store_true", help="pakai data intraday 1 menit")
    parser.add_argument(
        "--interval",
        type=float,
        default=config.DEFAULT_SCAN_INTERVAL,
        help="jeda antar scan dalam detik",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.backtest:
        scanner.configure_scan_mode(False)
        run_backtest()
        return

    run_loop = args.loop or not args.once
    run_intraday = args.intraday or run_loop
    scanner.configure_scan_mode(run_intraday)

    if run_loop:
        logger.info("Mode scan: %s (%s, %s)", scanner.SCAN_MODE, scanner.SCAN_INTERVAL, scanner.SCAN_PERIOD)
        scanner.run_forever(args.interval)
    else:
        logger.info("Mode scan: %s (%s, %s)", scanner.SCAN_MODE, scanner.SCAN_INTERVAL, scanner.SCAN_PERIOD)
        scanner.run_scan_once()


if __name__ == "__main__":
    main()
