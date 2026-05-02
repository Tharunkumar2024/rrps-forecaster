"""Forecast service — ML-based inference with rule-based fallback."""

import logging
import math
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.model_store import get_forecast_model, is_model_available
from app.models.tables import Order
from app.schemas.forecast import ForecastResponse, HourlyForecast

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rule-based fallback (Week 1 logic kept as safety net)
# ---------------------------------------------------------------------------

HOURLY_WEIGHT: dict[int, float] = {
    0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0,
    6: 0.05, 7: 0.10, 8: 0.15, 9: 0.10, 10: 0.08,
    11: 0.30, 12: 0.80, 13: 1.00, 14: 0.60, 15: 0.20,
    16: 0.15, 17: 0.40, 18: 0.70, 19: 1.00, 20: 0.90,
    21: 0.50, 22: 0.20, 23: 0.05,
}

WEEKEND_MULTIPLIER = 1.4


async def _fallback_forecast(
    db: AsyncSession,
    target_date: date,
) -> ForecastResponse:
    """Rule-based forecast — used when ML model is unavailable."""
    cutoff = datetime.now() - timedelta(days=90)
    stmt = select(func.avg(Order.covers)).where(Order.timestamp >= cutoff)
    result = await db.execute(stmt)
    avg_covers = result.scalar()

    base_daily_covers: float = float(avg_covers) if avg_covers else 30.0
    is_weekend = target_date.weekday() >= 5

    hourly: list[HourlyForecast] = []
    for hour in range(24):
        weight = HOURLY_WEIGHT.get(hour, 0.0)
        predicted = base_daily_covers * weight
        if is_weekend: predicted *= WEEKEND_MULTIPLIER
        hourly.append(
            HourlyForecast(hour=hour, predicted_covers=max(0, math.ceil(predicted)))
        )

    return ForecastResponse(forecast_date=target_date, source="rule_based", hourly_forecast=hourly)


# ---------------------------------------------------------------------------
# ML-based forecast
# ---------------------------------------------------------------------------

async def _build_inference_features(
    db: AsyncSession,
    target_date: date,
) -> pd.DataFrame:
    """Build the feature matrix for all 24 hours of target_date.

    Needs historical data for lag/rolling features.
    """
    # Fetch last 8 days of hourly covers to compute lags + rolling
    lookback_start = datetime.combine(target_date - timedelta(days=8), datetime.min.time())
    stmt = (
        select(Order.timestamp, Order.covers)
        .where(Order.timestamp >= lookback_start)
        .order_by(Order.timestamp)
    )
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return pd.DataFrame()

    hist_df = pd.DataFrame(rows, columns=["timestamp", "covers"])
    hist_df["timestamp"] = pd.to_datetime(hist_df["timestamp"])
    hist_df = (
        hist_df.set_index("timestamp")
        .resample("h")["covers"]
        .sum()
        .reset_index()
    )
    hist_df.rename(columns={"timestamp": "ds", "covers": "y"}, inplace=True)

    # Append target_date hours ONLY if they aren't already in hist_df
    target_rows = []
    existing_hours = set(hist_df["ds"]) if not hist_df.empty else set()
    for hour in range(24):
        dt = datetime(target_date.year, target_date.month, target_date.day, hour)
        if dt not in existing_hours:
            target_rows.append({"ds": dt, "y": 0})
            
    if target_rows:
        target_df = pd.DataFrame(target_rows)
        full_df = pd.concat([hist_df, target_df], ignore_index=True)
    else:
        full_df = hist_df.copy()
        
    full_df.sort_values("ds", inplace=True)
    full_df.reset_index(drop=True, inplace=True)

    # Feature engineering — same as training
    full_df["hour"] = full_df["ds"].dt.hour
    full_df["day_of_week"] = full_df["ds"].dt.dayofweek
    full_df["is_weekend"] = (full_df["day_of_week"] >= 5).astype(int)
    full_df["is_friday"] = (full_df["day_of_week"] == 4).astype(int)
    full_df["month"] = full_df["ds"].dt.month
    full_df["day_of_month"] = full_df["ds"].dt.day
    full_df["week_of_year"] = full_df["ds"].dt.isocalendar().week.astype(int)

    # Peak hour indicators
    full_df["is_lunch_peak"] = full_df["hour"].isin([12, 13, 14]).astype(int)
    full_df["is_dinner_peak"] = full_df["hour"].isin([18, 19, 20, 21]).astype(int)

    # Cyclical encodings
    full_df["hour_sin"] = np.sin(2 * np.pi * full_df["hour"] / 24)
    full_df["hour_cos"] = np.cos(2 * np.pi * full_df["hour"] / 24)
    full_df["dow_sin"] = np.sin(2 * np.pi * full_df["day_of_week"] / 7)
    full_df["dow_cos"] = np.cos(2 * np.pi * full_df["day_of_week"] / 7)
    full_df["month_sin"] = np.sin(2 * np.pi * full_df["month"] / 12)
    full_df["month_cos"] = np.cos(2 * np.pi * full_df["month"] / 12)

    full_df["lag_24h"] = full_df["y"].shift(24)
    full_df["lag_168h"] = full_df["y"].shift(168)

    full_df["rolling_24h_mean"] = full_df["y"].shift(1).rolling(window=24, min_periods=1).mean()
    full_df["rolling_7d_mean"] = full_df["y"].shift(1).rolling(window=168, min_periods=1).mean()

    # Extract only the target_date rows
    target_mask = full_df["ds"].dt.date == target_date
    inference_df = full_df[target_mask].copy()

    return inference_df


async def _ml_forecast(
    db: AsyncSession,
    target_date: date,
) -> ForecastResponse:
    """Generate forecast using the loaded ML model."""
    artifact = get_forecast_model()
    model = artifact["model"]
    feature_cols = artifact["feature_cols"]
    operating_hours = set(artifact.get("operating_hours", range(6, 24)))

    inference_df = await _build_inference_features(db, target_date)

    # Filter to operating hours only (model was only trained on these)
    op_df = inference_df[inference_df["hour"].isin(operating_hours)].copy()

    if op_df.empty or op_df[feature_cols].isnull().any().any():
        null_counts = op_df[feature_cols].isnull().sum()
        logger.warning("Insufficient historical data for ML inference — falling back to rules. Nulls: \n%s", null_counts[null_counts > 0])
        return await _fallback_forecast(db, target_date)

    x_input = op_df[feature_cols]
    predictions = model.predict(x_input)
    predictions = np.maximum(predictions, 0).round().astype(int)

    # Build full 24-hour result — 0 for non-operating hours
    pred_map = dict(zip(op_df["hour"].values, predictions))
    hourly: list[HourlyForecast] = []
    for hour in range(24):
        covers = int(pred_map.get(hour, 0))
        hourly.append(HourlyForecast(hour=hour, predicted_covers=covers))

    return ForecastResponse(forecast_date=target_date, source="ml_model", hourly_forecast=hourly)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_forecast(
    db: AsyncSession,
    target_date: date,
) -> ForecastResponse:
    """Generate an hourly forecast — ML model if available, else rule-based fallback."""
    if not is_model_available():
        logger.info("ML model not loaded — using rule-based fallback for %s", target_date)
        return await _fallback_forecast(db, target_date)

    try:
        return await _ml_forecast(db, target_date)
    except Exception as exc:
        logger.error("ML forecast failed: %s — falling back to rules", exc)
        return await _fallback_forecast(db, target_date)
