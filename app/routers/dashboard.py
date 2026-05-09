import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.services.breadth import calculate_nyse_highs_lows
from app.services.fear_greed import calculate_fear_greed
from app.services.market_data import fetch_index_quotes
from app.templating import templates

router = APIRouter(tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    indices, fear_greed, hl_data = await asyncio.gather(
        asyncio.to_thread(fetch_index_quotes),
        asyncio.to_thread(calculate_fear_greed),
        asyncio.to_thread(calculate_nyse_highs_lows),
    )
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "indices": indices,
            "fear_greed": fear_greed,
            "hl_data": hl_data,
        },
    )
