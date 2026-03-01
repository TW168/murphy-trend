"""yfinance data fetching utilities."""

from __future__ import annotations

import yfinance as yf
import pandas as pd


INDEX_TICKERS = {
    "S&P 500": "^GSPC",
    "Dow Jones": "^DJI",
    "NASDAQ": "^IXIC",
}


def fetch_stock_data(ticker: str, period: str = "2y") -> pd.DataFrame:
    """Fetch OHLCV daily data for a ticker. Raises ValueError on bad ticker."""
    t = yf.Ticker(ticker)
    df = t.history(period=period, auto_adjust=True)
    if df.empty:
        raise ValueError(f"No data found for ticker '{ticker}'")
    df.index = df.index.tz_localize(None)
    return df


def fetch_ticker_info(ticker: str) -> dict:
    """Return basic info dict for a ticker (name, sector, market cap)."""
    t = yf.Ticker(ticker)
    info = t.info or {}
    sector = (
        info.get("sector")
        or info.get("category")
        or info.get("quoteType")
        or "N/A"
    )
    return {
        "company_name": info.get("longName") or info.get("shortName") or ticker.upper(),
        "sector": sector,
        "market_cap": info.get("marketCap"),
        "currency": info.get("currency", "USD"),
    }


def fetch_index_quotes() -> list[dict]:
    """Fetch current quotes for major market indices."""
    results = []
    for name, symbol in INDEX_TICKERS.items():
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="2d", auto_adjust=True)
            if len(hist) >= 2:
                prev_close = hist["Close"].iloc[-2]
                last_price = hist["Close"].iloc[-1]
                change = last_price - prev_close
                change_pct = (change / prev_close) * 100
            elif len(hist) == 1:
                last_price = hist["Close"].iloc[-1]
                change = 0.0
                change_pct = 0.0
            else:
                continue
            results.append(
                {
                    "name": name,
                    "symbol": symbol,
                    "price": round(float(last_price), 2),
                    "change": round(float(change), 2),
                    "change_pct": round(float(change_pct), 2),
                }
            )
        except Exception:
            results.append(
                {
                    "name": name,
                    "symbol": symbol,
                    "price": None,
                    "change": None,
                    "change_pct": None,
                }
            )
    return results
