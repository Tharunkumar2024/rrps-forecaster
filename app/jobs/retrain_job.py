"""Automated model retraining job."""

import logging
import asyncio

from app.scripts.train_forecast_model import run as run_training_pipeline
from app.core.model_store import load_forecast_model

logger = logging.getLogger(__name__)


def perform_retraining() -> None:
    """Execute the model retraining pipeline synchronously."""
    try:
        logger.info("Starting automated model retraining job...")
        
        # 1. Run the offline training pipeline
        # (This reads from DB, engineers features, trains XGBoost, saves to disk)
        run_training_pipeline()
        
        # 2. Reload the newly trained model into memory safely
        load_forecast_model()
        
        logger.info("Automated model retraining completed successfully.")
    except Exception as exc:
        logger.exception("Automated model retraining failed. Keeping previous model active.", exc_info=exc)


async def schedule_retraining() -> None:
    """Wrapper to run the blocking training pipeline in a thread."""
    await asyncio.to_thread(perform_retraining)
