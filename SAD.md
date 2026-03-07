# Murphy Trend — Software Architecture Document

## Introduction

Murphy Trend is a stock technical analysis web application that implements the methodology from John J. Murphy's *Technical Analysis of the Financial Markets*. It provides trend direction predictions at 30-, 60-, and 90-day horizons with price targets for any publicly traded ticker.

The application is a server-rendered Python web app with real-time market data from Yahoo Finance, a Murphy-based signal engine, and interactive Plotly charts.

---

## System Overview

```
Browser ──► FastAPI (Jinja2 SSR) ──► yfinance ──► Yahoo Finance API
                │
                ├──► SQLite / PostgreSQL (Watchlist, AnalysisCache)
                └──► Plotly (chart JSON → browser render)
```

Users interact with a server-rendered UI. The server fetches live market data, runs the technical analysis engine, and returns fully rendered HTML pages with embedded Plotly chart JSON. No frontend framework is used.

---

## Architectural Styles & Patterns

- **Layered architecture:** routers → services → data access. Routers handle HTTP concerns only; business logic lives in `services/`.
- **Server-Side Rendering (SSR):** Jinja2 templates generate complete HTML. No REST API or SPA — progressive enhancement only.
- **Cache-aside:** Analysis results are cached per ticker per calendar day in `AnalysisCache`. The router checks cache before calling the analysis service, reducing yfinance round trips.
- **Passive data model:** SQLAlchemy ORM models are plain data containers. No active record pattern.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Web framework | FastAPI 0.115+ |
| Templating | Jinja2 3.x |
| ASGI server | Uvicorn |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| Database | SQLite (default), PostgreSQL (production) |
| Market data | yfinance |
| Data processing | pandas 2.x, NumPy |
| Charting | Plotly (server-side JSON, client-side render) |
| Docs rendering | markdown2 + Pygments |
| Frontend | Bootstrap 5.3, Bootstrap Icons |
| Package manager | uv |
| Container | Docker + docker-compose |
| Deployment | Dokploy on Hostinger VPS |

---

## Data Model

### `watchlist`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| user_id | VARCHAR(64) | Nullable; reserved for future auth |
| ticker | VARCHAR(16) | Ticker symbol (e.g. AAPL) |
| name | VARCHAR(128) | Optional display label |
| created_at | DATETIME | Server default: now |

### `analysis_cache`

| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | Auto-increment |
| ticker | VARCHAR(16) | Indexed |
| date | VARCHAR(10) | YYYY-MM-DD (cache key) |
| result_json | TEXT | Full analysis result as JSON |
| outlook_score | FLOAT | Denormalized for quick queries |
| expires_at | DATETIME | End of calendar day (UTC) |

---

## Folder Structure

