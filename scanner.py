import json
import time
from datetime import datetime

import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, EMAIndicator, MACD
from ta.volatility import AverageTrueRange

import config
from telegram import load_last_signal_state, save_last_signal_state, send_telegram


if hasattr(yf, "set_tz_cache_location"):
    yf.set_tz_cache_location(str(config.YFINANCE_CACHE_DIR))

JAKARTA_TZ = config.JAKARTA_TZ

SCAN_PERIOD = config.DAILY_DOWNLOAD_PERIOD
SCAN_INTERVAL = config.DAILY_DOWNLOAD_INTERVAL
SCAN_MODE = "daily"


def get_trading_time(now=None):
    now = now or datetime.now(JAKARTA_TZ)
    hour = now.hour

    if now.weekday() >= 5:
        return "Market tutup (akhir pekan)"

    if 9 <= hour < 11:
        return "BUY TIME (pagi - momentum awal)"
    if 11 <= hour < 14:
        return "HOLD / WAIT"
    if 14 <= hour <= 15:
        return "SELL TIME (take profit / cut loss)"
    return "Market tutup"


def configure_scan_mode(intraday=False):
    global SCAN_PERIOD, SCAN_INTERVAL, SCAN_MODE

    if intraday:
        SCAN_MODE = "intraday"
        SCAN_PERIOD = config.INTRADAY_DOWNLOAD_PERIOD
        SCAN_INTERVAL = config.INTRADAY_DOWNLOAD_INTERVAL
    else:
        SCAN_MODE = "daily"
        SCAN_PERIOD = config.DAILY_DOWNLOAD_PERIOD
        SCAN_INTERVAL = config.DAILY_DOWNLOAD_INTERVAL


def select_top_candidates(results, limit=config.TOP_N):
    return sorted(results, key=lambda item: item["score"], reverse=True)[:limit]


def select_buy_candidates(results):
    return sorted(
        [item for item in results if item["buy_signal"]],
        key=lambda item: (item["confidence"], item["score"]),
        reverse=True,
    )


def build_buy_section(buy_candidates):
    if not buy_candidates:
        return "BUY SECTION:\n- Tidak ada saham yang lolos buy signal\n\n"

    lines = ["BUY SECTION:"]
    for item in buy_candidates[:config.BUY_TOP_N]:
        lines.append(
            f"{item['ticker']} -> BUY | Score {item['score']} | Conf {item['confidence']} "
            f"| RSI {item['rsi']:.1f} | Regime {item['market_regime']}"
        )
    return "\n".join(lines) + "\n\n"


def build_watch_section(top_candidates):
    lines = ["WATCH SECTION:"]
    for item in top_candidates:
        lines.append(
            f"{item['ticker']} -> {item['setup']} | Regime {item['market_regime']} "
            f"| Score {item['score']} | Conf {item['confidence']} "
            f"| RSI {item['rsi']:.1f} | Vol x{item['volume_ratio']:.2f}"
        )
    return "\n".join(lines) + "\n\n"


def build_signal_note(best):
    if best["setup"] == "BUY WATCH":
        return "Bullish setup -> pantau entry"
    if best["setup"] == "WATCHLIST":
        return "Cukup menarik -> tunggu trigger"
    if best["setup"] == "WAIT":
        return "Setup campuran -> tunggu konfirmasi"
    return "Kondisi belum kuat -> hindari entry"


def build_scan_message(top_candidates, buy_candidates, best, trade_time):
    msg = f"TOP {config.TOP_N} SAHAM HARI INI\n\n"
    msg += build_buy_section(buy_candidates)
    msg += build_watch_section(top_candidates)
    msg += f"""

TERBAIK: {best['ticker']} ({best['score']})
SETUP: {best['setup']}
REGIME: {best['market_regime']}
CONFIDENCE: {best['confidence']}

STATUS MARKET:
{trade_time}

WAKTU JAKARTA:
{datetime.now(JAKARTA_TZ).strftime('%Y-%m-%d %H:%M:%S WIB')}

KONDISI:
RSI: {best['rsi']:.2f}
ADX: {best['adx']:.2f}
Volume ratio: x{best['volume_ratio']:.2f}
ATR: {best['atr_pct']:.2f}%
Support 20D: {best['support_20']:.2f} ({best['support_gap_pct']:.2f}% dari harga)
Resistance 20D: {best['resistance_20']:.2f} ({best['resistance_gap_pct']:.2f}% dari harga)
{build_signal_note(best)}
Alasan: {best['reasons']}

LEVEL:
SL: {best['stop_loss']:.2f}
TP: {best['take_profit']:.2f}

STRATEGI:
- BUY saat harga dekat support / pagi hari
- SELL saat mendekati resistance / sore hari
"""
    return msg


