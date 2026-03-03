from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["tribute"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/tribute", response_class=HTMLResponse)
async def tribute_page(request: Request):
    return templates.TemplateResponse("tribute.html", {"request": request})
