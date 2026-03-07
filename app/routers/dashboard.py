import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.services.fear_greed import calculate_fear_greed
from app.services.market_data import fetch_index_quotes
from app.templating import templates

router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    indices = fetch_index_quotes()
    fear_greed = await asyncio.to_thread(calculate_fear_greed)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "indices": indices,
            "fear_greed": fear_greed,
        },
    )
