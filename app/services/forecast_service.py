"""Forecast service — rule-based dummy logic for Week 1."""

import math
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.tables import Order
from app.schemas.forecast import ForecastResponse, HourlyForecast

# Hourly demand multipliers based on typical restaurant traffic curves.
# Index 0 = midnight, index 12 = noon, index 19 = 7 PM dinner peak.
HOURLY_WEIGHT: dict[int, float] = {
    0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0,
    6: 0.05, 7: 0.10, 8: 0.15, 9: 0.10, 10: 0.08,
    11: 0.30, 12: 0.80, 13: 1.00, 14: 0.60, 15: 0.20,
    16: 0.15, 17: 0.40, 18: 0.70, 19: 1.00, 20: 0.90,
    21: 0.50, 22: 0.20, 23: 0.05,
}

WEEKEND_MULTIPLIER = 1.4


async def generate_forecast(
    db: AsyncSession,
    target_date: date,
) -> ForecastResponse:
    """Generate an hourly forecast for *target_date* using historical averages.

    Falls back to a base of 30 covers/hour if no historical data exists.
    """
    # Pull the average daily covers from the last 90 days of orders
    cutoff = datetime.now() - timedelta(days=90)
    stmt = (
        select(func.avg(Order.covers))
        .where(Order.timestamp >= cutoff)
    )
    result = await db.execute(stmt)
    avg_covers = result.scalar()

    base_daily_covers: float = float(avg_covers) if avg_covers else 30.0

    is_weekend = target_date.weekday() >= 5

    hourly: list[HourlyForecast] = []
    for hour in range(24):
        weight = HOURLY_WEIGHT.get(hour, 0.0)
        predicted = base_daily_covers * weight
        if is_weekend:
            predicted *= WEEKEND_MULTIPLIER
        hourly.append(
            HourlyForecast(hour=hour, predicted_covers=max(0, math.ceil(predicted)))
        )

    return ForecastResponse(forecast_date=target_date, hourly_forecast=hourly)
