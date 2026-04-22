import pandas as pd

import config

logger = config.get_logger(__name__)

from scanner import (
    build_feature_frame,
    download_history,
    evaluate_row,
)


def backtest_stock(ticker):
    data = download_history(ticker)
    if data is None:
        return None

    df = build_feature_frame(data)
    if df is None or df.empty:
        logger.warning("Indikator kosong setelah dropna untuk %s", ticker)
        return None

    df = df.copy()
    for horizon in config.BACKTEST_HORIZONS:
        df[f"future_return_{horizon}d"] = df["close"].shift(-horizon) / df["close"] - 1

    df = df.dropna(subset=[f"future_return_{horizon}d" for horizon in config.BACKTEST_HORIZONS])
    if df.empty:
        return None

    evaluated = df.apply(evaluate_row, axis=1, result_type="expand")
    for horizon in config.BACKTEST_HORIZONS:
        evaluated[f"future_return_{horizon}d"] = df[f"future_return_{horizon}d"].astype(float)
    evaluated["ticker"] = ticker.replace(".JK", "")
    evaluated["signal"] = evaluated["setup"].eq("BUY WATCH")
    evaluated["positive"] = evaluated[f"future_return_{config.BACKTEST_HORIZON_DAYS}d"] > 0
    evaluated["score_bucket"] = pd.cut(
        evaluated["score"],
        bins=config.BACKTEST_BUCKETS,
        labels=config.BACKTEST_BUCKET_LABELS,
        include_lowest=True,
    )
    return evaluated


def summarize_signal_frame(df, horizon_days, threshold):
    horizon_col = f"future_return_{horizon_days}d"
    signal = df["score"] >= threshold
    signal_df = df[signal]

    if signal_df.empty:
        return {
            "threshold": threshold,
            "horizon": horizon_days,
            "signal_count": 0,
            "hit_rate": 0.0,
            "avg_return": 0.0,
            "median_return": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
        }

    returns = signal_df[horizon_col]
    wins = returns[returns > 0]
    losses = returns[returns <= 0]
    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())
    profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else float("inf")

    return {
        "threshold": threshold,
        "horizon": horizon_days,
        "signal_count": int(len(signal_df)),
        "hit_rate": float((returns > 0).mean() * 100),
        "avg_return": float(returns.mean() * 100),
        "median_return": float(returns.median() * 100),
        "profit_factor": float(profit_factor),
        "expectancy": float(returns.mean() * 100),
    }


def run_backtest():
    all_rows = []
    logger.info("Menjalankan backtest sederhana...")

    for stock in config.STOCKS:
        logger.info("Backtest %s...", stock)
        result = backtest_stock(stock)
        if result is not None and not result.empty:
            all_rows.append(result)

    if not all_rows:
        logger.error("Backtest gagal: tidak ada data yang bisa dievaluasi")
        return

    df = pd.concat(all_rows, ignore_index=True)
    if df.empty:
        logger.error("Backtest gagal: hasil gabungan kosong")
        return

    base_metrics = {}
    for horizon in config.BACKTEST_HORIZONS:
        col = f"future_return_{horizon}d"
        base_metrics[horizon] = {
            "hit_rate": float((df[col] > 0).mean() * 100),
            "avg_return": float(df[col].mean() * 100),
            "median_return": float(df[col].median() * 100),
        }

    signal_df = df[df["signal"]]
    signal_count = len(signal_df)
    signal_metrics = {}
    for horizon in config.BACKTEST_HORIZONS:
        col = f"future_return_{horizon}d"
        if signal_count:
            signal_metrics[horizon] = {
                "hit_rate": float((signal_df[col] > 0).mean() * 100),
                "avg_return": float(signal_df[col].mean() * 100),
                "median_return": float(signal_df[col].median() * 100),
            }
        else:
            signal_metrics[horizon] = {
                "hit_rate": 0.0,
                "avg_return": 0.0,
                "median_return": 0.0,
            }

    score_hit_rate = {}
    score_avg_return = {}
    horizon_col = f"future_return_{config.BACKTEST_HORIZON_DAYS}d"
    bucket_stats = df.groupby("score_bucket", dropna=True)[horizon_col].agg(["count", "mean", "median"])
    for bucket, group in df.groupby("score_bucket", dropna=True):
        if group.empty:
            continue
        score_hit_rate[str(bucket)] = float((group[horizon_col] > 0).mean() * 100)
        score_avg_return[str(bucket)] = float(group[horizon_col].mean() * 100)

    best_bucket = None
    best_bucket_return = None
    if not bucket_stats.empty:
        best_row = bucket_stats["mean"].idxmax()
        best_bucket = str(best_row)
        best_bucket_return = float(bucket_stats.loc[best_row, "mean"] * 100)

    sweep_rows = []
    for horizon in config.BACKTEST_HORIZONS:
        for threshold in config.BACKTEST_THRESHOLDS:
            sweep_rows.append(summarize_signal_frame(df, horizon, threshold))
    sweep_df = pd.DataFrame(sweep_rows)
    best_sweep = sweep_df.sort_values(
        ["avg_return", "hit_rate", "profit_factor", "signal_count"],
        ascending=[False, False, False, False],
    ).iloc[0]

    logger.info("=== BACKTEST SUMMARY ===")
    logger.info("Samples: %s | BUY WATCH count: %s", len(df), signal_count)
    logger.info(
        "Baseline %sD: hit %.2f%% | avg %.2f%% | median %.2f%%",
        config.BACKTEST_HORIZON_DAYS,
        base_metrics[config.BACKTEST_HORIZON_DAYS]["hit_rate"],
        base_metrics[config.BACKTEST_HORIZON_DAYS]["avg_return"],
        base_metrics[config.BACKTEST_HORIZON_DAYS]["median_return"],
    )
    logger.info(
        "BUY WATCH %sD: hit %.2f%% | avg %.2f%% | median %.2f%%",
        config.BACKTEST_HORIZON_DAYS,
        signal_metrics[config.BACKTEST_HORIZON_DAYS]["hit_rate"],
        signal_metrics[config.BACKTEST_HORIZON_DAYS]["avg_return"],
        signal_metrics[config.BACKTEST_HORIZON_DAYS]["median_return"],
    )
    if best_bucket is not None:
        logger.info("Best score bucket: %s (%.2f%%)", best_bucket, best_bucket_return)
    logger.info(
        "Best sweep: threshold >= %s | horizon %sD | avg %.2f%% | hit %.2f%% | pf %.2f",
        int(best_sweep["threshold"]),
        int(best_sweep["horizon"]),
        float(best_sweep["avg_return"]),
        float(best_sweep["hit_rate"]),
        float(best_sweep["profit_factor"]),
    )

    if signal_count:
        signal_tickers = (
            signal_df.groupby("ticker")
            .agg(
                count=(f"future_return_{config.BACKTEST_HORIZON_DAYS}d", "count"),
                hit_rate=("positive", "mean"),
                avg_return=(f"future_return_{config.BACKTEST_HORIZON_DAYS}d", "mean"),
            )
            .sort_values(["hit_rate", "avg_return"], ascending=False)
            .head(3)
        )
        logger.info("Top BUY WATCH tickers:")
        for ticker, row in signal_tickers.iterrows():
            logger.info(
                "%s | count %s | hit %.2f%% | avg %.2f%%",
                ticker,
                int(row["count"]),
                float(row["hit_rate"]) * 100,
                float(row["avg_return"]) * 100,
            )