def build_ticker_state(item):
    return {
        "signature": json.dumps(
            {
                "ticker": item["ticker"],
                "price": round(float(item["price"]), 2),
                "setup": item["setup"],
                "regime": item["market_regime"],
                "score": int(item["score"]),
                "confidence": int(item["confidence"]),
                "rsi": round(float(item["rsi"]), 2),
                "adx": round(float(item["adx"]), 2),
                "volume_ratio": round(float(item["volume_ratio"]), 2),
                "atr_pct": round(float(item["atr_pct"]), 2),
                "support_20": round(float(item["support_20"]), 2),
                "resistance_20": round(float(item["resistance_20"]), 2),
                "buy_signal": item["buy_signal"],
            },
            sort_keys=True,
        ),
        "ticker": item["ticker"],
        "price": item["price"],
        "setup": item["setup"],
        "regime": item["market_regime"],
        "score": item["score"],
        "confidence": item["confidence"],
        "rsi": item["rsi"],
        "adx": item["adx"],
        "volume_ratio": item["volume_ratio"],
        "atr_pct": item["atr_pct"],
        "support_20": item["support_20"],
        "resistance_20": item["resistance_20"],
        "buy_signal": item["buy_signal"],
        "updated_at": datetime.now(JAKARTA_TZ).isoformat(),
    }


def build_ticker_change_line(previous, current):
    if not previous:
        return (
            f"BARU {current['ticker']} | {current['setup']} | Regime {current['regime']} "
            f"| Score {current['score']} | Conf {current['confidence']} | RSI {current['rsi']:.1f}"
        )

    return (
        f"{current.get('ticker', '-')} | {previous.get('price', 0):.2f} -> {current['price']:.2f} | "
        f"{previous.get('setup', '-')} -> {current['setup']} | "
        f"{previous.get('regime', '-')} -> {current['regime']} | "
        f"Score {previous.get('score', 0)} -> {current['score']} | "
        f"Conf {previous.get('confidence', 0)} -> {current['confidence']} | "
        f"RSI {previous.get('rsi', 0):.1f} -> {current['rsi']:.1f}"
    )


def build_changes_message(changed_items, trade_time):
    lines = [f"PERUBAHAN SAHAM ({len(changed_items)})", ""]
    lines.append(f"STATUS MARKET: {trade_time}")
    lines.append(f"WAKTU JAKARTA: {datetime.now(JAKARTA_TZ).strftime('%Y-%m-%d %H:%M:%S WIB')}")
    lines.append("")

    for previous, current in changed_items:
        lines.append(build_ticker_change_line(previous, current))
        lines.append(
            f"  - Volume x{current['volume_ratio']:.2f} | ADX {current['adx']:.2f} | "
            f"ATR {current['atr_pct']:.2f}%"
        )
        lines.append(
            f"  - Support {current['support_20']:.2f} | Resistance {current['resistance_20']:.2f}"
        )
        lines.append(f"  - {build_signal_note(current)}")
        lines.append(f"  - Alasan: {current['reasons']}")
        lines.append("")

    return "\n".join(lines).strip()


def should_send_update(previous_state, current_ticker_states):
    previous_tickers = previous_state.get("tickers", {})
    if not previous_tickers:
        return True

    for ticker, current_state in current_ticker_states.items():
        previous_state_for_ticker = previous_tickers.get(ticker)
        if not previous_state_for_ticker:
            return True
        if previous_state_for_ticker.get("signature") != current_state.get("signature"):
            return True

    return False


