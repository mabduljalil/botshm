import os
from pathlib import Path
from zoneinfo import ZoneInfo


APP_DIR = Path(__file__).resolve().parent
RUNTIME_CACHE_ROOT = Path("/tmp/bibit") if os.getenv("VERCEL") else APP_DIR / ".cache"
CACHE_DIR = RUNTIME_CACHE_ROOT
YFINANCE_CACHE_DIR = CACHE_DIR / "yfinance"
STATE_FILE = CACHE_DIR / "last_signal_state.json"

TELEGRAM_API_URL = "https://api.telegram.org"
REQUEST_TIMEOUT = 15

DAILY_DOWNLOAD_PERIOD = "1y"
DAILY_DOWNLOAD_INTERVAL = "1d"
INTRADAY_DOWNLOAD_PERIOD = "7d"
INTRADAY_DOWNLOAD_INTERVAL = "1m"

TOP_N = 5
BUY_TOP_N = 3
MIN_CANDLES = 220
DEFAULT_SCAN_INTERVAL = 1

BACKTEST_HORIZON_DAYS = 5
BACKTEST_HORIZONS = [3, 5, 10]
BACKTEST_THRESHOLDS = [55, 60, 65, 70, 75, 80]
BACKTEST_BUCKETS = [-1, 19, 39, 59, 79, 100]
BACKTEST_BUCKET_LABELS = ["0-19", "20-39", "40-59", "60-79", "80-100"]

STOCKS = [
    "BBRI.JK", "BBCA.JK", "BMRI.JK", "TLKM.JK", "ASII.JK",
    "ADRO.JK", "UNVR.JK", "ICBP.JK", "INDF.JK", "MDKA.JK",
    "GOTO.JK", "CPIN.JK", "KLBF.JK", "ANTM.JK", "PGAS.JK",
]

JAKARTA_TZ = ZoneInfo("Asia/Jakarta")


def load_dotenv_file(env_path=".env"):
    path = APP_DIR / env_path
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")

        if key and key not in os.environ:
            os.environ[key] = value


load_dotenv_file()
CACHE_DIR.mkdir(parents=True, exist_ok=True)
YFINANCE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
