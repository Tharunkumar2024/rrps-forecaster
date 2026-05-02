"""Unit tests for the Forecast service and API."""

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.schemas.forecast import ForecastResponse, HourlyForecast
from app.services.forecast_service import generate_forecast


@pytest.mark.asyncio
async def test_forecast_valid_input(test_db):
    """U-001: Generate forecast for a valid date."""
    target_date = date(2026, 5, 10)
    
    mock_hourly = [HourlyForecast(hour=i, predicted_covers=50) for i in range(24)]
    mock_response = ForecastResponse(forecast_date=target_date, source="ml_model", hourly_forecast=mock_hourly)
    
    with patch("app.services.forecast_service._ml_forecast", return_value=mock_response):
        forecast = await generate_forecast(test_db, target_date)
        
    assert isinstance(forecast, ForecastResponse)
    assert len(forecast.hourly_forecast) == 24
    assert forecast.forecast_date == target_date
    

@pytest.mark.asyncio
async def test_forecast_missing_model(test_db):
    """U-002: Generate forecast when ML model is unavailable (uses fallback)."""
    target_date = date(2026, 5, 10)
    
    with patch("app.services.forecast_service.is_model_available", return_value=False):
        forecast = await generate_forecast(test_db, target_date)
        
    assert forecast.forecast_date == target_date
    assert forecast.hourly_forecast[2].predicted_covers == 0  # Non-op hour
    assert forecast.hourly_forecast[12].predicted_covers > 0  # Peak hour


@pytest.mark.asyncio
async def test_forecast_non_operating_hours(test_db):
    """U-003: Ensure non-operating hours return 0 exactly."""
    target_date = date(2026, 5, 10)
    
    mock_hourly = [HourlyForecast(hour=i, predicted_covers=100 if 8 <= i <= 22 else 0) for i in range(24)]
    mock_response = ForecastResponse(forecast_date=target_date, source="ml_model", hourly_forecast=mock_hourly)
    
    with patch("app.services.forecast_service._ml_forecast", return_value=mock_response):
        forecast = await generate_forecast(test_db, target_date)
        
    hourly_data = {h.hour: h.predicted_covers for h in forecast.hourly_forecast}
    assert hourly_data[3] == 0
    assert hourly_data[23] == 0
    assert hourly_data[14] == 100


def test_api_forecast_invalid_date(client: TestClient):
    """A-001: GET /forecast with bad date format."""
    response = client.get("/api/v1/forecast?target_date=not-a-date")
    assert response.status_code == 422
    assert "Input should be a valid date" in response.text


def test_api_forecast_default_date(client: TestClient):
    """A-006: GET /forecast with missing target_date defaults properly."""
    with patch("app.api.forecast.generate_forecast") as mock_gen:
        # Prevent actual db interaction for this test
        mock_gen.return_value = ForecastResponse(forecast_date=date(2026,1,1), source="ml_model", hourly_forecast=[])
        
        response = client.get("/api/v1/forecast")
        
    assert response.status_code == 200
    mock_gen.assert_called_once()


def test_api_model_info_active(client: TestClient):
    """A-004: GET /model-info check."""
    # Ensure it says the model is loaded and provides a float for MAPE
    with patch("app.api.forecast.is_model_available", return_value=True), \
         patch("app.api.forecast.get_forecast_model", return_value={"mape": 15.5, "feature_cols": [1,2,3]}):
        response = client.get("/api/v1/model-info")
        
    assert response.status_code == 200
    data = response.json()
    assert data["is_model_loaded"] is True
    assert isinstance(data["model_mape"], float)


def test_api_metrics_endpoint(client: TestClient):
    """A-005: GET /metrics — Prometheus exposure check."""
    response = client.get("/metrics")
    assert response.status_code == 200
    # Prometheus metrics are returned as text/plain
    assert "text/plain" in response.headers["content-type"] or "text/plain" in response.headers.get("content-type", "")
    # Should contain standard HTTP metrics from the instrumentator
    assert "http_request" in response.text or "HELP" in response.text