def download_history(ticker):
    try:
        data = yf.download(
            ticker,
            period=SCAN_PERIOD,
            interval=SCAN_INTERVAL,
            progress=False,
            auto_adjust=False,
            threads=False,
        )
    except Exception as exc:
        print(f"Error download {ticker}: {exc}")
        return None

    if data is None or data.empty:
        print(f"Data kosong untuk {ticker}")
        return None

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    if len(data) < config.MIN_CANDLES:
        print(f"Data {ticker} kurang dari {config.MIN_CANDLES} candle")
        return None

    close = data.get("Close")
    high = data.get("High")
    low = data.get("Low")
    volume = data.get("Volume")
    if close is None:
        print(f"Kolom Close tidak ditemukan untuk {ticker}")
        return None

    if isinstance(close, pd.DataFrame):
        close = close.squeeze()

    if close is None or close.empty:
        print(f"Close kosong untuk {ticker}")
        return None

    if high is None or low is None or volume is None:
        print(f"Kolom High/Low/Volume tidak lengkap untuk {ticker}")
        return None

    return data


def build_feature_frame(data):
    close = data["Close"]
    high = data["High"]
    low = data["Low"]
    volume = data["Volume"]

    try:
        ema20 = EMAIndicator(close=close, window=20).ema_indicator()
        ema50 = EMAIndicator(close=close, window=50).ema_indicator()
        ema200 = EMAIndicator(close=close, window=200).ema_indicator()
        rsi = RSIIndicator(close=close, window=14).rsi()
        macd = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
        macd_line = macd.macd()
        macd_signal = macd.macd_signal()
        macd_diff = macd.macd_diff()
        adx = ADXIndicator(high=high, low=low, close=close, window=14)
        adx_val = adx.adx()
        atr = AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range()
        vol_sma20 = volume.rolling(20).mean()
        resistance_20 = high.shift(1).rolling(20).max()
        support_20 = low.shift(1).rolling(20).min()
    except Exception as exc:
        print(f"Error hitung indikator: {exc}")
        return None

    df = pd.DataFrame({
        "close": close,
        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,
        "rsi": rsi,
        "macd_line": macd_line,
        "macd_signal": macd_signal,
        "macd_diff": macd_diff,
        "adx": adx_val,
        "atr": atr,
        "volume": volume,
        "vol_sma20": vol_sma20,
        "resistance_20": resistance_20,
        "support_20": support_20,
    })

    df["ema200_prev5"] = df["ema200"].shift(5)
    return df.dropna()


