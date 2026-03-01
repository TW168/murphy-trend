"""
Murphy-based technical analysis engine.
Implements indicators and signals from John J. Murphy's
'Technical Analysis of the Financial Markets'.
"""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from app.services.market_data import fetch_stock_data, fetch_ticker_info
from app.services.patterns import detect_patterns


# ---------------------------------------------------------------------------
# Indicator calculations
# ---------------------------------------------------------------------------


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series, fast=12, slow=26, signal=9) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _bbands(series: pd.Series, period=20, std_dev=2) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = series.rolling(period).mean()
    std = series.rolling(period).std(ddof=0)
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period=14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


# ---------------------------------------------------------------------------
# Support / Resistance
# ---------------------------------------------------------------------------


def _find_swing_points(df: pd.DataFrame, window: int = 10) -> tuple[list[float], list[float]]:
    """Identify swing highs (resistance) and swing lows (support) in last 120 bars."""
    data = df.tail(120)
    highs, lows = [], []
    for i in range(window, len(data) - window):
        hi = data["High"].iloc[i]
        lo = data["Low"].iloc[i]
        if hi == data["High"].iloc[i - window: i + window + 1].max():
            highs.append(round(float(hi), 2))
        if lo == data["Low"].iloc[i - window: i + window + 1].min():
            lows.append(round(float(lo), 2))

    # Cluster nearby levels (within 1%)
    def cluster(levels: list[float]) -> list[float]:
        if not levels:
            return []
        levels = sorted(set(levels))
        clustered: list[float] = [levels[0]]
        for lvl in levels[1:]:
            if abs(lvl - clustered[-1]) / clustered[-1] > 0.01:
                clustered.append(lvl)
            else:
                clustered[-1] = round((clustered[-1] + lvl) / 2, 2)
        return clustered

    return cluster(highs)[-4:], cluster(lows)[:4]


# ---------------------------------------------------------------------------
# Fibonacci retracements
# ---------------------------------------------------------------------------


def _fibonacci_levels(swing_low: float, swing_high: float) -> dict[str, float]:
    diff = swing_high - swing_low
    return {
        "0.0%": round(swing_high, 2),
        "23.6%": round(swing_high - 0.236 * diff, 2),
        "38.2%": round(swing_high - 0.382 * diff, 2),
        "50.0%": round(swing_high - 0.500 * diff, 2),
        "61.8%": round(swing_high - 0.618 * diff, 2),
        "100.0%": round(swing_low, 2),
    }


# ---------------------------------------------------------------------------
# Signal scoring
# ---------------------------------------------------------------------------


