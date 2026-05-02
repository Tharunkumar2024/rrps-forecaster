"""Pydantic response schemas for the forecast endpoint."""

from datetime import date

from pydantic import BaseModel, Field


class HourlyForecast(BaseModel):
    """Single hour prediction."""

    hour: int = Field(..., ge=0, le=23, description="Hour of day (0-23)")
    predicted_covers: int = Field(..., ge=0, description="Predicted customer count")


class ForecastResponse(BaseModel):
    """Full daily forecast response."""

    forecast_date: date
    source: str = Field(
        default="rule_based",
        description="Forecast source: 'ml_model' or 'rule_based'",
    )
    hourly_forecast: list[HourlyForecast]


class ModelInfoResponse(BaseModel):
    """Model status and metadata."""

    is_model_loaded: bool
    model_mape: float | None = None
    feature_count: int | None = None
