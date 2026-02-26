from datetime import datetime

from pydantic import BaseModel


class WatchlistCreate(BaseModel):
    ticker: str
    name: str | None = None
    user_id: str | None = None


class WatchlistRead(BaseModel):
    id: int
    ticker: str
    name: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class Signal(BaseModel):
    name: str
    value: str
    interpretation: str
    direction: str  # "bullish" | "bearish" | "neutral"


class Prediction(BaseModel):
    days: int
    low: float
    target: float
    high: float
    direction: str  # "bullish" | "bearish" | "neutral"


class AnalysisResponse(BaseModel):
    ticker: str
    company_name: str
    sector: str
    current_price: float
    price_change: float
    price_change_pct: float
    # Key indicator values
    sma50: float | None
    sma200: float | None
    rsi: float | None
    macd: float | None
    macd_signal: float | None
    bb_upper: float | None
    bb_lower: float | None
    # Outlook
    outlook: str  # "bullish" | "bearish" | "neutral"
    outlook_score: float  # -1.0 to 1.0
    signals: list[Signal]
    # Predictions
    predictions: list[Prediction]
    # Key levels
    support_levels: list[float]
    resistance_levels: list[float]
    fib_levels: dict[str, float]
    # Chart data
    chart_json: str
    last_updated: datetime
