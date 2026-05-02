"""In-memory model store — loaded once at startup, used by services.

This module provides a simple singleton approach via module-level state.
No class needed — functional style per coding_rules.
"""

import logging
from pathlib import Path
from typing import Any

import joblib

logger = logging.getLogger(__name__)

# Module-level state: the loaded model object
_forecast_model: Any | None = None
_is_model_loaded: bool = False


def load_forecast_model(model_path: Path) -> bool:
    """Load the forecast model from disk into memory.

    Returns True if successful, False otherwise.
    """
    global _forecast_model, _is_model_loaded

    if not model_path.exists():
        logger.warning("Forecast model not found at %s — using rule-based fallback", model_path)
        _forecast_model = None
        _is_model_loaded = False
        return False

    try:
        _forecast_model = joblib.load(model_path)
        _is_model_loaded = True
        logger.info("Forecast model loaded successfully from %s", model_path)
        return True
    except Exception as exc:
        logger.error("Failed to load forecast model: %s", exc)
        _forecast_model = None
        _is_model_loaded = False
        return False


def get_forecast_model() -> Any | None:
    """Return the in-memory forecast model, or None if not loaded."""
    return _forecast_model


def is_model_available() -> bool:
    """Check if the ML model is loaded and ready for inference."""
    return _is_model_loaded