def _score_trend(df: pd.DataFrame, sma50: float | None, sma200: float | None) -> list[dict]:
    signals = []
    close = df["Close"]
    price = float(close.iloc[-1])

    # Higher highs / higher lows (last 20 bars)
    recent = close.tail(20)
    mid = len(recent) // 2
    first_half_max = float(recent.iloc[:mid].max())
    second_half_max = float(recent.iloc[mid:].max())
    first_half_min = float(recent.iloc[:mid].min())
    second_half_min = float(recent.iloc[mid:].min())

    if second_half_max > first_half_max and second_half_min > first_half_min:
        signals.append({
            "name": "Price Trend",
            "value": "Higher Highs & Higher Lows",
            "interpretation": "Uptrend structure confirmed — each rally exceeds prior high",
            "direction": "bullish",
            "score": 1.0,
            "weight": 1.5,
        })
    elif second_half_max < first_half_max and second_half_min < first_half_min:
        signals.append({
            "name": "Price Trend",
            "value": "Lower Highs & Lower Lows",
            "interpretation": "Downtrend structure — sellers in control",
            "direction": "bearish",
            "score": -1.0,
            "weight": 1.5,
        })
    else:
        signals.append({
            "name": "Price Trend",
            "value": "Sideways / Consolidation",
            "interpretation": "No clear trend direction; market is range-bound",
            "direction": "neutral",
            "score": 0.0,
            "weight": 1.5,
        })

    if sma50 is not None:
        dir_ = "bullish" if price > sma50 else "bearish"
        signals.append({
            "name": "Price vs 50-Day MA",
            "value": f"${price:.2f} {'above' if price > sma50 else 'below'} SMA50 (${sma50:.2f})",
            "interpretation": f"Price {'above' if price > sma50 else 'below'} 50-day average — intermediate trend {'up' if price > sma50 else 'down'}",
            "direction": dir_,
            "score": 1.0 if price > sma50 else -1.0,
            "weight": 1.0,
        })

    if sma200 is not None:
        dir_ = "bullish" if price > sma200 else "bearish"
        signals.append({
            "name": "Price vs 200-Day MA",
            "value": f"${price:.2f} {'above' if price > sma200 else 'below'} SMA200 (${sma200:.2f})",
            "interpretation": f"Price {'above' if price > sma200 else 'below'} 200-day average — long-term trend {'up' if price > sma200 else 'down'}",
            "direction": dir_,
            "score": 1.0 if price > sma200 else -1.0,
            "weight": 1.0,
        })

    if sma50 is not None and sma200 is not None:
        # Golden / Death cross — check recent crossover (last 10 days)
        sma50_series = _sma(df["Close"], 50).tail(10)
        sma200_series = _sma(df["Close"], 200).tail(10)
        valid = sma50_series.dropna()
        valid200 = sma200_series.dropna()
        if len(valid) >= 2 and len(valid200) >= 2:
            crossed_up = valid.iloc[-2] < valid200.iloc[-2] and valid.iloc[-1] > valid200.iloc[-1]
            crossed_dn = valid.iloc[-2] > valid200.iloc[-2] and valid.iloc[-1] < valid200.iloc[-1]
            if crossed_up:
                signals.append({
                    "name": "MA Cross",
                    "value": "Golden Cross",
                    "interpretation": "50-day MA crossed above 200-day — major bullish signal",
                    "direction": "bullish",
                    "score": 1.0,
                    "weight": 2.0,
                })
            elif crossed_dn:
                signals.append({
                    "name": "MA Cross",
                    "value": "Death Cross",
                    "interpretation": "50-day MA crossed below 200-day — major bearish signal",
                    "direction": "bearish",
                    "score": -1.0,
                    "weight": 2.0,
                })
            else:
                above = sma50 > sma200
                signals.append({
                    "name": "MA Alignment",
                    "value": f"SMA50 {'>' if above else '<'} SMA200",
                    "interpretation": f"No recent cross — 50-day {'above' if above else 'below'} 200-day MA",
                    "direction": "bullish" if above else "bearish",
                    "score": 0.5 if above else -0.5,
                    "weight": 2.0,
                })

    return signals


def _score_rsi(rsi_val: float | None) -> dict | None:
    if rsi_val is None:
        return None
    if rsi_val >= 70:
        return {
            "name": "RSI (14)",
            "value": f"{rsi_val:.1f}",
            "interpretation": f"Overbought ({rsi_val:.0f}) — momentum stretched; watch for reversal or pullback",
            "direction": "bearish",
            "score": -0.75,
            "weight": 1.5,
        }
    if rsi_val <= 30:
        return {
            "name": "RSI (14)",
            "value": f"{rsi_val:.1f}",
            "interpretation": f"Oversold ({rsi_val:.0f}) — selling exhausted; potential bounce or reversal",
            "direction": "bullish",
            "score": 0.75,
            "weight": 1.5,
        }
    if rsi_val >= 55:
        return {
            "name": "RSI (14)",
            "value": f"{rsi_val:.1f}",
            "interpretation": f"Bullish momentum ({rsi_val:.0f}) — RSI in bull range",
            "direction": "bullish",
            "score": 0.35,
            "weight": 1.5,
        }
    if rsi_val <= 45:
        return {
            "name": "RSI (14)",
            "value": f"{rsi_val:.1f}",
            "interpretation": f"Bearish momentum ({rsi_val:.0f}) — RSI in bear range",
            "direction": "bearish",
            "score": -0.35,
            "weight": 1.5,
        }
    return {
        "name": "RSI (14)",
        "value": f"{rsi_val:.1f}",
        "interpretation": f"Neutral ({rsi_val:.0f}) — no extreme momentum",
        "direction": "neutral",
        "score": 0.0,
        "weight": 1.5,
    }


