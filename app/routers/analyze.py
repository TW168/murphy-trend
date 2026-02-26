import json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import AnalysisCache
from app.services.analysis import analyze_ticker

router = APIRouter(tags=["analyze"])
templates = Jinja2Templates(directory="app/templates")


def _get_cached(db: Session, ticker: str) -> dict | None:
    today = datetime.utcnow().date().isoformat()
    row = (
        db.query(AnalysisCache)
        .filter(AnalysisCache.ticker == ticker, AnalysisCache.date == today)
        .filter(AnalysisCache.expires_at > datetime.utcnow())
        .first()
    )
    if row:
        return json.loads(row.result_json)
    return None


def _save_cache(db: Session, ticker: str, result: dict) -> None:
    today = datetime.utcnow().date().isoformat()
    expires_at = datetime.utcnow().replace(hour=23, minute=59, second=59)
    existing = (
        db.query(AnalysisCache)
        .filter(AnalysisCache.ticker == ticker, AnalysisCache.date == today)
        .first()
    )
    if existing:
        existing.result_json = json.dumps(result)
        existing.expires_at = expires_at
        existing.outlook_score = result.get("outlook_score")
    else:
        db.add(AnalysisCache(
            ticker=ticker,
            date=today,
            result_json=json.dumps(result),
            outlook_score=result.get("outlook_score"),
            expires_at=expires_at,
        ))
    db.commit()


@router.get("/analyze", response_class=HTMLResponse)
async def analyze_get(request: Request, ticker: str = "", db: Session = Depends(get_db)):
    if not ticker:
        return templates.TemplateResponse("analyze.html", {"request": request, "result": None, "error": None, "ticker": ""})

    ticker = ticker.upper().strip()
    error = None
    result = None

    cached = _get_cached(db, ticker)
    if cached:
        result = cached
    else:
        try:
            result = analyze_ticker(ticker)
            _save_cache(db, ticker, result)
        except ValueError as e:
            error = str(e)
        except Exception as e:
            error = f"Analysis failed: {e}"

    return templates.TemplateResponse(
        "analyze.html",
        {"request": request, "result": result, "error": error, "ticker": ticker},
    )


@router.post("/analyze", response_class=HTMLResponse)
async def analyze_post(request: Request):
    form = await request.form()
    ticker = str(form.get("ticker", "")).upper().strip()
    return RedirectResponse(url=f"/analyze?ticker={ticker}", status_code=303)
