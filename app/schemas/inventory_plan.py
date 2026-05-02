"""Pydantic response schemas for the inventory-plan endpoint."""

from datetime import date

from pydantic import BaseModel, Field


class IngredientNeed(BaseModel):
    """Quantity needed for a single ingredient."""

    ingredient_name: str
    quantity_kg: float = Field(..., ge=0, description="Estimated quantity in kg")
    shelf_life_days: int
    lead_time_days: int


class InventoryPlanResponse(BaseModel):
    """Full daily inventory plan response."""

    plan_date: date
    ingredients: list[IngredientNeed]