def _score_macd(macd_line: float | None, signal_line: float | None, hist: float | None, prev_hist: float | None) -> list[dict]:
    signals = []
    if macd_line is None or signal_line is None:
        return signals
    above = macd_line > signal_line
    signals.append({
        "name": "MACD Signal",
        "value": f"MACD {macd_line:.3f} / Signal {signal_line:.3f}",
        "interpretation": f"MACD {'above' if above else 'below'} signal line — {'bullish' if above else 'bearish'} momentum",
        "direction": "bullish" if above else "bearish",
        "score": 1.0 if above else -1.0,
        "weight": 1.5,
    })
    if hist is not None and prev_hist is not None:
        expanding = abs(hist) > abs(prev_hist) and np.sign(hist) == np.sign(prev_hist)
        if expanding:
            signals.append({
                "name": "MACD Histogram",
                "value": f"Expanding ({'↑' if hist > 0 else '↓'})",
                "interpretation": f"Histogram expanding — {'bullish' if hist > 0 else 'bearish'} momentum accelerating",
                "direction": "bullish" if hist > 0 else "bearish",
                "score": 0.5 if hist > 0 else -0.5,
                "weight": 1.0,
            })
        else:
            signals.append({
                "name": "MACD Histogram",
                "value": f"Contracting ({'↑' if hist > 0 else '↓'})",
                "interpretation": f"Histogram contracting — {'bullish' if hist > 0 else 'bearish'} momentum weakening",
                "direction": "neutral",
                "score": 0.1 if hist > 0 else -0.1,
                "weight": 1.0,
            })
    return signals


def _score_bollinger(price: float, bb_upper: float | None, bb_mid: float | None, bb_lower: float | None) -> dict | None:
    if bb_upper is None or bb_lower is None or bb_mid is None:
        return None
    band_width = bb_upper - bb_lower
    pct_b = (price - bb_lower) / band_width if band_width > 0 else 0.5
    if pct_b >= 0.9:
        return {
            "name": "Bollinger Bands",
            "value": f"%B {pct_b:.2f} — near upper band",
            "interpretation": "Price at upper Bollinger Band — overbought or strong trend breakout",
            "direction": "bearish",
            "score": -0.5,
            "weight": 1.0,
        }
    if pct_b <= 0.1:
        return {
            "name": "Bollinger Bands",
            "value": f"%B {pct_b:.2f} — near lower band",
            "interpretation": "Price at lower Bollinger Band — oversold or downside breakout",
            "direction": "bullish",
            "score": 0.5,
            "weight": 1.0,
        }
    return {
        "name": "Bollinger Bands",
        "value": f"%B {pct_b:.2f} — mid-range",
        "interpretation": "Price within normal Bollinger Band range",
        "direction": "neutral",
        "score": 0.0,
        "weight": 1.0,
    }


