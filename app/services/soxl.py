"""SOXL examiner service: data fetching, indicator computation, and rules engine."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import yfinance as yf

# Constants
SOXL_TICKER = "SOXL"
FETCH_LOOKBACK = 250
GAP_LOOKBACK = 30
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
RSI_PERIOD = 14
CACHE_TTL = timedelta(minutes=15)

# In-memory cache
_cache: Dict[str, Any] = {"ts": None, "df": None}


@dataclass
class SoxlResult:
    """Container for computed SOXL values and derived signals."""

    df: pd.DataFrame
    computed: Dict[str, Any]


def fetch_soxl_data() -> Tuple[pd.DataFrame, bool]:
    """Fetch last `FETCH_LOOKBACK` daily OHLCV bars for SOXL with 15-minute caching.

    Returns (df, stale) where `stale` is True if returned from cache due to fetch failure.
    """
    now = datetime.utcnow()
    ts: Optional[datetime] = _cache.get("ts")
    if ts and _cache.get("df") is not None and now - ts < CACHE_TTL:
        return _cache["df"].copy(), False

    try:
        df = yf.download(SOXL_TICKER, period=f"{FETCH_LOOKBACK}d", auto_adjust=True, progress=False)
        if df.empty:
            raise RuntimeError("yfinance returned no data")
        # Flatten MultiIndex columns when yfinance returns ticker-level frames.
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        # Ensure columns: Open, High, Low, Close, Volume
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        _cache["df"] = df.copy()
        _cache["ts"] = now
        return df, False
    except Exception:
        # On failure, return last cached if available and mark stale
        if _cache.get("df") is not None:
            return _cache["df"].copy(), True
        raise


def _rsi_wilder(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Compute RSI using Wilder's smoothing (returns full series)."""
    delta = close.diff()
    up = delta.clip(lower=0.0)
    down = -1 * delta.clip(upper=0.0)

    gain = up.ewm(alpha=1 / period, adjust=False).mean()
    loss = down.ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_indicators(df: pd.DataFrame) -> SoxlResult:
    """Compute MACD, Signal, Histogram, RSI, SMAs, gap levels, and volume trends for SOXL.

    Returns a SoxlResult with the original dataframe and a computed dict of values.
    """
    df = df.copy()
    close = df["Close"]

    ema_fast = close.ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = close.ewm(span=MACD_SLOW, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=MACD_SIGNAL, adjust=False).mean()
    hist = macd - signal

    df["macd"] = macd
    df["signal"] = signal
    df["hist"] = hist
    df["rsi"] = _rsi_wilder(close)
    df["sma50"] = close.rolling(window=50, min_periods=1).mean()
    df["sma200"] = close.rolling(window=200, min_periods=1).mean()

    # Gap detection over last GAP_LOOKBACK bars
    recent = df.tail(GAP_LOOKBACK + 1)
    gap_level = None
    gap_held = False
    fresh_gap_held = False
    # iterate pairs
    rec = recent.reset_index()
    for i in range(1, len(rec)):
        prev = rec.loc[i - 1]
        cur = rec.loc[i]
        if cur["High"] < prev["Low"]:
            gap_level = float(prev["Low"])
            # held if the day's high stayed below reclaim level
            held = float(cur["High"]) < gap_level
            gap_held = held
            # if this is the most recent bar in df
            if cur.name == len(rec) - 1:
                fresh_gap_held = held
            # record the most recent gap and break
            break

    # Volume trends
    vol10 = df["Volume"].tail(10).mean()
    vol30 = df["Volume"].tail(30).mean()
    price_fall_vs_10 = df["Close"].iloc[-1] < df["Close"].iloc[-11] if len(df) > 11 else False
    vol_rising = vol10 > vol30 if not pd.isna(vol10) and not pd.isna(vol30) else False

    computed = {
        "latest": {
            "date": df.index[-1].strftime("%Y-%m-%d"),
            "close": float(df["Close"].iloc[-1]),
            "prev_close": float(df["Close"].iloc[-2]) if len(df) > 1 else None,
        },
        "macd": float(df["macd"].iloc[-1]),
        "signal": float(df["signal"].iloc[-1]),
        "hist": float(df["hist"].iloc[-1]),
        "hist_prev": float(df["hist"].iloc[-2]) if len(df) > 1 else None,
        "rsi": float(df["rsi"].iloc[-1]),
        "sma50": float(df["sma50"].iloc[-1]),
        "sma200": float(df["sma200"].iloc[-1]),
        "gap_level": gap_level,
        "gap_held": gap_held,
        "fresh_gap_held": fresh_gap_held,
        "vol10": float(vol10) if not pd.isna(vol10) else None,
        "vol30": float(vol30) if not pd.isna(vol30) else None,
        "price_falling_vs_10": price_fall_vs_10,
        "vol_rising": vol_rising,
        "stale": False,
    }

    return SoxlResult(df=df, computed=computed)


def evaluate_rules(result: SoxlResult, stop_price: Optional[float] = None) -> Dict[str, Any]:
    """Evaluate rules (E0..E3, X1..X3) on the latest completed bar and return verdict and diagnostics."""
    c = result.computed

    # Early warning E0: histogram contracting for two consecutive bars
    hist = result.df["hist"].values
    e0 = False
    if len(hist) >= 3:
        e0 = abs(hist[-1]) < abs(hist[-2]) and abs(hist[-2]) < abs(hist[-3])

    e1 = c["macd"] > c["signal"]
    e2 = c["rsi"] > 40.0
    # E3: latest close > gap reclaim level, or pass if no gap
    if c["gap_level"] is None:
        e3 = True
    else:
        e3 = c["latest"]["close"] > c["gap_level"]

    # Exit triggers
    x1 = c["macd"] < c["signal"]
    x2 = False
    if stop_price is not None:
        x2 = c["latest"]["close"] < float(stop_price)
    x3 = bool(c["fresh_gap_held"])

    verdict = "WAIT"
    if x1 or x2 or x3:
        verdict = "SELL"
    elif e1 and e2 and e3:
        verdict = "BUY"

    diagnostics = {
        "E0_histogram_contracting": e0,
        "E1_macd_above_signal": e1,
        "E2_rsi_gt_40": e2,
        "E3_above_gap_reclaim": e3,
        "X1_macd_below_signal": x1,
        "X2_below_stop": x2,
        "X3_fresh_gap_held": x3,
        "verdict": verdict,
    }

    return diagnostics
