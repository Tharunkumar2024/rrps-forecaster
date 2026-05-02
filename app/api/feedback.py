"""Feedback API route for continuous improvement loop."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.services.feedback_service import process_feedback

router = APIRouter(tags=["Feedback Loop"])


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="Submit actual results",
    description="Capture actual real-world covers to compute model error and improve future forecasts.",
)
async def submit_feedback(
    payload: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    try:
        return await process_feedback(db, payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to process feedback: {exc}")