def _score_volume(df: pd.DataFrame) -> dict | None:
    if "Volume" not in df.columns:
        return None
    close = df["Close"]
    volume = df["Volume"]
    recent = df.tail(10)
    price_up = float(recent["Close"].iloc[-1]) > float(recent["Close"].iloc[0])
    vol_avg_recent = float(recent["Volume"].mean())
    vol_avg_prior = float(df.tail(30).head(20)["Volume"].mean())
    vol_expanding = vol_avg_recent > vol_avg_prior

    if price_up and vol_expanding:
        return {
            "name": "Volume Trend",
            "value": "Rising price + rising volume",
            "interpretation": "Volume confirming rally — institutional participation increasing",
            "direction": "bullish",
            "score": 0.75,
            "weight": 1.0,
        }
    if price_up and not vol_expanding:
        return {
            "name": "Volume Trend",
            "value": "Rising price + declining volume",
            "interpretation": "Rally on weak volume — distribution signal; potential exhaustion",
            "direction": "bearish",
            "score": -0.5,
            "weight": 1.0,
        }
    if not price_up and vol_expanding:
        return {
            "name": "Volume Trend",
            "value": "Falling price + rising volume",
            "interpretation": "Selling pressure confirmed by volume — bearish",
            "direction": "bearish",
            "score": -0.75,
            "weight": 1.0,
        }
    return {
        "name": "Volume Trend",
        "value": "Falling price + declining volume",
        "interpretation": "Declining price on low volume — potential selling exhaustion",
        "direction": "neutral",
        "score": 0.0,
        "weight": 1.0,
    }


def _score_obv(df: pd.DataFrame) -> dict | None:
    if "Volume" not in df.columns:
        return None
    obv = _obv(df["Close"], df["Volume"])
    recent_obv = obv.tail(20)
    if len(recent_obv) < 4:
        return None
    trend_up = float(recent_obv.iloc[-1]) > float(recent_obv.iloc[0])
    return {
        "name": "OBV",
        "value": f"{'Rising' if trend_up else 'Declining'}",
        "interpretation": f"On-Balance Volume {'rising — buying pressure accumulating' if trend_up else 'declining — selling pressure dominant'}",
        "direction": "bullish" if trend_up else "bearish",
        "score": 0.5 if trend_up else -0.5,
        "weight": 1.0,
    }


# ---------------------------------------------------------------------------
# Price targets
# ---------------------------------------------------------------------------


def _calculate_targets(
    df: pd.DataFrame,
    outlook_score: float,
    atr_val: float | None,
) -> list[dict]:
    price = float(df["Close"].iloc[-1])
    if atr_val is None or atr_val == 0:
        atr_val = price * 0.02  # 2% fallback

    atr_pct = atr_val / price
    results = []
    for days in [30, 60, 90]:
        multiplier = outlook_score * 1.5
        t_factor = (days / 252) ** 0.5
        expected_move = atr_pct * t_factor * 1.5
        directional = price * multiplier * (days / 252)
        target = price + directional
        spread = price * expected_move
        low = target - spread
        high = target + spread
        direction = "bullish" if outlook_score > 0.15 else ("bearish" if outlook_score < -0.15 else "neutral")
        results.append({
            "days": days,
            "low": round(max(low, 0.01), 2),
            "target": round(max(target, 0.01), 2),
            "high": round(max(high, 0.01), 2),
            "direction": direction,
        })
    return results


# ---------------------------------------------------------------------------
# Plotly chart
# ---------------------------------------------------------------------------


def _find_chart_gaps(df: pd.DataFrame, min_pct: float = 0.75) -> list[dict]:
    """Return true price gaps in df for chart drawing (Murphy definition).

    A true gap means the entire session range does not overlap with the prior
    session range — no trading occurred in the gap zone.
      Gap up:   curr["Low"]  > prev["High"]
      Gap down: curr["High"] < prev["Low"]

    y0/y1 define the unfilled price zone between the two sessions.
    """
    gaps = []
    for i in range(1, len(df)):
        prev = df.iloc[i - 1]
        curr = df.iloc[i]
        prev_high = float(prev["High"])
        prev_low = float(prev["Low"])
        curr_high = float(curr["High"])
        curr_low = float(curr["Low"])

        if curr_low > prev_high:
            gap_pct = (curr_low - prev_high) / prev_high * 100
            if gap_pct >= min_pct:
                gaps.append({
                    "date_prev": df.index[i - 1],
                    "date": df.index[i],
                    "y0": prev_high,
                    "y1": curr_low,
                    "direction": "up",
                })
        elif curr_high < prev_low:
            gap_pct = (prev_low - curr_high) / prev_low * 100
            if gap_pct >= min_pct:
                gaps.append({
                    "date_prev": df.index[i - 1],
                    "date": df.index[i],
                    "y0": curr_high,
                    "y1": prev_low,
                    "direction": "down",
                })
    return gaps