def evaluate_row(row):
    price = float(row["close"])
    ema20_val = float(row["ema20"])
    ema50_val = float(row["ema50"])
    ema200_val = float(row["ema200"])
    ema200_prev = float(row["ema200_prev5"])
    rsi_val = float(row["rsi"])
    macd_line_val = float(row["macd_line"])
    macd_signal_val = float(row["macd_signal"])
    macd_diff_val = float(row["macd_diff"])
    adx_val = float(row["adx"])
    atr_val = float(row["atr"])
    volume_val = float(row["volume"])
    vol_sma20_val = float(row["vol_sma20"])
    resistance_20_val = float(row["resistance_20"])
    support_20_val = float(row["support_20"])

    volume_ratio = volume_val / vol_sma20_val if vol_sma20_val else 0.0
    atr_pct = (atr_val / price) * 100 if price else 0.0
    resistance_gap_pct = ((resistance_20_val - price) / price) * 100 if price else 0.0
    support_gap_pct = ((price - support_20_val) / price) * 100 if price else 0.0
    breakout = price >= resistance_20_val and volume_ratio >= 1.2
    near_support = 0 <= support_gap_pct <= max(atr_pct * 0.8, 1.5)
    near_breakout = 0 <= resistance_gap_pct <= max(atr_pct * 0.8, 1.5)

    if ema20_val > ema50_val > ema200_val and price > ema200_val:
        market_regime = "BULLISH"
    elif ema20_val < ema50_val < ema200_val and price < ema200_val:
        market_regime = "BEARISH"
    else:
        market_regime = "SIDEWAYS"

    score = 0
    reasons = []

    if price > ema20_val:
        score += 15
        reasons.append("above ema20")
    else:
        score -= 10

    if ema20_val > ema50_val:
        score += 20
        reasons.append("trend up")
    else:
        score -= 10

    if ema50_val > ema200_val:
        score += 12
        reasons.append("mid-term up")
    if ema200_val > ema200_prev:
        score += 8
        reasons.append("ema200 rising")

    if macd_line_val > macd_signal_val and macd_diff_val > 0:
        score += 20
        reasons.append("macd bullish")
    elif macd_diff_val < 0:
        score -= 10

    if adx_val >= 20:
        score += 10
        reasons.append("trend strength")
    if adx_val >= 25:
        score += 5
    if adx_val < 15:
        score -= 6

    if volume_ratio >= 1.5:
        score += 12
        reasons.append("volume spike")
    elif volume_ratio >= 1.1:
        score += 8
        reasons.append("volume support")
    elif volume_ratio < 0.8:
        score -= 5

    if 45 <= rsi_val <= 65:
        score += 12
        reasons.append("healthy rsi")
    elif 65 < rsi_val <= 72:
        score += 4
        reasons.append("momentum hot")
    elif rsi_val > 72:
        score -= 8
        reasons.append("overbought")
    elif rsi_val < 35:
        score -= 6
        reasons.append("weak momentum")

    if breakout:
        score += 12
        reasons.append("breakout")
    elif near_support and ema20_val > ema50_val:
        score += 10
        reasons.append("pullback zone")
    elif near_breakout:
        score += 6
        reasons.append("near resistance")

    if market_regime == "BULLISH":
        score += 10
        reasons.append("bull regime")
    elif market_regime == "BEARISH":
        score -= 12
        reasons.append("bear regime")

    if atr_pct < 0.7:
        score -= 4
        reasons.append("too quiet")
    elif 0.7 <= atr_pct <= 6.0:
        score += 6
        reasons.append("atr healthy")
    else:
        score -= 5
        reasons.append("too volatile")

    score = max(0, min(100, score))

    if score >= 78 and market_regime == "BULLISH" and (breakout or near_support) and macd_diff_val > 0 and rsi_val <= 72:
        setup = "BUY WATCH"
    elif score >= 62 and market_regime != "BEARISH":
        setup = "WATCHLIST"
    else:
        setup = "AVOID"

    stop_loss = price - (atr_val * 1.5)
    take_profit = price + (atr_val * 3.0)
    confidence = min(100, max(0, score + (10 if setup == "BUY WATCH" else 0) - (8 if market_regime == "BEARISH" else 0)))
    buy_signal = setup == "BUY WATCH"

    return {
        "price": price,
        "score": score,
        "confidence": confidence,
        "rsi": rsi_val,
        "adx": adx_val,
        "volume_ratio": volume_ratio,
        "atr_pct": atr_pct,
        "market_regime": market_regime,
        "setup": setup,
        "reasons": ", ".join(reasons[:4]) if reasons else "n/a",
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "support_20": support_20_val,
        "resistance_20": resistance_20_val,
        "support_gap_pct": support_gap_pct,
        "resistance_gap_pct": resistance_gap_pct,
        "breakout": breakout,
        "near_support": near_support,
        "near_breakout": near_breakout,
        "buy_signal": buy_signal,
    }


