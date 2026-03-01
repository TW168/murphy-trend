from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["tribute"])
templates = Jinja2Templates(directory="app/templates")

CHICAGO = ZoneInfo("America/Chicago")


@router.get("/tribute", response_class=HTMLResponse)
async def tribute_page(request: Request):
    now = datetime.now(CHICAGO)
    return templates.TemplateResponse("tribute.html", {
        "request": request,
        "chicago_time": now.strftime("%B %d, %Y · %I:%M %p CT"),
    })
