"""Pydantic response schemas for the staff-plan endpoint."""

from datetime import date

from pydantic import BaseModel, Field


class RoleAllocation(BaseModel):
    """Staff count for a single role in a given hour."""

    role: str
    count: int = Field(..., ge=0)


class HourlyStaffPlan(BaseModel):
    """Staff recommendation for one hour."""

    hour: int = Field(..., ge=0, le=23)
    roles: list[RoleAllocation]


class StaffPlanResponse(BaseModel):
    """Full daily staff plan response."""

    plan_date: date
    hourly_plan: list[HourlyStaffPlan]