def build_signal_signature(best, buy_candidates, mode):
    return json.dumps(
        {
            "mode": mode,
            "ticker": best["ticker"],
            "setup": best["setup"],
            "regime": best["market_regime"],
            "score_bucket": (best["score"] // 5) * 5,
            "buy_watch": best["setup"] == "BUY WATCH",
            "buy_count": len(buy_candidates),
            "buy_tickers": [item["ticker"] for item in buy_candidates[:3]],
        },
        sort_keys=True,
    )


def analyze(ticker):
    data = download_history(ticker)
    if data is None:
        return None

    df = build_feature_frame(data)
    if df is None or df.empty:
        print(f"Indikator kosong setelah dropna untuk {ticker}")
        return None

    latest = evaluate_row(df.iloc[-1])
    if latest is None:
        return None

    latest["ticker"] = ticker.replace(".JK", "")
    return latest


def run_backtest():
    from backtest import run_backtest as _run_backtest

    return _run_backtest()


def run_scan_once():
    results = []

    for stock in config.STOCKS:
        result = analyze(stock)
        if result:
            results.append(result)

    print(f"Total saham berhasil dianalisis: {len(results)}")

    if not results:
        msg = "Semua saham gagal dianalisis (cek koneksi / API)"
        print(msg)
        telegram_ok = send_telegram(msg)
        return {
            "status": "error",
            "message": msg,
            "telegram_sent": telegram_ok,
            "mode": SCAN_MODE,
            "top_count": 0,
            "buy_count": 0,
            "best": None,
            "top_tickers": [],
        }

    top_candidates = select_top_candidates(results)

    if not top_candidates:
        msg = "Tidak ada saham yang memenuhi kriteria"
        print(msg)
        telegram_ok = send_telegram(msg)
        return {
            "status": "no_candidates",
            "message": msg,
            "telegram_sent": telegram_ok,
            "mode": SCAN_MODE,
            "top_count": 0,
            "buy_count": 0,
            "best": None,
            "top_tickers": [],
        }

    trade_time = get_trading_time()
    buy_candidates = select_buy_candidates(results)
    best = buy_candidates[0] if buy_candidates else top_candidates[0]
    previous_state = load_last_signal_state()
    previous_tickers = previous_state.get("tickers", {})
    current_ticker_states = {item["ticker"]: build_ticker_state(item) for item in results}

    changed_items = []
    for ticker, current_state in current_ticker_states.items():
        previous_ticker_state = previous_tickers.get(ticker)
        if not previous_ticker_state or previous_ticker_state.get("signature") != current_state.get("signature"):
            changed_items.append((previous_ticker_state, current_state))

    if not changed_items:
        print("Tidak ada perubahan per saham, Telegram tidak dikirim")
        print("Scan selesai")
        return {
            "status": "unchanged",
            "message": "Tidak ada perubahan per saham, Telegram tidak dikirim",
            "telegram_sent": False,
            "mode": SCAN_MODE,
            "top_count": len(top_candidates),
            "buy_count": len(buy_candidates),
            "best": best,
            "top_tickers": [item["ticker"] for item in top_candidates[:config.TOP_N]],
            "changed_count": 0,
            "changed_tickers": [],
        }

    msg = build_changes_message(changed_items, trade_time)
    telegram_ok = send_telegram(msg)
    print("Scan selesai")
    if telegram_ok:
        save_last_signal_state({
            "tickers": current_ticker_states,
            "updated_at": datetime.now(JAKARTA_TZ).isoformat(),
        })
    else:
        print("Pesan Telegram gagal dikirim")

    return {
        "status": "sent" if telegram_ok else "telegram_failed",
        "message": msg,
        "telegram_sent": telegram_ok,
        "mode": SCAN_MODE,
        "top_count": len(top_candidates),
        "buy_count": len(buy_candidates),
        "best": best,
        "top_tickers": [item["ticker"] for item in top_candidates[:config.TOP_N]],
        "changed_count": len(changed_items),
        "changed_tickers": [current["ticker"] for _, current in changed_items],
    }


def run_forever(interval_seconds):
    interval_seconds = max(1, int(interval_seconds))
    print(f"Auto scan aktif. Interval: {interval_seconds} detik")

    while True:
        started_at = datetime.now(JAKARTA_TZ)
        print(f"\n[{started_at.strftime('%Y-%m-%d %H:%M:%S WIB')}] Mulai scan...")
        try:
            run_scan_once()
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"Error saat auto scan: {exc}")

        elapsed = (datetime.now(JAKARTA_TZ) - started_at).total_seconds()
        sleep_for = max(0, interval_seconds - elapsed)
        if sleep_for > 0:
            time.sleep(sleep_for)
