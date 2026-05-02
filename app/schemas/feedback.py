"""Pydantic schemas for the feedback API."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    """Input payload for submitting feedback."""

    target_date: date = Field(..., description="Date the forecast was for (YYYY-MM-DD)")
    predicted_covers: int = Field(..., ge=0, description="Covers predicted by the system")
    actual_covers: int = Field(..., ge=0, description="Actual covers recorded on the day")
    reason: Optional[str] = Field(None, description="Reason code (e.g., 'rain', 'event', 'holiday')")
    notes: Optional[str] = Field(None, description="Free-text notes from the manager")


class FeedbackResponse(BaseModel):
    """Response after submitting feedback."""

    id: str
    target_date: date
    predicted_covers: int
    actual_covers: int
    error_count: int
    reason: Optional[str]
    notes: Optional[str]
    status: str = "success"
