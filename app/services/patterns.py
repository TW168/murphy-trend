"""
Classical chart pattern recognition.
Implements patterns from John J. Murphy's 'Technical Analysis of the Financial Markets'.
Each detector returns a signal dict compatible with the analysis.py scoring system,
or None if the pattern is not present.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _local_peaks(series: pd.Series, window: int = 5) -> list[int]:
    """Return positional indices of local maxima within `series`."""
    vals = series.values
    peaks = []
    for i in range(window, len(vals) - window):
        if vals[i] == max(vals[i - window : i + window + 1]):
            peaks.append(i)
    return peaks


def _local_troughs(series: pd.Series, window: int = 5) -> list[int]:
    """Return positional indices of local minima within `series`."""
    vals = series.values
    troughs = []
    for i in range(window, len(vals) - window):
        if vals[i] == min(vals[i - window : i + window + 1]):
            troughs.append(i)
    return troughs


def _linreg_slope_pct(series: pd.Series) -> float:
    """Linear regression slope normalised to mean (slope per bar as fraction of price)."""
    x = np.arange(len(series), dtype=float)
    y = series.values.astype(float)
    if len(y) < 3:
        return 0.0
    slope = float(np.polyfit(x, y, 1)[0])
    mean = float(series.mean())
    return slope / mean if mean != 0 else 0.0


def _fmt(ts) -> str:
    """Format a pandas Timestamp as ISO date string for Plotly."""
    return ts.strftime("%Y-%m-%d")


def _chart_colors(direction: str) -> tuple[str, str]:
    """Return (fillcolor, bordercolor) for a given pattern direction."""
    if direction == "bullish":
        return "rgba(42,157,143,0.22)", "#2a9d8f"
    if direction == "bearish":
        return "rgba(230,57,70,0.22)", "#e63946"
    return "rgba(244,162,97,0.22)", "#f4a261"


# ---------------------------------------------------------------------------
# Reversal patterns
# ---------------------------------------------------------------------------


def _detect_head_and_shoulders(df: pd.DataFrame) -> dict | None:
    """
    Bearish Head & Shoulders — 3 peaks where the middle (head) is clearly highest,
    shoulders roughly equal. Also detects Inverse H&S (bullish).
    Uses last 80 bars.
    """
    data = df.tail(80)
    if len(data) < 30:
        return None

    # --- Bearish H&S ---
    peaks = _local_peaks(data["High"], window=5)
    if len(peaks) >= 3:
        p_idx = peaks[-3:]
        p1, p2, p3 = (float(data["High"].iloc[i]) for i in p_idx)
        shoulder_avg = (p1 + p3) / 2
        # Head must be higher than both shoulders by ≥1%
        if p2 > p1 * 1.01 and p2 > p3 * 1.01:
            # Shoulders within 5% of each other
            if abs(p1 - p3) / shoulder_avg < 0.05:
                seg1_low = float(data["Low"].iloc[p_idx[0] : p_idx[1]].min())
                seg2_low = float(data["Low"].iloc[p_idx[1] : p_idx[2]].min())
                neckline = (seg1_low + seg2_low) / 2
                target = neckline - (p2 - neckline)
                current = float(data["Close"].iloc[-1])
                broke = current < neckline
                near = abs(current - neckline) / neckline < 0.03
                if broke:
                    interp = f"Neckline ${neckline:.2f} broken — measured-move target ${target:.2f}"
                elif near:
                    interp = f"Approaching neckline ${neckline:.2f} — watch for breakdown toward ${target:.2f}"
                else:
                    interp = (
                        f"Head ${p2:.2f}, shoulders ~${shoulder_avg:.2f}, "
                        f"neckline ${neckline:.2f} — bearish if neckline breaks"
                    )
                fill, border = _chart_colors("bearish")
                return {
                    "name": "Head & Shoulders",
                    "value": f"Head ${p2:.2f} / Shoulders ~${shoulder_avg:.2f} / Neckline ${neckline:.2f}",
                    "interpretation": interp,
                    "direction": "bearish",
                    "score": -1.0 if broke else -0.6,
                    "weight": 1.5,
                    "chart_data": {
                        "x0": _fmt(data.index[p_idx[0]]),
                        "x1": _fmt(data.index[-1]),
                        "y0": round(neckline * 0.99, 2),
                        "y1": round(p2 * 1.01, 2),
                        "label": "Head & Shoulders",
                        "fill": fill,
                        "border": border,
                    },
                }

    # --- Bullish Inverse H&S ---
    troughs = _local_troughs(data["Low"], window=5)
    if len(troughs) >= 3:
        t_idx = troughs[-3:]
        t1, t2, t3 = (float(data["Low"].iloc[i]) for i in t_idx)
        shoulder_avg = (t1 + t3) / 2
        if t2 < t1 * 0.99 and t2 < t3 * 0.99:
            if abs(t1 - t3) / shoulder_avg < 0.05:
                seg1_high = float(data["High"].iloc[t_idx[0] : t_idx[1]].max())
                seg2_high = float(data["High"].iloc[t_idx[1] : t_idx[2]].max())
                neckline = (seg1_high + seg2_high) / 2
                target = neckline + (neckline - t2)
                current = float(data["Close"].iloc[-1])
                broke = current > neckline
                near = abs(current - neckline) / neckline < 0.03
                if broke:
                    interp = f"Neckline ${neckline:.2f} cleared — measured-move target ${target:.2f}"
                elif near:
                    interp = f"Approaching neckline ${neckline:.2f} — watch for breakout toward ${target:.2f}"
                else:
                    interp = (
                        f"Head ${t2:.2f}, shoulders ~${shoulder_avg:.2f}, "
                        f"neckline ${neckline:.2f} — bullish if neckline clears"
                    )
                fill, border = _chart_colors("bullish")
                return {
                    "name": "Inverse Head & Shoulders",
                    "value": f"Head ${t2:.2f} / Shoulders ~${shoulder_avg:.2f} / Neckline ${neckline:.2f}",
                    "interpretation": interp,
                    "direction": "bullish",
                    "score": 1.0 if broke else 0.6,
                    "weight": 1.5,
                    "chart_data": {
                        "x0": _fmt(data.index[t_idx[0]]),
                        "x1": _fmt(data.index[-1]),
                        "y0": round(t2 * 0.99, 2),
                        "y1": round(neckline * 1.01, 2),
                        "label": "Inv. Head & Shoulders",
                        "fill": fill,
                        "border": border,
                    },
                }

    return None


def _detect_double_top(df: pd.DataFrame) -> dict | None:
    """
    Bearish Double Top — two peaks within 3% of each other with a meaningful trough
    between them and current price pulling back from the second peak.
    Uses last 60 bars.
    """
    data = df.tail(60)
    if len(data) < 20:
        return None

    peaks = _local_peaks(data["High"], window=7)
    if len(peaks) < 2:
        return None

    p1_i, p2_i = peaks[-2], peaks[-1]
    p1 = float(data["High"].iloc[p1_i])
    p2 = float(data["High"].iloc[p2_i])

    # Peaks within 3%
    if abs(p1 - p2) / max(p1, p2) > 0.03:
        return None

    # Meaningful trough between the peaks (at least 3% below peaks)
    trough = float(data["Low"].iloc[p1_i:p2_i].min())
    peak_avg = (p1 + p2) / 2
    if (peak_avg - trough) / peak_avg < 0.03:
        return None

    current = float(data["Close"].iloc[-1])
    # Price should be below second peak (declining from it)
    if current >= p2 * 0.99:
        return None

    target = trough - (peak_avg - trough)
    broke_support = current < trough

    if broke_support:
        interp = f"Support ${trough:.2f} broken — measured-move target ${target:.2f}"
    else:
        interp = (
            f"Two tops at ~${peak_avg:.2f}, support at ${trough:.2f} — "
            f"bearish if ${trough:.2f} breaks; target ${target:.2f}"
        )
    fill, border = _chart_colors("bearish")
    return {
        "name": "Double Top",
        "value": f"Tops ~${peak_avg:.2f} / Support ${trough:.2f}",
        "interpretation": interp,
        "direction": "bearish",
        "score": -1.0 if broke_support else -0.6,
        "weight": 1.5,
        "chart_data": {
            "x0": _fmt(data.index[p1_i]),
            "x1": _fmt(data.index[-1]),
            "y0": round(trough * 0.99, 2),
            "y1": round(peak_avg * 1.01, 2),
            "label": "Double Top",
            "fill": fill,
            "border": border,
        },
    }


def _detect_double_bottom(df: pd.DataFrame) -> dict | None:
    """
    Bullish Double Bottom — two troughs within 3% of each other with a meaningful
    peak between them and current price rebounding from the second trough.
    Uses last 60 bars.
    """
    data = df.tail(60)
    if len(data) < 20:
        return None

    troughs = _local_troughs(data["Low"], window=7)
    if len(troughs) < 2:
        return None

    t1_i, t2_i = troughs[-2], troughs[-1]
    t1 = float(data["Low"].iloc[t1_i])
    t2 = float(data["Low"].iloc[t2_i])

    if abs(t1 - t2) / min(t1, t2) > 0.03:
        return None

    peak = float(data["High"].iloc[t1_i:t2_i].max())
    trough_avg = (t1 + t2) / 2
    if (peak - trough_avg) / trough_avg < 0.03:
        return None

    current = float(data["Close"].iloc[-1])
    if current <= t2 * 1.01:
        return None

    target = peak + (peak - trough_avg)
    broke_resistance = current > peak

    if broke_resistance:
        interp = f"Resistance ${peak:.2f} cleared — measured-move target ${target:.2f}"
    else:
        interp = (
            f"Two bottoms at ~${trough_avg:.2f}, resistance at ${peak:.2f} — "
            f"bullish if ${peak:.2f} clears; target ${target:.2f}"
        )
    fill, border = _chart_colors("bullish")
    return {
        "name": "Double Bottom",
        "value": f"Bottoms ~${trough_avg:.2f} / Resistance ${peak:.2f}",
        "interpretation": interp,
        "direction": "bullish",
        "score": 1.0 if broke_resistance else 0.6,
        "weight": 1.5,
        "chart_data": {
            "x0": _fmt(data.index[t1_i]),
            "x1": _fmt(data.index[-1]),
            "y0": round(trough_avg * 0.99, 2),
            "y1": round(peak * 1.01, 2),
            "label": "Double Bottom",
            "fill": fill,
            "border": border,
        },
    }


# ---------------------------------------------------------------------------
# Continuation patterns
# ---------------------------------------------------------------------------


def _detect_triangle(df: pd.DataFrame) -> dict | None:
    """
    Detect ascending, descending, or symmetrical triangle in last 35 bars.
    Uses linear regression slopes on highs and lows.
    """
    data = df.tail(35)
    if len(data) < 20:
        return None

    high_slope = _linreg_slope_pct(data["High"])
    low_slope = _linreg_slope_pct(data["Low"])
    flat = 0.0012  # ≈0.12% of price per bar threshold for "flat"

    x0 = _fmt(data.index[0])
    x1 = _fmt(data.index[-1])
    y0 = round(float(data["Low"].min()) * 0.99, 2)
    y1 = round(float(data["High"].max()) * 1.01, 2)

    if abs(high_slope) <= flat and low_slope > flat:
        resistance = round(float(data["High"].tail(10).mean()), 2)
        fill, border = _chart_colors("bullish")
        return {
            "name": "Ascending Triangle",
            "value": f"Flat resistance ~${resistance:.2f} / Rising lows",
            "interpretation": (
                f"Flat resistance at ~${resistance:.2f} with rising lows — "
                "buyers gaining strength; bullish breakout expected"
            ),
            "direction": "bullish",
            "score": 0.7,
            "weight": 1.25,
            "chart_data": {"x0": x0, "x1": x1, "y0": y0, "y1": y1,
                           "label": "Ascending △", "fill": fill, "border": border},
        }

    if abs(low_slope) <= flat and high_slope < -flat:
        support = round(float(data["Low"].tail(10).mean()), 2)
        fill, border = _chart_colors("bearish")
        return {
            "name": "Descending Triangle",
            "value": f"Flat support ~${support:.2f} / Declining highs",
            "interpretation": (
                f"Flat support at ~${support:.2f} with declining highs — "
                "sellers in control; bearish breakdown expected"
            ),
            "direction": "bearish",
            "score": -0.7,
            "weight": 1.25,
            "chart_data": {"x0": x0, "x1": x1, "y0": y0, "y1": y1,
                           "label": "Descending △", "fill": fill, "border": border},
        }

    if high_slope < -flat and low_slope > flat:
        apex = round((float(data["High"].iloc[-1]) + float(data["Low"].iloc[-1])) / 2, 2)
        fill, border = _chart_colors("neutral")
        return {
            "name": "Symmetrical Triangle",
            "value": f"Converging toward ~${apex:.2f}",
            "interpretation": (
                f"Lower highs and higher lows converging near ${apex:.2f} — "
                "volatility compression; breakout direction confirms trend"
            ),
            "direction": "neutral",
            "score": 0.0,
            "weight": 1.0,
            "chart_data": {"x0": x0, "x1": x1, "y0": y0, "y1": y1,
                           "label": "Symm. △", "fill": fill, "border": border},
        }

    return None


def _detect_flag(df: pd.DataFrame) -> dict | None:
    """
    Bull or Bear Flag — sharp directional pole (≥5% in 8 bars) followed by
    a tight, counter-trend consolidation (last 7 bars).
    """
    data = df.tail(20)
    if len(data) < 15:
        return None

    pole = data.iloc[:10]
    flag = data.iloc[10:]

    pole_start = float(pole["Close"].iloc[0])
    pole_end = float(pole["Close"].iloc[-1])
    pole_move = (pole_end - pole_start) / pole_start

    if abs(pole_move) < 0.05:
        return None

    flag_range = (float(flag["High"].max()) - float(flag["Low"].min()))
    flag_range_pct = flag_range / float(flag["Close"].mean())
    pole_size = float(pole["High"].max()) - float(pole["Low"].min())

    # Flag must be tight: range < 40% of pole size
    if flag_range > pole_size * 0.4:
        return None

    current = float(data["Close"].iloc[-1])
    x0 = _fmt(data.index[0])
    x1 = _fmt(data.index[-1])
    y0 = round(float(data["Low"].min()) * 0.99, 2)
    y1 = round(float(data["High"].max()) * 1.01, 2)

    if pole_move > 0:
        target = round(current + (pole_end - pole_start), 2)
        fill, border = _chart_colors("bullish")
        return {
            "name": "Bull Flag",
            "value": f"Pole +{pole_move*100:.1f}% / Flag {flag_range_pct*100:.1f}% range",
            "interpretation": (
                f"Tight consolidation after +{pole_move*100:.1f}% rally — "
                f"measured-move target ~${target:.2f} on breakout"
            ),
            "direction": "bullish",
            "score": 0.7,
            "weight": 1.25,
            "chart_data": {"x0": x0, "x1": x1, "y0": y0, "y1": y1,
                           "label": "Bull Flag", "fill": fill, "border": border},
        }
    else:
        target = round(current + (pole_end - pole_start), 2)
        fill, border = _chart_colors("bearish")
        return {
            "name": "Bear Flag",
            "value": f"Pole {pole_move*100:.1f}% / Flag {flag_range_pct*100:.1f}% range",
            "interpretation": (
                f"Tight bounce after {pole_move*100:.1f}% decline — "
                f"measured-move target ~${target:.2f} on breakdown"
            ),
            "direction": "bearish",
            "score": -0.7,
            "weight": 1.25,
            "chart_data": {"x0": x0, "x1": x1, "y0": y0, "y1": y1,
                           "label": "Bear Flag", "fill": fill, "border": border},
        }


def _detect_rectangle(df: pd.DataFrame) -> dict | None:
    """
    Rectangle (trading range) — price oscillating between roughly flat support
    and resistance with multiple touches. Uses last 40 bars.
    """
    data = df.tail(40)
    if len(data) < 20:
        return None

    high_slope = abs(_linreg_slope_pct(data["High"]))
    low_slope = abs(_linreg_slope_pct(data["Low"]))
    flat = 0.0012

    if high_slope > flat or low_slope > flat:
        return None

    resistance = round(float(data["High"].mean()), 2)
    support = round(float(data["Low"].mean()), 2)
    height_pct = (resistance - support) / support * 100

    # Only flag if there's a meaningful, tight range (1–8%)
    if height_pct < 1.0 or height_pct > 8.0:
        return None

    current = float(data["Close"].iloc[-1])
    pct_b = (current - support) / (resistance - support) if resistance != support else 0.5

    if pct_b > 0.8:
        direction, score = "bearish", -0.4
        note = f"Near top of range ${resistance:.2f} — watch for breakdown or breakout"
    elif pct_b < 0.2:
        direction, score = "bullish", 0.4
        note = f"Near bottom of range ${support:.2f} — watch for bounce or breakdown"
    else:
        direction, score = "neutral", 0.0
        note = "Mid-range — no edge until breakout of the rectangle"

    fill, border = _chart_colors(direction)
    return {
        "name": "Rectangle (Range)",
        "value": f"Support ${support:.2f} / Resistance ${resistance:.2f} ({height_pct:.1f}% range)",
        "interpretation": note,
        "direction": direction,
        "score": score,
        "weight": 1.0,
        "chart_data": {
            "x0": _fmt(data.index[0]),
            "x1": _fmt(data.index[-1]),
            "y0": round(support * 0.99, 2),
            "y1": round(resistance * 1.01, 2),
            "label": "Rectangle",
            "fill": fill,
            "border": border,
        },
    }


# ---------------------------------------------------------------------------
# Gap & Key Reversal
# ---------------------------------------------------------------------------


def _detect_gap(df: pd.DataFrame) -> dict | None:
    """
    Detect a significant gap up or gap down in the last 5 trading days.
    Gap = today's open outside prior day's high/low range.
    """
    data = df.tail(6)
    if len(data) < 2:
        return None

    for i in range(len(data) - 1, 0, -1):
        today_open = float(data["Open"].iloc[i])
        today_close = float(data["Close"].iloc[i])
        prior_high = float(data["High"].iloc[i - 1])
        prior_low = float(data["Low"].iloc[i - 1])
        prior_close = float(data["Close"].iloc[i - 1])

        gap_pct = abs(today_open - prior_close) / prior_close * 100

        if today_open > prior_high and gap_pct >= 0.5:
            filled = today_close < prior_high
            fill, border = _chart_colors("bullish" if not filled else "neutral")
            return {
                "name": "Gap Up",
                "value": f"Opened ${today_open:.2f} above prior high ${prior_high:.2f} (+{gap_pct:.1f}%)",
                "interpretation": (
                    f"Gap up of {gap_pct:.1f}% — {'gap partially filled (weakening)' if filled else 'gap held; bullish continuation signal'}"
                ),
                "direction": "bullish" if not filled else "neutral",
                "score": 0.5 if not filled else 0.1,
                "weight": 1.0,
                "chart_data": {
                    "x0": _fmt(data.index[i - 1]),
                    "x1": _fmt(data.index[i]),
                    "y0": round(prior_high, 2),
                    "y1": round(today_open, 2),
                    "label": f"Gap Up +{gap_pct:.1f}%",
                    "fill": fill,
                    "border": border,
                },
            }

        if today_open < prior_low and gap_pct >= 0.5:
            filled = today_close > prior_low
            fill, border = _chart_colors("bearish" if not filled else "neutral")
            return {
                "name": "Gap Down",
                "value": f"Opened ${today_open:.2f} below prior low ${prior_low:.2f} (-{gap_pct:.1f}%)",
                "interpretation": (
                    f"Gap down of {gap_pct:.1f}% — {'gap partially filled (weakening)' if filled else 'gap held; bearish continuation signal'}"
                ),
                "direction": "bearish" if not filled else "neutral",
                "score": -0.5 if not filled else -0.1,
                "weight": 1.0,
                "chart_data": {
                    "x0": _fmt(data.index[i - 1]),
                    "x1": _fmt(data.index[i]),
                    "y0": round(today_open, 2),
                    "y1": round(prior_low, 2),
                    "label": f"Gap Down -{gap_pct:.1f}%",
                    "fill": fill,
                    "border": border,
                },
            }

    return None


def _detect_key_reversal(df: pd.DataFrame) -> dict | None:
    """
    Key Reversal Day — new multi-week extreme followed by a close in the opposite
    direction. High volume required for confirmation. Checks last 3 bars.
    """
    data = df.tail(25)
    if len(data) < 5:
        return None

    lookback_high = float(data["High"].iloc[:-1].max())
    lookback_low = float(data["Low"].iloc[:-1].min())
    avg_volume = float(data["Volume"].iloc[:-3].mean()) if "Volume" in data.columns else None

    for i in range(len(data) - 1, max(len(data) - 4, 0), -1):
        bar_high = float(data["High"].iloc[i])
        bar_low = float(data["Low"].iloc[i])
        bar_close = float(data["Close"].iloc[i])
        prior_close = float(data["Close"].iloc[i - 1])
        bar_vol = float(data["Volume"].iloc[i]) if "Volume" in data.columns else None

        high_vol = (bar_vol > avg_volume * 1.3) if (avg_volume and bar_vol) else True

        # Bearish key reversal: new high, closes below prior close
        if bar_high >= lookback_high * 0.995 and bar_close < prior_close and high_vol:
            fill, border = _chart_colors("bearish")
            return {
                "name": "Bearish Key Reversal",
                "value": f"New high ${bar_high:.2f}, closed ${bar_close:.2f} below prior close ${prior_close:.2f}",
                "interpretation": (
                    "Price made new high then reversed to close below prior day — "
                    "classic sign of buyer exhaustion and potential trend reversal"
                ),
                "direction": "bearish",
                "score": -0.8,
                "weight": 1.25,
                "chart_data": {
                    "x0": _fmt(data.index[i - 1]),
                    "x1": _fmt(data.index[i]),
                    "y0": round(min(bar_low, prior_close) * 0.99, 2),
                    "y1": round(bar_high * 1.01, 2),
                    "label": "Bearish Key Reversal",
                    "fill": fill,
                    "border": border,
                },
            }

        # Bullish key reversal: new low, closes above prior close
        if bar_low <= lookback_low * 1.005 and bar_close > prior_close and high_vol:
            fill, border = _chart_colors("bullish")
            return {
                "name": "Bullish Key Reversal",
                "value": f"New low ${bar_low:.2f}, closed ${bar_close:.2f} above prior close ${prior_close:.2f}",
                "interpretation": (
                    "Price made new low then reversed to close above prior day — "
                    "classic sign of seller exhaustion and potential trend reversal"
                ),
                "direction": "bullish",
                "score": 0.8,
                "weight": 1.25,
                "chart_data": {
                    "x0": _fmt(data.index[i - 1]),
                    "x1": _fmt(data.index[i]),
                    "y0": round(bar_low * 0.99, 2),
                    "y1": round(max(bar_high, prior_close) * 1.01, 2),
                    "label": "Bullish Key Reversal",
                    "fill": fill,
                    "border": border,
                },
            }

    return None


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

_DETECTORS = [
    _detect_head_and_shoulders,
    _detect_double_top,
    _detect_double_bottom,
    _detect_triangle,
    _detect_flag,
    _detect_rectangle,
    _detect_gap,
    _detect_key_reversal,
]


def detect_patterns(df: pd.DataFrame) -> list[dict]:
    """
    Run all pattern detectors against the dataframe.
    Returns a list of signal dicts (same format as analysis.py signals).
    Failed detectors are silently skipped.
    """
    results = []
    for detector in _DETECTORS:
        try:
            result = detector(df)
            if result:
                results.append(result)
        except Exception:
            pass
    return results
