"""NYSE market breadth: Net New 52-Week Highs and Lows."""
import json
import logging
from datetime import date

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

_cache: dict = {}

# Representative NYSE-listed large-caps across sectors
NYSE_STOCKS = [
    # Financials
    "JPM", "BAC", "WFC", "C", "GS", "MS", "BLK", "AXP", "COF", "USB",
    "TFC", "PNC", "SCHW", "MET", "PRU", "AIG", "ALL", "CB", "TRV", "BK",
    # Healthcare
    "JNJ", "UNH", "PFE", "ABT", "MRK", "LLY", "BMY", "CVS", "HUM", "CI",
    "MDT", "ELV", "HCA", "SYK", "BSX", "BDX",
    # Energy
    "XOM", "CVX", "COP", "EOG", "SLB", "PSX", "VLO", "MPC", "OXY", "HAL",
    "DVN", "KMI", "WMB",
    # Industrials
    "GE", "HON", "CAT", "DE", "BA", "UPS", "FDX", "RTX", "LMT", "NOC",
    "MMM", "EMR", "ETN", "PH", "ITW", "GD",
    # Consumer Staples / Discretionary
    "PG", "KO", "PEP", "PM", "MO", "CL", "KMB", "WMT", "TGT", "HD",
    "LOW", "MCD", "YUM", "DRI", "HLT", "MAR", "EL",
    # Materials
    "LIN", "APD", "ECL", "NEM", "FCX", "PPG", "SHW",
    # Utilities
    "NEE", "DUK", "SO", "D", "AEP", "EXC", "XEL", "ED", "ETR",
    # Real Estate
    "AMT", "PLD", "CCI", "O", "SPG", "PSA", "EQR", "AVB", "WELL",
    # Technology (NYSE-listed)
    "IBM", "HPE", "ORCL", "ACN",
]


def _build_hl_chart(net: pd.Series, highs: pd.Series, lows: pd.Series, total: int) -> str:
    dates = net.index.strftime("%Y-%m-%d").tolist()
    net_vals = [int(v) for v in net.tolist()]
    highs_vals = [int(v) for v in highs.tolist()]
    lows_vals = [int(v) for v in lows.tolist()]
    pct_vals = [round(v / total * 100, 2) for v in net_vals]

    traces = [
        {
            "type": "scatter",
            "x": dates,
            "y": pct_vals,
            "mode": "lines",
            "line": {"color": "#2563eb", "width": 2, "shape": "spline", "smoothing": 0.8},
            "fill": "tozeroy",
            "fillcolor": "rgba(37,99,235,0.08)",
            "name": "Net",
            "customdata": list(zip(highs_vals, lows_vals, net_vals)),
            "hovertemplate": (
                "<b>%{x|%b %d, %Y}</b><br>"
                "At 52-week high: %{customdata[0]} stocks<br>"
                "At 52-week low: %{customdata[1]} stocks<br>"
                "Net (highs minus lows): <b>%{customdata[2]:+d} stocks (%{y:.2f}%)</b>"
                "<extra></extra>"
            ),
        }
    ]

    layout = {
        "margin": {"t": 10, "b": 40, "l": 55, "r": 10},
        "paper_bgcolor": "#ffffff",
        "plot_bgcolor": "#ffffff",
        "font": {"family": "Inter, sans-serif", "size": 11, "color": "#2b2d42"},
        "hovermode": "x unified",
        "showlegend": False,
        "xaxis": {
            "type": "date",
            "showgrid": False,
            "tickfont": {"size": 11},
            "fixedrange": True,
            "tickcolor": "#dee2e6",
            "linecolor": "#dee2e6",
            "tickformat": "%b %Y",
            "dtick": "M3",
        },
        "yaxis": {
            "gridcolor": "#dee2e6",
            "griddash": "dot",
            "tickfont": {"size": 11},
            "zeroline": True,
            "zerolinecolor": "#adb5bd",
            "zerolinewidth": 1.5,
            "fixedrange": True,
            "ticksuffix": "%",
        },
    }

    return json.dumps({"data": traces, "layout": layout})


def calculate_nyse_highs_lows() -> dict:
    """Download NYSE stock data and compute net new 52-week highs minus lows."""
    today = date.today().isoformat()
    if _cache.get("date") == today and _cache.get("data"):
        return _cache["data"]

    try:
        raw = yf.download(
            NYSE_STOCKS,
            period="2y",
            auto_adjust=True,
            progress=False,
            threads=True,
        )

        if raw.empty:
            logger.warning("NYSE breadth: yfinance returned empty data")
            return {}

        # Handle multi-level columns from batch download
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw["Close"]
        else:
            close = raw

        close = close.dropna(how="all")

        # Rolling 252-day high/low (1 trading year)
        roll_max = close.rolling(252).max()
        roll_min = close.rolling(252).min()

        # Strict: only stocks that actually hit a new 52-week high/low today (within 0.1%)
        is_high = close >= roll_max * 0.999
        is_low = close <= roll_min * 1.001

        highs = is_high.sum(axis=1)
        lows = is_low.sum(axis=1)
        net = highs - lows

        # Drop warmup period
        valid = roll_max.notna().any(axis=1)
        net = net[valid]
        highs = highs[valid]
        lows = lows[valid]

        # Last 252 trading days for the chart
        net_plot = net.iloc[-252:]
        highs_plot = highs.iloc[-252:]
        lows_plot = lows.iloc[-252:]
        total = close.shape[1]
        net_pct = (net / total * 100).round(2)
        net_pct_plot = net_pct.iloc[-252:]

        chart_json = _build_hl_chart(net_plot, highs_plot, lows_plot, total)

        current_net = int(net_plot.iloc[-1]) if len(net_plot) > 0 else 0
        current_highs = int(highs_plot.iloc[-1]) if len(highs_plot) > 0 else 0
        current_lows = int(lows_plot.iloc[-1]) if len(lows_plot) > 0 else 0
        current_pct = round(float(net_pct_plot.iloc[-1]), 2) if len(net_pct_plot) > 0 else 0.0
        last_updated = net_pct_plot.index[-1].strftime("%b %-d at %-I:%M %p") if len(net_pct_plot) > 0 else ""

        result = {
            "chart_json": chart_json,
            "current_net": current_net,
            "current_highs": current_highs,
            "current_lows": current_lows,
            "current_pct": current_pct,
            "last_updated": last_updated,
            "signal": "Greed" if current_net > 5 else ("Fear" if current_net < -5 else "Neutral"),
        }

        _cache["date"] = today
        _cache["data"] = result
        return result

    except Exception as exc:
        logger.error("NYSE highs/lows calculation failed: %s", exc)
        return {}
