import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import connection, initialize_database
from app.logging_config import configure_logging
from app.rate_limit import RateLimitMiddleware
from app.routers import alerts, auth, clips, fusion, model, ndvi, organizations, regions, satellite_changes, sensors
from app.schemas import HealthResponse


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging(get_settings().log_level)
    if get_settings().jwt_secret == "change-me-in-production":
        logging.getLogger("app").warning(
            "SECURITY: jwt_secret is the default value; set JWT_SECRET in the environment"
        )
    initialize_database()
    from app.services.scheduler import start_scheduler, stop_scheduler
    start_scheduler(get_settings().fusion_auto_interval_minutes)
    yield
    stop_scheduler()


settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)

# CORS is added after the rate limiter so it wraps it: 429 responses still carry CORS headers.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    db_status = "ok"
    try:
        with connection() as conn:
            conn.execute("SELECT 1")
    except Exception:
        logging.getLogger("app").exception("Health check database probe failed")
        db_status = "error"
    return HealthResponse(status="ok" if db_status == "ok" else "degraded", service="canopy-api", db=db_status)


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(organizations.router, prefix="/api/organizations", tags=["organizations"])
app.include_router(regions.router, prefix="/api/regions", tags=["regions"])
app.include_router(sensors.router, prefix="/api/sensors", tags=["sensors"])
app.include_router(satellite_changes.router, prefix="/api/satellite-changes", tags=["satellite-changes"])
app.include_router(ndvi.router, prefix="/api/ndvi", tags=["ndvi"])
app.include_router(fusion.router, prefix="/api/fusion", tags=["fusion"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(clips.router, prefix="/api/clips", tags=["clips"])
app.include_router(model.router, prefix="/api/model", tags=["model"])
