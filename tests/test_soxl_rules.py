import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from app.services.soxl import compute_indicators, evaluate_rules


def make_df_from_closes(closes, start=None):
    if start is None:
        start = datetime.utcnow().date() - timedelta(days=len(closes))
    dates = pd.bdate_range(start=start, periods=len(closes))
    df = pd.DataFrame({
        "Open": closes,
        "High": np.array(closes) * 1.01,
        "Low": np.array(closes) * 0.99,
        "Close": closes,
        "Volume": np.linspace(1000, 2000, len(closes)),
    }, index=dates)
    return df


def test_buy_case():
    # increasing close series -> MACD positive, RSI high
    closes = list(np.linspace(10, 20, 260))
    df = make_df_from_closes(closes)
    res = compute_indicators(df)
    diag = evaluate_rules(res)
    assert diag["verdict"] == "BUY"


def test_sell_case_macd_cross_down():
    # create data with recent downtrend to force MACD < signal
    up = list(np.linspace(10, 20, 200))
    down = list(np.linspace(20, 5, 60))
    closes = up + down
    df = make_df_from_closes(closes)
    res = compute_indicators(df)
    diag = evaluate_rules(res)
    assert diag["verdict"] == "SELL"


def test_wait_case():
    # flat to slightly up should not meet all entry conditions
    closes = list(10 + np.sin(np.linspace(0, 3, 260)))
    df = make_df_from_closes(closes)
    res = compute_indicators(df)
    diag = evaluate_rules(res)
    assert diag["verdict"] in {"WAIT", "SELL"}
