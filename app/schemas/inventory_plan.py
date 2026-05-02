"""Pydantic response schemas for the inventory-plan endpoint."""

from datetime import date

from typing import Optional

from pydantic import BaseModel, Field


class InventoryRequest(BaseModel):
    """Input payload for generating an inventory plan."""

    target_date: Optional[date] = Field(
        None, description="Date to plan inventory for (YYYY-MM-DD). Defaults to tomorrow."
    )
    current_stock: dict[str, float] = Field(
        default_factory=dict,
        description="Dictionary mapping ingredient name to current stock in kg.",
    )

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
