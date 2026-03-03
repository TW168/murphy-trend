from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Watchlist
from app.services.market_data import fetch_index_quotes
from app.templating import templates

router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    indices = fetch_index_quotes()
    watchlist = db.query(Watchlist).order_by(Watchlist.created_at.desc()).limit(20).all()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "indices": indices, "watchlist": watchlist},
    )


@router.post("/watchlist/add")
async def add_to_watchlist(
    request: Request,
    db: Session = Depends(get_db),
):
    form = await request.form()
    ticker = str(form.get("ticker", "")).upper().strip()
    name = str(form.get("name", "")).strip() or None
    if ticker:
        existing = db.query(Watchlist).filter(Watchlist.ticker == ticker).first()
        if not existing:
            db.add(Watchlist(ticker=ticker, name=name))
            db.commit()
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=303)


@router.post("/watchlist/remove/{ticker}")
async def remove_from_watchlist(ticker: str, db: Session = Depends(get_db)):
    db.query(Watchlist).filter(Watchlist.ticker == ticker.upper()).delete()
    db.commit()
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=303)
