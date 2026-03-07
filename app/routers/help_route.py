from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.templating import templates

router = APIRouter(tags=["help"])


@router.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    return templates.TemplateResponse("help.html", {"request": request})


@router.get("/help/course", response_class=HTMLResponse)
async def course_page(request: Request):
    return templates.TemplateResponse("course.html", {"request": request})
