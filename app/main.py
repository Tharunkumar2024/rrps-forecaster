"""FastAPI application entry point with lifespan context manager."""

import time
import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.core.model_store import load_forecast_model
from app.jobs.retrain_job import perform_retraining

settings = get_settings()

# 1. Initialize structured logging
setup_logging(level=10 if settings.debug else 20)  # DEBUG=10, INFO=20
import logging
logger = logging.getLogger(__name__)

# Scheduler instance
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup / shutdown lifecycle."""
    logger.info("Starting %s (%s)", settings.app_name, settings.app_env)

    # 1. Load ML model into memory at startup
    is_loaded = load_forecast_model(settings.forecast_model_path)
    if is_loaded:
        logger.info("ML forecast model ready for inference")
    else:
        logger.warning("ML model not found — API will use rule-based fallback until model is trained")

    # 2. Setup automated model retraining job (daily at 02:00 AM)
    # Using thread pool executor (default for apscheduler blocking functions)
    scheduler.add_job(
        perform_retraining,
        "cron",
        hour=2,
        minute=0,
        id="daily_retrain_job",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Automated model retraining scheduler started.")

    yield

    logger.info("Shutting down %s", settings.app_name)
    scheduler.shutdown()


app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    description="AI-powered restaurant demand, staffing, and inventory optimization system.",
    lifespan=lifespan,
)

# 2. Add metrics instrumentation
Instrumentator().instrument(app).expose(app, tags=["System"])

# 3. Request tracking middleware
@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    """Log requests and measure latency."""
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Bind request id context logically
    logger.info(
        "Request started",
        extra={
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url.path),
        }
    )
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "status_code": response.status_code,
                "latency_ms": round(process_time * 1000, 2),
            }
        )
        return response
    except Exception as exc:
        process_time = time.time() - start_time
        logger.error(
            "Request failed",
            extra={
                "request_id": request_id,
                "latency_ms": round(process_time * 1000, 2),
                "error": str(exc),
            },
            exc_info=True,
        )
        raise

# CORS — allow all origins in dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server via python main.py with host={settings.host}, port={settings.port}, reload={settings.reload}")
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.reload)
