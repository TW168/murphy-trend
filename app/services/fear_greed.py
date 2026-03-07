"""CNN-style Fear & Greed Index calculation.

Aggregates 7 market sentiment indicators into a 0-100 composite score.
Each indicator is scored by its rolling percentile rank over 125 days —
measuring how much it deviates from its average compared to how much
it normally diverges (the CNN methodology).
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

# ---------------------------------------------------------------------------
# Tickers used across components
# ---------------------------------------------------------------------------
_ALL_TICKERS = [
    "^GSPC", "^VIX", "^SKEW", "SPY", "TLT", "HYG", "LQD",
    "XLK", "XLF", "XLV", "XLI", "XLC", "XLE",
    "XLU", "XLRE", "XLY", "XLP", "XLB",
]

_SECTOR_ETFS = [
    "XLK", "XLF", "XLV", "XLI", "XLC", "XLE",
    "XLU", "XLRE", "XLY", "XLP", "XLB",
]

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
_cache: dict = {"date": None, "result": None}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def _pct_rank(series: pd.Series, window: int = 125) -> pd.Series:
    """Rolling percentile rank over *window* days. Returns 0-100.

    This is the core CNN methodology: where does today's value sit
    relative to its recent history?
    """
    return series.rolling(window, min_periods=60).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False,
    ) * 100


def _fetch_all_data() -> dict[str, pd.DataFrame]:
    """Fetch 1y daily data for all tickers in a single download call."""
    raw = yf.download(
        _ALL_TICKERS,
        period="1y",
        group_by="ticker",
        auto_adjust=True,
        threads=True,
    )
    data: dict[str, pd.DataFrame] = {}
    for ticker in _ALL_TICKERS:
        try:
            df = raw[ticker].dropna(how="all")
            if not df.empty:
                df.index = (
                    df.index.tz_localize(None)
                    if df.index.tz
                    else df.index
                )
                data[ticker] = df
        except (KeyError, AttributeError):
            continue
    return data


# ---------------------------------------------------------------------------
# Component scorers — each returns a pd.Series of 0-100 scores
# ---------------------------------------------------------------------------

def _score_market_momentum(
    data: dict[str, pd.DataFrame],
) -> pd.Series | None:
    """S&P 500 and its 125-day moving average.

    Percentile-ranks the S&P 500 price over 125 days — where does
    today's price sit relative to the last 125 trading days?
    """
    df = data.get("^GSPC")
    if df is None or len(df) < 125:
        return None
    close = df["Close"]
    return _pct_rank(close)


def _score_price_strength(
    data: dict[str, pd.DataFrame],
) -> pd.Series | None:
    """Average 52-week range percentile across sector ETFs.

    For each ETF: (price - 52wk_low) / (52wk_high - 52wk_low) * 100.
    Then average across all ETFs. Already 0-100 and self-calibrating.
    """
    available = [
        t for t in _SECTOR_ETFS
        if t in data and len(data[t]) >= 125
    ]
    if len(available) < 5:
        return None

    min_len = min(len(data[t]) for t in available)
    common_idx = data[available[0]].index[-min_len:]

    pct_ranks = pd.DataFrame(index=common_idx, dtype=float)
    for t in available:
        close = data[t]["Close"].reindex(common_idx)
        high_252 = close.rolling(252, min_periods=125).max()
        low_252 = close.rolling(252, min_periods=125).min()
        rng = high_252 - low_252
        pct_ranks[t] = (
            (close - low_252) / rng.replace(0, np.nan)
        ).clip(0, 1)

    scores = (pct_ranks.mean(axis=1) * 100).fillna(50.0)
    return scores


def _score_price_breadth(
    data: dict[str, pd.DataFrame],
) -> pd.Series | None:
    """Advance/decline breadth across sector ETFs, percentile-ranked.

    Daily advance ratio (% of sectors up) is percentile-ranked
    over 125 days to measure deviation from normal.
    """
    available = [
        t for t in _SECTOR_ETFS
        if t in data and len(data[t]) >= 30
    ]
    if len(available) < 5:
        return None

    min_len = min(len(data[t]) for t in available)
    common_idx = data[available[0]].index[-min_len:]

    advances = pd.DataFrame(index=common_idx, dtype=float)
    for t in available:
        close = data[t]["Close"].reindex(common_idx)
        advances[t] = (close.diff() > 0).astype(float)

    daily_ratio = advances.mean(axis=1)
    smoothed = daily_ratio.rolling(25, min_periods=15).mean()
    return _pct_rank(smoothed)


def _score_put_call(
    data: dict[str, pd.DataFrame],
) -> pd.Series | None:
    """Put/Call proxy via CBOE SKEW Index, percentile-ranked (inverted).

    SKEW measures demand for out-of-the-money puts (tail risk hedging).
    High SKEW = traders buying downside protection = fear.
    Low SKEW = complacency = greed.
    Falls back to sector momentum breadth if SKEW is unavailable.
    """
    df = data.get("^SKEW")
    if df is not None and len(df) >= 125:
        close = df["Close"]
        rank = _pct_rank(close)
        return (100 - rank).clip(0, 100)

    # Fallback: sector momentum breadth (% above 50d SMA)
    available = [
        t for t in _SECTOR_ETFS
        if t in data and len(data[t]) >= 50
    ]
    if len(available) < 5:
        return None
    min_len = min(len(data[t]) for t in available)
    common_idx = data[available[0]].index[-min_len:]
    above_sma = pd.DataFrame(index=common_idx, dtype=float)
    for t in available:
        close = data[t]["Close"].reindex(common_idx)
        sma50 = _sma(close, 50)
        above_sma[t] = (close > sma50).astype(float)
    return (above_sma.mean(axis=1) * 100).fillna(50.0)


def _score_market_volatility(
    data: dict[str, pd.DataFrame],
) -> pd.Series | None:
    """VIX vs its 50-day MA, percentile-ranked (inverted).

    Deviation of VIX from its 50d MA is percentile-ranked.
    Inverted: lower VIX relative to MA = higher score (greed).
    """
    df = data.get("^VIX")
    if df is None or len(df) < 50:
        return None
    close = df["Close"]
    sma50 = _sma(close, 50)
    deviation = (close - sma50) / sma50
    rank = _pct_rank(deviation)
    return (100 - rank).clip(0, 100)


def _score_safe_haven(
    data: dict[str, pd.DataFrame],
) -> pd.Series | None:
    """20-day return spread: SPY - TLT, percentile-ranked.

    When stocks outperform bonds (positive spread), it signals
    greed. The spread is percentile-ranked over 125 days.
    """
    spy = data.get("SPY")
    tlt = data.get("TLT")
    if spy is None or tlt is None:
        return None
    if len(spy) < 25 or len(tlt) < 25:
        return None
    spy_ret = spy["Close"].pct_change(20)
    tlt_ret = tlt["Close"].pct_change(20)
    common = spy_ret.index.intersection(tlt_ret.index)
    spread = spy_ret.reindex(common) - tlt_ret.reindex(common)
    return _pct_rank(spread)


def _score_junk_bond(
    data: dict[str, pd.DataFrame],
) -> pd.Series | None:
    """20-day return spread: HYG - LQD, percentile-ranked.

    When junk bonds outperform investment grade (positive spread),
    it signals greed. The spread is percentile-ranked over 125 days.
    """
    hyg = data.get("HYG")
    lqd = data.get("LQD")
    if hyg is None or lqd is None:
        return None
    if len(hyg) < 25 or len(lqd) < 25:
        return None
    hyg_ret = hyg["Close"].pct_change(20)
    lqd_ret = lqd["Close"].pct_change(20)
    common = hyg_ret.index.intersection(lqd_ret.index)
    spread = hyg_ret.reindex(common) - lqd_ret.reindex(common)
    return _pct_rank(spread)


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

_COMPONENT_NAMES = [
    "Market Momentum",
    "Stock Price Strength",
    "Stock Price Breadth",
    "Put/Call Options",
    "Market Volatility",
    "Safe Haven Demand",
    "Junk Bond Demand",
]

_SCORERS = [
    _score_market_momentum,
    _score_price_strength,
    _score_price_breadth,
    _score_put_call,
    _score_market_volatility,
    _score_safe_haven,
    _score_junk_bond,
]


def _label(score: float) -> str:
    if score <= 24:
        return "Extreme Fear"
    if score <= 44:
        return "Fear"
    if score <= 55:
        return "Neutral"
    if score <= 74:
        return "Greed"
    return "Extreme Greed"


# ---------------------------------------------------------------------------
# Chart builder
# ---------------------------------------------------------------------------

def _build_chart(dates: pd.DatetimeIndex, scores: pd.Series) -> str:
    """Build a Plotly JSON chart of historical Fear & Greed scores."""
    sma125 = _sma(scores, 125)

    fig = go.Figure()

    # Sentiment zone bands
    zones = [
        (0, 25, "rgba(230,57,70,0.08)", "Extreme Fear"),
        (25, 45, "rgba(244,162,97,0.08)", "Fear"),
        (45, 55, "rgba(108,117,125,0.06)", "Neutral"),
        (55, 75, "rgba(42,157,143,0.08)", "Greed"),
        (75, 100, "rgba(29,138,126,0.10)", "Extreme Greed"),
    ]
    for y0, y1, color, _ in zones:
        fig.add_hrect(y0=y0, y1=y1, fillcolor=color, line_width=0)

    # Score line
    fig.add_trace(go.Scatter(
        x=dates, y=scores, mode="lines",
        name="Fear & Greed",
        line=dict(color="#2a9d8f", width=2),
        hovertemplate="%{x|%b %d}: %{y:.0f}<extra></extra>",
    ))

    # 125-day MA
    fig.add_trace(go.Scatter(
        x=dates, y=sma125, mode="lines",
        name="125-day MA",
        line=dict(color="#277da1", width=1.5, dash="dash"),
        hovertemplate="%{x|%b %d}: %{y:.0f}<extra></extra>",
    ))

    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=220,
        font=dict(
            family="Inter, system-ui, sans-serif",
            size=11, color="#2b2d42",
        ),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        yaxis=dict(
            range=[0, 100], gridcolor="#f0f0f0",
            zeroline=False, dtick=25,
        ),
        xaxis=dict(gridcolor="#f0f0f0", zeroline=False),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1, font=dict(size=10),
        ),
        hovermode="x unified",
    )

    return fig.to_json()


def _build_vix_chart(
    data: dict[str, pd.DataFrame],
) -> str | None:
    """Build a Plotly chart of VIX vs its 50-day MA."""
    df = data.get("^VIX")
    if df is None or len(df) < 50:
        return None
    close = df["Close"]
    sma50 = _sma(close, 50)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df.index, y=close, mode="lines",
        name="VIX",
        line=dict(color="#e63946", width=2),
        hovertemplate="%{x|%b %d}: %{y:.2f}<extra></extra>",
    ))

    fig.add_trace(go.Scatter(
        x=df.index, y=sma50, mode="lines",
        name="50-day MA",
        line=dict(color="#277da1", width=1.5, dash="dash"),
        hovertemplate="%{x|%b %d}: %{y:.2f}<extra></extra>",
    ))

    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=260,
        font=dict(
            family="Inter, system-ui, sans-serif",
            size=11, color="#2b2d42",
        ),
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        yaxis=dict(gridcolor="#f0f0f0", zeroline=False),
        xaxis=dict(gridcolor="#f0f0f0", zeroline=False),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1, font=dict(size=10),
        ),
        hovermode="x unified",
    )

    return fig.to_json()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def calculate_fear_greed() -> dict:
    """Calculate the Fear & Greed Index. Results are cached daily."""
    today = datetime.now().strftime("%Y-%m-%d")
    if _cache["date"] == today and _cache["result"] is not None:
        return _cache["result"]

    data = _fetch_all_data()
    if not data:
        return {
            "score": None,
            "label": "Unavailable",
            "components": [],
            "chart_json": None,
            "last_updated": today,
        }

    # Compute all component score series
    component_series: list[tuple[str, pd.Series]] = []
    for name, scorer in zip(_COMPONENT_NAMES, _SCORERS):
        try:
            series = scorer(data)
            if series is not None and not series.dropna().empty:
                component_series.append((name, series))
        except Exception:
            continue

    if not component_series:
        return {
            "score": None,
            "label": "Unavailable",
            "components": [],
            "chart_json": None,
            "last_updated": today,
        }

    # Align all series to a common date index
    all_dates = component_series[0][1].index
    for _, s in component_series[1:]:
        all_dates = all_dates.intersection(s.index)
    all_dates = all_dates.sort_values()

    # Build composite score series
    aligned = pd.DataFrame(
        {name: s.reindex(all_dates) for name, s in component_series},
    )
    composite = aligned.mean(axis=1)

    # Current values
    current_score = round(float(composite.iloc[-1]))
    current_label = _label(current_score)

    # Component breakdown (latest values)
    components = []
    for name, _ in component_series:
        val = aligned[name].iloc[-1]
        if pd.notna(val):
            components.append({
                "name": name,
                "score": round(float(val)),
            })

    # Build charts
    chart_json = _build_chart(all_dates, composite)
    vix_chart_json = _build_vix_chart(data)

    # VIX current values for display
    vix_data = data.get("^VIX")
    vix_current = None
    vix_sma50 = None
    if vix_data is not None and len(vix_data) >= 50:
        vix_current = round(
            float(vix_data["Close"].iloc[-1]), 2,
        )
        vix_sma50 = round(
            float(_sma(vix_data["Close"], 50).iloc[-1]), 2,
        )

    result = {
        "score": current_score,
        "label": current_label,
        "components": components,
        "chart_json": chart_json,
        "vix_chart_json": vix_chart_json,
        "vix_current": vix_current,
        "vix_sma50": vix_sma50,
        "last_updated": today,
    }

    _cache["date"] = today
    _cache["result"] = result
    return result
