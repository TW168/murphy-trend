from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.services.soxl import compute_indicators, evaluate_rules, fetch_soxl_data
from app.templating import templates

router = APIRouter(tags=["soxl"])


@router.get("/soxl", response_class=HTMLResponse)
async def soxl_page(request: Request):
    """Render the SOXL Examiner page with computed signals and the verdict."""
    stale = False
    try:
        df, stale = await asyncio.to_thread(fetch_soxl_data)
        result = await asyncio.to_thread(compute_indicators, df)
    except Exception as e:
        # If fetch failed and no cache, render an error message
        return templates.TemplateResponse(
            "soxl.html",
            {"request": request, "error": f"Data unavailable: {e}", "result": None, "stale": True},
        )

    diagnostics = evaluate_rules(result)
    diagnostics["stale"] = stale

    return templates.TemplateResponse(
        "soxl.html",
        {
            "request": request,
            "result": result.computed,
            "diagnostics": diagnostics,
            "stale": stale,
        },
    )


@router.get("/api/soxl", response_class=JSONResponse)
async def soxl_api(stop: float | None = None):
    """Return computed SOXL indicators and the verdict as JSON. Optional `stop` query param influences exit X2."""
    df, stale = await asyncio.to_thread(fetch_soxl_data)
    result = await asyncio.to_thread(compute_indicators, df)
    diagnostics = evaluate_rules(result, stop_price=stop)
    diagnostics["stale"] = stale
    payload: dict[str, Any] = {"computed": result.computed, "diagnostics": diagnostics}
    return JSONResponse(payload)
