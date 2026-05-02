"""Feedback service — validates, computes errors, and stores real-world results."""

import logging
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import Feedback
from app.schemas.feedback import FeedbackCreate, FeedbackResponse

logger = logging.getLogger(__name__)


async def process_feedback(
    db: AsyncSession,
    payload: FeedbackCreate,
) -> FeedbackResponse:
    """Process and store a feedback record.
    
    Computes error_count = actual_covers - predicted_covers
    and saves to DB.
    """
    error_count = payload.actual_covers - payload.predicted_covers
    
    new_id = str(uuid.uuid4())
    feedback_record = Feedback(
        id=new_id,
        feedback_date=payload.target_date,
        predicted=payload.predicted_covers,
        actual=payload.actual_covers,
        reason=payload.reason,
        notes=payload.notes,
    )
    
    db.add(feedback_record)
    
    logger.info(
        "Feedback stored for %s: predicted=%d, actual=%d, error=%d, reason=%s",
        payload.target_date,
        payload.predicted_covers,
        payload.actual_covers,
        error_count,
        payload.reason,
    )
    
    return FeedbackResponse(
        id=new_id,
        target_date=payload.target_date,
        predicted_covers=payload.predicted_covers,
        actual_covers=payload.actual_covers,
        error_count=error_count,
        reason=payload.reason,
        notes=payload.notes,
        status="success",
    )