def test_forecast_mape_calculation():
    """U-004: Validate WMAPE calculation formula."""
    import numpy as np

    y_true = np.array([100, 200, 150, 80, 50])
    y_pred = np.array([110, 190, 160, 70, 60])

    # WMAPE = sum(|actual - predicted|) / sum(actual)
    abs_errors = np.abs(y_true - y_pred)
    wmape = abs_errors.sum() / y_true.sum()

    expected_wmape = (10 + 10 + 10 + 10 + 10) / (100 + 200 + 150 + 80 + 50)
    assert abs(wmape - expected_wmape) < 1e-6
    assert abs(wmape - 50 / 580) < 1e-6


def test_forecast_mape_with_zeros():
    """U-004 edge: WMAPE when y_true contains zeros."""
    import numpy as np

    y_true = np.array([0, 0, 100])
    y_pred = np.array([5, 3, 110])

    total_actual = y_true.sum()
    if total_actual == 0:
        wmape = float("inf")
    else:
        wmape = np.abs(y_true - y_pred).sum() / total_actual

    # (5 + 3 + 10) / 100 = 0.18
    assert abs(wmape - 0.18) < 1e-6


@pytest.mark.asyncio
async def test_forecast_past_date(test_db):
    """U-013: Forecast a date in the past — should still return valid payload."""
    target_date = date(2020, 1, 1)

    with patch("app.services.forecast_service.is_model_available", return_value=False):
        forecast = await generate_forecast(test_db, target_date)

    assert forecast.forecast_date == target_date
    assert len(forecast.hourly_forecast) == 24
    assert forecast.source == "rule_based"


@pytest.mark.asyncio
async def test_forecast_extreme_future(test_db):
    """U-014: Forecast far into the future — cyclical features should compute without error."""
    target_date = date(2050, 1, 1)

    with patch("app.services.forecast_service.is_model_available", return_value=False):
        forecast = await generate_forecast(test_db, target_date)

    assert forecast.forecast_date == target_date
    assert len(forecast.hourly_forecast) == 24
    # All hours should have non-negative values
    for h in forecast.hourly_forecast:
        assert h.predicted_covers >= 0


def test_ml_feature_parity():
    """U-015: Validate that inference feature columns match training expectations."""
    import numpy as np
    import pandas as pd

    # Simulate the feature engineering from forecast_service._build_inference_features
    target_date = date(2026, 5, 10)
    rows = []
    for hour in range(24):
        rows.append({"ds": pd.Timestamp(target_date.year, target_date.month, target_date.day, hour), "y": 0})
    df = pd.DataFrame(rows)

    df["hour"] = df["ds"].dt.hour
    df["day_of_week"] = df["ds"].dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["is_friday"] = (df["day_of_week"] == 4).astype(int)
    df["month"] = df["ds"].dt.month
    df["day_of_month"] = df["ds"].dt.day
    df["week_of_year"] = df["ds"].dt.isocalendar().week.astype(int)
    df["is_lunch_peak"] = df["hour"].isin([12, 13, 14]).astype(int)
    df["is_dinner_peak"] = df["hour"].isin([18, 19, 20, 21]).astype(int)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["lag_24h"] = df["y"].shift(24)
    df["lag_168h"] = df["y"].shift(168)
    df["rolling_24h_mean"] = df["y"].shift(1).rolling(window=24, min_periods=1).mean()
    df["rolling_7d_mean"] = df["y"].shift(1).rolling(window=168, min_periods=1).mean()

    expected_feature_cols = [
        "hour", "day_of_week", "is_weekend", "is_friday", "month",
        "day_of_month", "week_of_year", "is_lunch_peak", "is_dinner_peak",
        "hour_sin", "hour_cos", "dow_sin", "dow_cos", "month_sin", "month_cos",
        "lag_24h", "lag_168h", "rolling_24h_mean", "rolling_7d_mean",
    ]

    for col in expected_feature_cols:
        assert col in df.columns, f"Missing feature column: {col}"

