from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.templating import templates

router = APIRouter(tags=["tribute"])


@router.get("/tribute", response_class=HTMLResponse)
async def tribute_page(request: Request):
    return templates.TemplateResponse("tribute.html", {"request": request})
