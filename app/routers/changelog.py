from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.templating import templates

router = APIRouter(tags=["changelog"])

ENTRIES = [
    {
        "version": "v1.5",
        "date": "Mar 2026",
        "type": "new",
        "changes": [
            "Added Changelog page so visitors can track updates",
        ],
    },
    {
        "version": "v1.4",
        "date": "Feb 2026",
        "type": "fix",
        "changes": [
            "Fixed Fear & Greed history chart line rendering",
            "Removed Quick Analyze shortcut (redundant with main Analyze page)",
        ],
    },
    {
        "version": "v1.3",
        "date": "Feb 2026",
        "type": "new",
        "changes": [
            "Added Fear & Greed Index widget to dashboard with historical chart",
            "Removed Watchlist section from dashboard for a cleaner layout",
            "Moved system health indicator to top of dashboard",
        ],
    },
    {
        "version": "v1.2",
        "date": "Jan 2026",
        "type": "new",
        "changes": [
            "Added Technical Analysis Course as a subpage under Concepts",
            "Added Valuation Measures section to analysis output",
            "Extended default chart range to 2 years",
        ],
    },
    {
        "version": "v1.1",
        "date": "Jan 2026",
        "type": "fix",
        "changes": [
            "Fixed Internal Server Error on certain ticker lookups",
            "Fixed Concepts page links opening in new tabs",
        ],
    },
    {
        "version": "v1.0",
        "date": "Dec 2025",
        "type": "new",
        "changes": [
            "Initial release — Murphy Trend is live",
            "Dashboard with S&P 500, DOW, NASDAQ live prices",
            "Full technical analysis engine: trend, retracements, patterns, MAs, volume, oscillators, Bollinger Bands",
            "30 / 60 / 90-day price predictions with plain-English Murphy Outlook",
            "Murphy Concepts reference page",
            "John J. Murphy Tribute page",
            "Dark mode toggle",
        ],
    },
]


@router.get("/changelog", response_class=HTMLResponse)
async def changelog_page(request: Request):
    return templates.TemplateResponse(
        "changelog.html", {"request": request, "entries": ENTRIES}
    )
