"""Staff optimization API route."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.staff_plan import StaffPlanResponse
from app.services.forecast_service import generate_forecast
from app.services.staff_planner import generate_staff_plan

router = APIRouter(tags=["Staff Planning"])


@router.get(
    "/staff-plan",
    response_model=StaffPlanResponse,
    summary="Get staff scheduling recommendation",
    description="Returns recommended staff count per role per hour optimized via OR-Tools.",
)
async def get_staff_plan(
    target_date: date = Query(
        default=None,
        description="Date to plan staff for (YYYY-MM-DD). Defaults to tomorrow.",
    ),
    db: AsyncSession = Depends(get_db),
) -> StaffPlanResponse:
    if target_date is None:
        target_date = date.today() + timedelta(days=1)

    try:
        # Step 1: Get the demand forecast
        forecast = await generate_forecast(db, target_date)
        # Step 2: Pass forecast to OR-Tools optimization engine
        return await generate_staff_plan(db, forecast)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Staff plan generation failed: {exc}")