def _build_chart(df: pd.DataFrame, sma50: pd.Series, sma200: pd.Series,
                 bb_upper: pd.Series, bb_mid: pd.Series, bb_lower: pd.Series,
                 macd_line: pd.Series, signal_line: pd.Series, macd_hist: pd.Series,
                 rsi_series: pd.Series,
                 support: list[float], resistance: list[float],
                 gaps: list[dict] | None = None) -> str:
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.60, 0.20, 0.20],
        subplot_titles=("Price & Indicators", "MACD", "RSI (14)"),
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        name="OHLC",
        increasing_line_color="#2a9d8f",
        decreasing_line_color="#e63946",
        showlegend=False,
    ), row=1, col=1)

    # SMAs
    fig.add_trace(go.Scatter(x=df.index, y=sma50, name="SMA 50", line=dict(color="#277da1", width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=sma200, name="SMA 200", line=dict(color="#f4a261", width=1.5)), row=1, col=1)

    # Bollinger Bands
    fig.add_trace(go.Scatter(x=df.index, y=bb_upper, name="BB Upper",
                             line=dict(color="rgba(128,128,128,0.4)", width=1), showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=bb_lower, name="BB Lower",
                             fill="tonexty", fillcolor="rgba(128,128,128,0.08)",
                             line=dict(color="rgba(128,128,128,0.4)", width=1), showlegend=False), row=1, col=1)

    # Support / Resistance lines
    for lvl in support:
        fig.add_hline(y=lvl, line_dash="dot", line_color="#2a9d8f", line_width=1,
                      annotation_text=f"S {lvl:.2f}", annotation_position="right", row=1, col=1)
    for lvl in resistance:
        fig.add_hline(y=lvl, line_dash="dot", line_color="#e63946", line_width=1,
                      annotation_text=f"R {lvl:.2f}", annotation_position="right", row=1, col=1)

    # Gap shading
    for g in (gaps or []):
        color = "rgba(42,157,143,0.15)" if g["direction"] == "up" else "rgba(230,57,70,0.15)"
        border = "#2a9d8f" if g["direction"] == "up" else "#e63946"
        label = f"Gap {'Up' if g['direction'] == 'up' else 'Down'} +{g['y1'] - g['y0']:.2f}" if g["direction"] == "up" else f"Gap Down -{g['y1'] - g['y0']:.2f}"
        fig.add_shape(
            type="rect",
            x0=g["date_prev"], x1=g["date"],
            y0=g["y0"], y1=g["y1"],
            fillcolor=color,
            line=dict(color=border, width=0.5, dash="dot"),
            row=1, col=1,
        )
        fig.add_annotation(
            x=g["date"], y=(g["y0"] + g["y1"]) / 2,
            text=label,
            showarrow=False,
            font=dict(size=9, color=border),
            xanchor="left",
            bgcolor="rgba(255,255,255,0.7)",
            borderpad=2,
            row=1, col=1,
        )

    # MACD
    hist_colors = ["#2a9d8f" if v >= 0 else "#e63946" for v in macd_hist.fillna(0)]
    fig.add_trace(go.Bar(x=df.index, y=macd_hist, name="Histogram",
                         marker_color=hist_colors, showlegend=False), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=macd_line, name="MACD",
                             line=dict(color="#277da1", width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=signal_line, name="Signal",
                             line=dict(color="#f4a261", width=1.5)), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=rsi_series, name="RSI",
                             line=dict(color="#9c6644", width=1.5)), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="#e63946", line_width=1, row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#2a9d8f", line_width=1, row=3, col=1)

    fig.update_layout(
        height=620,
        margin=dict(l=10, r=80, t=30, b=10),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(family="Inter, sans-serif", size=12, color="#2b2d42"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#f0f0f0", zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#f0f0f0", zeroline=False)

    return fig.to_json()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def analyze_ticker(ticker: str) -> dict[str, Any]:
    """
    Full Murphy technical analysis. Returns a dict matching AnalysisResponse schema.
    """
    ticker = ticker.upper().strip()
    df = fetch_stock_data(ticker, period="2y")
    info = fetch_ticker_info(ticker)

    close = df["Close"]
    price = float(close.iloc[-1])
    prev_price = float(close.iloc[-2]) if len(close) > 1 else price
    price_change = price - prev_price
    price_change_pct = (price_change / prev_price * 100) if prev_price else 0.0

    # --- Indicators ---
    sma50_s = _sma(close, 50)
    sma200_s = _sma(close, 200)
    rsi_s = _rsi(close)
    macd_line_s, signal_line_s, hist_s = _macd(close)
    bb_upper_s, bb_mid_s, bb_lower_s = _bbands(close)
    atr_s = _atr(df["High"], df["Low"], close)

    sma50 = float(sma50_s.iloc[-1]) if not pd.isna(sma50_s.iloc[-1]) else None
    sma200 = float(sma200_s.iloc[-1]) if not pd.isna(sma200_s.iloc[-1]) else None
    rsi_val = float(rsi_s.iloc[-1]) if not pd.isna(rsi_s.iloc[-1]) else None
    macd_val = float(macd_line_s.iloc[-1]) if not pd.isna(macd_line_s.iloc[-1]) else None
    signal_val = float(signal_line_s.iloc[-1]) if not pd.isna(signal_line_s.iloc[-1]) else None
    hist_val = float(hist_s.iloc[-1]) if not pd.isna(hist_s.iloc[-1]) else None
    prev_hist = float(hist_s.iloc[-2]) if len(hist_s) > 1 and not pd.isna(hist_s.iloc[-2]) else None
    bb_upper = float(bb_upper_s.iloc[-1]) if not pd.isna(bb_upper_s.iloc[-1]) else None
    bb_mid = float(bb_mid_s.iloc[-1]) if not pd.isna(bb_mid_s.iloc[-1]) else None
    bb_lower = float(bb_lower_s.iloc[-1]) if not pd.isna(bb_lower_s.iloc[-1]) else None
    atr_val = float(atr_s.iloc[-1]) if not pd.isna(atr_s.iloc[-1]) else None

    # --- Signals ---
    raw_signals: list[dict] = []
    raw_signals.extend(_score_trend(df, sma50, sma200))
    rsi_sig = _score_rsi(rsi_val)
    if rsi_sig:
        raw_signals.append(rsi_sig)
    raw_signals.extend(_score_macd(macd_val, signal_val, hist_val, prev_hist))
    bb_sig = _score_bollinger(price, bb_upper, bb_mid, bb_lower)
    if bb_sig:
        raw_signals.append(bb_sig)
    vol_sig = _score_volume(df)
    if vol_sig:
        raw_signals.append(vol_sig)
    obv_sig = _score_obv(df)
    if obv_sig:
        raw_signals.append(obv_sig)

    # --- Pattern signals (contribute to score) ---
    pattern_signals = detect_patterns(df)
    raw_signals.extend(pattern_signals)

    # Weighted score
    total_weight = sum(s["weight"] for s in raw_signals)
    weighted_sum = sum(s["score"] * s["weight"] for s in raw_signals)
    outlook_score = round(float(weighted_sum / total_weight) if total_weight > 0 else 0.0, 3)
    outlook_score = max(-1.0, min(1.0, outlook_score))

    if outlook_score > 0.2:
        outlook = "bullish"
    elif outlook_score < -0.2:
        outlook = "bearish"
    else:
        outlook = "neutral"

    # Clean signals for output (remove internal score/weight keys)
    # Separate pattern signals from indicator signals for dedicated display
    indicator_signals = [s for s in raw_signals if s not in pattern_signals]
    signals_out = [
        {k: v for k, v in s.items() if k not in ("score", "weight")}
        for s in indicator_signals
    ]
    patterns_out = [
        {k: v for k, v in s.items() if k not in ("score", "weight")}
        for s in pattern_signals
    ]

    # --- Support / Resistance ---
    resistance, support = _find_swing_points(df)
    current_resist = [r for r in resistance if r > price]
    current_support = [s for s in support if s < price]

    # --- Fibonacci ---
    recent_high = float(df["High"].tail(60).max())
    recent_low = float(df["Low"].tail(60).min())
    fib_levels = _fibonacci_levels(recent_low, recent_high)

    # --- Predictions ---
    predictions = _calculate_targets(df, outlook_score, atr_val)

    # --- Chart ---
    chart_gaps = _find_chart_gaps(df)

    # Add chart gaps as pattern cards (clickable, in sync with chart shapes)
    for g in chart_gaps[-5:]:
        direction = "bullish" if g["direction"] == "up" else "bearish"
        fill = "rgba(42,157,143,0.22)" if direction == "bullish" else "rgba(230,57,70,0.22)"
        border = "#2a9d8f" if direction == "bullish" else "#e63946"
        gap_pct = abs(g["y1"] - g["y0"]) / (g["y0"] if g["direction"] == "up" else g["y1"]) * 100
        sign = "+" if g["direction"] == "up" else "-"
        label = f"Gap {'Up' if g['direction'] == 'up' else 'Down'} {sign}{gap_pct:.1f}%"
        patterns_out.append({
            "name": f"Gap {'Up' if g['direction'] == 'up' else 'Down'}",
            "value": f"${g['y0']:.2f} → ${g['y1']:.2f} ({sign}{gap_pct:.1f}%)",
            "interpretation": f"Unfilled gap on {g['date'].strftime('%b %d, %Y')} — the gap zone is shaded on the chart above",
            "direction": direction,
            "chart_data": {
                "x0": g["date_prev"].strftime("%Y-%m-%d"),
                "x1": g["date"].strftime("%Y-%m-%d"),
                "y0": g["y0"],
                "y1": g["y1"],
                "label": label,
                "fill": fill,
                "border": border,
            },
        })

    chart_json = _build_chart(
        df, sma50_s, sma200_s,
        bb_upper_s, bb_mid_s, bb_lower_s,
        macd_line_s, signal_line_s, hist_s,
        rsi_s,
        current_support[:2], current_resist[:2],
        gaps=chart_gaps,
    )

    return {
        "ticker": ticker,
        "company_name": info["company_name"],
        "sector": info["sector"],
        "current_price": round(price, 2),
        "price_change": round(price_change, 2),
        "price_change_pct": round(price_change_pct, 2),
        "sma50": round(sma50, 2) if sma50 else None,
        "sma200": round(sma200, 2) if sma200 else None,
        "rsi": round(rsi_val, 1) if rsi_val else None,
        "macd": round(macd_val, 4) if macd_val else None,
        "macd_signal": round(signal_val, 4) if signal_val else None,
        "bb_upper": round(bb_upper, 2) if bb_upper else None,
        "bb_lower": round(bb_lower, 2) if bb_lower else None,
        "outlook": outlook,
        "outlook_score": outlook_score,
        "signals": signals_out,
        "patterns": patterns_out,
        "predictions": predictions,
        "support_levels": current_support,
        "resistance_levels": current_resist,
        "fib_levels": fib_levels,
        "chart_json": chart_json,
        "last_updated": datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%dT%H:%M"),
    }
