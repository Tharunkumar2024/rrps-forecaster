"""FastAPI application entry point with lifespan context manager."""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.model_store import load_forecast_model

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup / shutdown lifecycle."""
    logger.info("Starting %s (%s)", settings.app_name, settings.app_env)

    # Load ML model into memory at startup
    is_loaded = load_forecast_model(settings.forecast_model_path)
    if is_loaded:
        logger.info("ML forecast model ready for inference")
    else:
        logger.warning("ML model not found — API will use rule-based fallback until model is trained")

    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="AI-powered restaurant demand, staffing, and inventory optimization system.",
    lifespan=lifespan,
)

# CORS — allow all origins in dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1", tags=["Recommendations"])


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok"}
