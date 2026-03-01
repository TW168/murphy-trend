# Murphy Trend

Stock technical analysis web app based on John J. Murphy's *Technical Analysis of the Financial Markets*. Enter any publicly traded ticker to get a Murphy Outlook (bullish / bearish / neutral), 30/60/90-day price targets, detected chart patterns, and interactive Plotly charts.

## Features

- **Murphy Outlook Score** — weighted composite of 10+ technical signals (MAs, RSI, MACD, Bollinger Bands, OBV, volume, price trend)
- **Chart Pattern Detection** — Head & Shoulders, Double Top/Bottom, Triangles, Flags, Rectangles, Gaps, Key Reversal Days
- **Price Targets** — 30-, 60-, and 90-day low / target / high projections
- **Key Levels** — support, resistance, and Fibonacci retracement levels
- **Watchlist** — save tickers for quick re-analysis
- **Market Overview** — live S&P 500, DOW, and NASDAQ quotes on the dashboard
- **Dark mode** — persists via localStorage

## Quick Start

```bash
# Install dependencies
uv sync

# Run migrations
uv run alembic upgrade head

# Start dev server
uv run uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

## Docker

```bash
docker-compose up --build
```

SQLite data is persisted in a named Docker volume (`data`). Set `DATABASE_URL` to a PostgreSQL connection string to switch databases.

## Configuration

Copy `.env.example` to `.env` and set:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:////data/murphy.db` | SQLAlchemy database URL |
| `SECRET_KEY` | — | Reserved for future auth |

## Stack

Python 3.12 · FastAPI · Jinja2 · SQLAlchemy 2 · Alembic · yfinance · pandas · Plotly · Bootstrap 5

## Architecture

See [/sad](/sad) in the running app or [SAD.md](SAD.md) for the full Software Architecture Document.

## Disclaimer

For informational purposes only. Not financial advice.
