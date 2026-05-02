"""Staff optimization service using Google OR-Tools CP-SAT solver."""

import logging
import math

from ortools.sat.python import cp_model
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.tables import Staff
from app.schemas.forecast import ForecastResponse
from app.schemas.staff_plan import (
    HourlyStaffPlan,
    RoleAllocation,
    StaffPlanResponse,
)

logger = logging.getLogger(__name__)

# Fallback efficiencies if DB is empty
DEFAULT_EFFICIENCY: dict[str, float] = {
    "waiter": 15.0,   # covers/hour
    "chef": 20.0,     # covers/hour (dishes handled implicitly)
    "host": 50.0,     # covers/hour
}

MINIMUM_STAFF: dict[str, int] = {
    "waiter": 1,
    "chef": 1,
    "host": 1,
}

DISHES_PER_COVER = 1.5


def _fallback_staff_plan(forecast: ForecastResponse, efficiency_map: dict[str, float]) -> StaffPlanResponse:
    """Rule-based fallback if OR-Tools optimization fails."""
    logger.warning("Using rule-based fallback for staff planning.")
    hourly_plan: list[HourlyStaffPlan] = []
    
    for h in forecast.hourly_forecast:
        if h.predicted_covers == 0:
            hourly_plan.append(HourlyStaffPlan(hour=h.hour, roles=[]))
            continue

        roles: list[RoleAllocation] = []
        for role, efficiency in efficiency_map.items():
            # Adjust target for chef if we assume efficiency was dishes/hour
            target = h.predicted_covers * DISHES_PER_COVER if role == "chef" else h.predicted_covers
            raw_count = math.ceil(target / efficiency)
            count = max(raw_count, MINIMUM_STAFF.get(role, 1))
            roles.append(RoleAllocation(role=role, count=count))

        hourly_plan.append(HourlyStaffPlan(hour=h.hour, roles=roles))

    return StaffPlanResponse(plan_date=forecast.forecast_date, hourly_plan=hourly_plan)


def _optimize_hour(predicted_covers: int, efficiency_map: dict[str, float]) -> list[RoleAllocation]:
    """Optimize staffing for a single hour using CP-SAT solver."""
    if predicted_covers == 0:
        return []

    model = cp_model.CpModel()
    
    # Variables
    staff_vars = {}
    for role in efficiency_map.keys():
        min_staff = MINIMUM_STAFF.get(role, 1)
        # Upper bound: a safe max value to prevent unbounded domain
        max_staff = max(min_staff, math.ceil(predicted_covers * DISHES_PER_COVER / min(efficiency_map.values())) * 2 + 5)
        staff_vars[role] = model.NewIntVar(min_staff, max_staff, f"staff_{role}")
        
    # Constraints: Capacity must meet demand
    # For independent roles, each must individually meet the required demand
    for role, efficiency in efficiency_map.items():
        # Using integer arithmetic for the solver. 
        # efficiency * count >= target_demand -> target_demand can be scaled by 10 to allow fractional efficiency
        eff_int = int(efficiency * 10)
        target = predicted_covers * DISHES_PER_COVER if role == "chef" else predicted_covers
        target_int = int(target * 10)
        
        model.Add(staff_vars[role] * eff_int >= target_int)
        
    # Objective: Minimize total headcount
    model.Minimize(sum(staff_vars.values()))
    
    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        roles = []
        for role, var in staff_vars.items():
            roles.append(RoleAllocation(role=role, count=int(solver.Value(var))))
        return roles
    else:
        raise RuntimeError("OR-Tools failed to find a feasible solution.")


async def generate_staff_plan(
    db: AsyncSession,
    forecast: ForecastResponse,
) -> StaffPlanResponse:
    """Generate per-hour, per-role staffing optimized by OR-Tools."""
    # Load efficiency factors from DB
    stmt = select(Staff)
    result = await db.execute(stmt)
    staff_records = result.scalars().all()

    efficiency_map: dict[str, float] = dict(DEFAULT_EFFICIENCY)
    for s in staff_records:
        efficiency_map[s.role] = s.efficiency_factor

    hourly_plan: list[HourlyStaffPlan] = []
    
    try:
        for h in forecast.hourly_forecast:
            if h.predicted_covers == 0:
                hourly_plan.append(HourlyStaffPlan(hour=h.hour, roles=[]))
                continue
                
            roles = _optimize_hour(h.predicted_covers, efficiency_map)
            hourly_plan.append(HourlyStaffPlan(hour=h.hour, roles=roles))
            
        return StaffPlanResponse(
            plan_date=forecast.forecast_date,
            hourly_plan=hourly_plan,
        )
    except Exception as exc:
        logger.error("Optimization engine error: %s", exc)
        return _fallback_staff_plan(forecast, efficiency_map)
