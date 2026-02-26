from pathlib import Path

import markdown2
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pygments.formatters import HtmlFormatter

router = APIRouter(tags=["sad"])
templates = Jinja2Templates(directory="app/templates")

SAD_PATH = Path("SAD.md")


@router.get("/sad", response_class=HTMLResponse)
async def sad(request: Request):
    if not SAD_PATH.exists():
        content_html = "<p>SAD.md not found.</p>"
    else:
        md_text = SAD_PATH.read_text(encoding="utf-8")
        content_html = markdown2.markdown(
            md_text,
            extras=["fenced-code-blocks", "tables", "header-ids", "toc", "code-friendly"],
        )

    # Pygments CSS for syntax highlighting
    formatter = HtmlFormatter(style="friendly")
    pygments_css = formatter.get_style_defs(".codehilite")

    return templates.TemplateResponse(
        "sad.html",
        {"request": request, "content_html": content_html, "pygments_css": pygments_css},
    )