```
app/
├── main.py              # FastAPI app factory, lifespan, router registration
├── database.py          # SQLAlchemy engine, SessionLocal, Base, get_db()
├── models/
│   └── models.py        # Watchlist, AnalysisCache ORM models
├── schemas/
│   └── schemas.py       # Pydantic schemas (AnalysisResponse, Signal, Prediction, …)
├── services/
│   ├── market_data.py   # yfinance wrappers: fetch_stock_data, fetch_index_quotes
│   ├── analysis.py      # Murphy signal engine, chart builder, price targets
│   └── fear_greed.py    # CNN-style Fear & Greed Index (7 components, 0-100)
├── routers/
│   ├── dashboard.py     # GET /, POST /watchlist/add, POST /watchlist/remove/{ticker}
│   ├── analyze.py       # GET /analyze, POST /analyze (redirect)
│   ├── sad.py           # GET /sad
│   ├── help_route.py    # GET /help, GET /help/course
│   └── health.py        # GET /health
├── templates/
│   ├── base.html        # Navbar, dark mode, footer, CDN links
│   ├── dashboard.html   # Market indices, watchlist, quick analyze
│   ├── analyze.html     # Chart, outlook, signals, targets, levels
│   ├── sad.html         # Rendered SAD.md with TOC sidebar
│   ├── help.html        # Murphy concepts reference + course CTA
│   └── course.html      # Progressive learning course (5 modules, 13 lessons)
└── static/
    ├── css/main.css     # Design system, dark mode, component styles
    └── js/main.js       # Dark mode toggle, Plotly theme sync

alembic/                 # Alembic migration scaffolding
SAD.md                   # This document
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard: market indices, Fear & Greed Index, watchlist |
| GET | `/analyze?ticker=AAPL` | Full technical analysis for ticker |
| POST | `/analyze` | Redirect to GET with ticker param |
| POST | `/watchlist/add` | Add ticker to watchlist |
| POST | `/watchlist/remove/{ticker}` | Remove ticker from watchlist |
| GET | `/sad` | Rendered Software Architecture Document |
| GET | `/help` | Murphy concepts reference |
| GET | `/help/course` | Progressive learning course (5 modules, 13 lessons) |
| GET | `/health` | `{"status":"healthy","timestamp":"…"}` |

### Analysis Engine Output

The `analyze_ticker(ticker)` service returns a dict with:

- `outlook` — `"bullish"` | `"bearish"` | `"neutral"`
- `outlook_score` — weighted signal score, -1.0 to +1.0
- `signals` — list of `{name, value, interpretation, direction}` dicts
- `predictions` — 30/60/90-day `{days, low, target, high, direction}` targets
- `support_levels`, `resistance_levels` — swing point clusters
- `fib_levels` — Fibonacci retracement dict (0%, 23.6%, 38.2%, 50%, 61.8%, 100%)
- `patterns` — list of detected chart patterns `{name, value, interpretation, direction, score, weight}`
- `chart_json` — Plotly figure JSON (candlestick + BB + SMA + MACD + RSI)

### Fear & Greed Index

The `calculate_fear_greed()` service in `fear_greed.py` computes a CNN-style market sentiment index (0-100) from 7 equally-weighted components. Each indicator is scored by how much it deviates from its average compared to how much it normally diverges, using a 125-day rolling percentile rank (the CNN methodology).

| # | Component | Data Source | Method |
|---|-----------|-------------|--------|
| 1 | Market Momentum | ^GSPC | S&P 500 price percentile rank over 125 days |
| 2 | Stock Price Strength | 11 sector ETFs | Average 52-week range percentile |
| 3 | Stock Price Breadth | 11 sector ETFs | Advance/decline ratio, percentile-ranked |
| 4 | Put/Call Options | ^SKEW | SKEW index percentile rank (inverted, proxy) |
| 5 | Market Volatility | ^VIX | VIX vs 50d MA deviation, percentile-ranked (inverted) |
| 6 | Safe Haven Demand | SPY, TLT | 20-day return spread, percentile-ranked |
| 7 | Junk Bond Demand | HYG, LQD | 20-day return spread, percentile-ranked |

Labels: 0-24 Extreme Fear, 25-44 Fear, 45-55 Neutral, 56-74 Greed, 75-100 Extreme Greed.

Data is fetched in a single `yf.download()` call for all tickers. Results are cached in-memory per calendar day. The dashboard displays a canvas semicircle gauge, component progress bars, and a Plotly historical chart with 125-day MA overlay.

### Signal Scoring Weights

| Signal | Weight |
|--------|--------|
| MA Cross (golden/death) | 2.0 |
| Price Trend (HH/HL vs LL/LH) | 1.5 |
| RSI (14) | 1.5 |
| MACD Signal Line | 1.5 |
| Price vs SMA50 | 1.0 |
| Price vs SMA200 | 1.0 |
| MACD Histogram | 1.0 |
| Bollinger Bands %B | 1.0 |
| Volume Trend | 1.0 |
| OBV | 1.0 |

Final `outlook_score = Σ(score × weight) / Σ(weight)`. Thresholds: >0.2 bullish, <-0.2 bearish.

---

## Deployment & Scaling

### Development

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### Docker (Production)

```bash
docker-compose up --build
```

The `docker-compose.yml` binds port 8000 and mounts a `data/` volume for the SQLite database file. Set `DATABASE_URL` environment variable to switch to PostgreSQL.

### Dokploy (Hostinger VPS)

The repository is configured for Dokploy deployment. Push to the main branch triggers an automatic Docker rebuild and redeploy. The `docker-compose.yml` is Dokploy-compatible (no swarm extensions required).

### Scaling considerations

- Switch `DATABASE_URL` to PostgreSQL for concurrent write safety
- Add a Redis cache layer (replace SQLite `AnalysisCache`) for multi-instance deployments
- yfinance rate limits: cache-aside pattern absorbs burst traffic; each ticker is fetched at most once per day
- Static files are served by FastAPI's `StaticFiles`; move to CDN or nginx in high-traffic production

---

## Security & Compliance

- **No authentication** in v1; `Watchlist.user_id` is reserved for a future auth layer
- **No PII collected** — only ticker symbols are stored
- **SQL injection:** prevented by SQLAlchemy ORM parameterized queries throughout
- **XSS:** Jinja2 auto-escaping is enabled by default; `| safe` is only used for pre-rendered Plotly JSON and Pygments CSS
- **Market data:** yfinance uses Yahoo Finance's public API. Data is for informational purposes only; the application does not constitute financial advice
- **Environment secrets:** `DATABASE_URL` and `SECRET_KEY` are loaded from `.env` (never committed); `.gitignore` excludes `.env`

---

## Future Roadmap

- **User authentication** — OAuth2 / JWT, per-user watchlists
- **Alerts** — price/signal-based notifications via email or webhook
- **Backtesting** — historical signal accuracy scoring
- **Portfolio view** — multi-ticker dashboard with correlation matrix
- **Weekly/monthly timeframes** — extend analysis beyond daily data
- **API endpoints** — JSON API for external integrations or a future SPA frontend
- **WebSocket streaming** — real-time price updates on the dashboard
