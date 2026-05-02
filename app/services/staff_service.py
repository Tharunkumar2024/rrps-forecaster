"""Staff planning service — rule-based allocation for Week 1."""

import math
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.tables import Staff
from app.schemas.forecast import ForecastResponse
from app.schemas.staff_plan import (
    HourlyStaffPlan,
    RoleAllocation,
    StaffPlanResponse,
)

# Fallback efficiency if no staff records exist
DEFAULT_EFFICIENCY: dict[str, float] = {
    "waiter": 15.0,   # 1 waiter handles ~15 covers/hour
    "chef": 20.0,     # 1 chef handles ~20 covers/hour
    "host": 50.0,     # 1 host per 50 covers/hour
}

MINIMUM_STAFF: dict[str, int] = {
    "waiter": 1,
    "chef": 1,
    "host": 1,
}


async def generate_staff_plan(
    db: AsyncSession,
    forecast: ForecastResponse,
) -> StaffPlanResponse:
    """Derive per-hour, per-role staffing from the demand forecast.

    Rule: staff_needed = ceil(predicted_covers / efficiency_factor).
    Ensures a minimum of 1 per role during operating hours.
    """
    # Load efficiency factors from DB
    stmt = select(Staff)
    result = await db.execute(stmt)
    staff_records = result.scalars().all()

    efficiency_map: dict[str, float] = dict(DEFAULT_EFFICIENCY)
    for s in staff_records:
        efficiency_map[s.role] = s.efficiency_factor

    hourly_plan: list[HourlyStaffPlan] = []
    for h in forecast.hourly_forecast:
        if h.predicted_covers == 0:
            hourly_plan.append(HourlyStaffPlan(hour=h.hour, roles=[]))
            continue

        roles: list[RoleAllocation] = []
        for role, efficiency in efficiency_map.items():
            raw_count = math.ceil(h.predicted_covers / efficiency)
            count = max(raw_count, MINIMUM_STAFF.get(role, 1))
            roles.append(RoleAllocation(role=role, count=count))

        hourly_plan.append(HourlyStaffPlan(hour=h.hour, roles=roles))

    return StaffPlanResponse(
        plan_date=forecast.forecast_date,
        hourly_plan=hourly_plan,
    )
