# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MurphyTrend** — a stock technical analysis web application based on John J. Murphy's "Technical Analysis of the Financial Markets." It predicts 30-day, 60-day, and 90-day trend direction and price targets.

## Tech Stack

- **Backend:** Python 3.12+, FastAPI + Jinja2, Uvicorn ASGI
- **Database:** SQLAlchemy 2.0 + Alembic (SQLite default; set `DATABASE_URL` env var for PostgreSQL)
- **Data:** yfinance (live market data), pandas, pandas_ta, plotly
- **Docs rendering:** python-markdown2 + Pygments (for the `/sad` route)
- **Frontend:** Bootstrap 5 (layout, scrollspy for `/sad` TOC sidebar)
- **Package manager:** `uv` (pyproject.toml + uv.lock)
- **Containerization:** Docker + docker-compose
- **VCS:** GitHub
- **Deployment:** Dokploy on Hostinger VPS (Docker-based; ensure `docker-compose.yml` is Dokploy-compatible)

## Common Commands

```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn app.main:app --reload --port 8000

# Run database migrations
uv run alembic upgrade head

# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Run tests
uv run pytest

# Run a single test
uv run pytest tests/path/to/test.py::test_name -v

# Lint
uv run ruff check .
uv run ruff format --check .

# Docker
docker-compose up --build
```

## Architecture

The app follows a layered FastAPI architecture with server-side rendering via Jinja2:

```
app/
├── main.py              # FastAPI app factory, route registration
├── routers/             # Route handlers (dashboard, analyze, sad, help, health)
├── services/            # Business logic: technical analysis engine, yfinance data fetching
├── models/              # SQLAlchemy ORM models (Watchlist, AnalysisCache)
├── schemas/             # Pydantic schemas for request/response validation
├── templates/           # Jinja2 HTML templates
├── static/              # CSS, JS, assets
└── database.py          # SQLAlchemy engine/session setup
alembic/                 # DB migration scripts
SAD.md                   # Software Architecture Document (served at /sad)
```

## Routes

| Route | Purpose |
|-------|---------|
| `GET /` | Dashboard: major index prices (S&P 500, DOW, NASDAQ) + ticker search |
| `GET /analyze` | Main analysis: ticker input, Plotly charts, Murphy signals, 30/60/90-day predictions |
| `GET /sad` | SAD.md rendered as HTML with sticky TOC sidebar (Bootstrap scrollspy) |
| `GET /help` | Murphy Concepts reference page |
| `GET /health` | `{ "status": "healthy", "timestamp": "..." }` |

## Technical Analysis Engine

Implement these Murphy-based indicators in `app/services/analysis.py`:

- **Trend:** Dow Theory secondary trends, higher highs/lows, trendlines, channels, support/resistance
- **Retracements:** 33%/50%/66% and Fibonacci 38.2%/61.8%
- **Patterns:** Head & Shoulders, double/triple tops/bottoms; triangles, flags, pennants, rectangles; gaps, key reversal days
- **Moving Averages:** 50-day & 200-day; golden/death cross; price position relative to MAs
- **Volume:** OBV, volume confirmation of breakouts
- **Oscillators:** MACD, RSI(14) with divergences and overbought/oversold zones
- **Bollinger Bands:** (20, 2) for volatility and price targets
- **Output:** Plain-English "Murphy Outlook" (bullish/bearish/neutral) + price targets via measured-move or Fib extension

## Design System

- **Palette:** Background `#f8f9fa → #f4f7f9`, cards `#ffffff`, primary teal `#2a9d8f`, accent blue `#277da1`, text `#2b2d42`
- **Font:** Inter
- **Standards:** WCAG AAA contrast, generous whitespace, smooth animations
- **Dark mode:** Toggle via localStorage

## Database Models

- `Watchlist` — user-saved ticker watchlists (fields: id, user_id, ticker, name, created_at)
- `AnalysisCache` — cached analysis results keyed by ticker + date to avoid redundant yfinance calls (fields: id, ticker, date, result_json, expires_at)

## SAD.md

The file `SAD.md` at the repo root is served at `/sad` as rendered HTML. It must contain: Introduction, System Overview, Architectural Styles & Patterns, Technology Stack, Data Model, Folder Structure, API Endpoints, Deployment & Scaling, Security & Compliance, Future Roadmap. The route converts it to HTML with Pygments syntax highlighting and a JS-generated Bootstrap scrollspy TOC sidebar.

## Status

The application is fully implemented. All routes, services, templates, and static assets exist. Run `uv sync` then `uv run uvicorn app.main:app --reload --port 8000` to start.
