from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import initialize_database
from app.routers import alerts, auth, clips, fusion, ndvi, organizations, regions, satellite_changes, sensors
from app.schemas import HealthResponse


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_database()
    yield


settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="canopy-api")


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(organizations.router, prefix="/api/organizations", tags=["organizations"])
app.include_router(regions.router, prefix="/api/regions", tags=["regions"])
app.include_router(sensors.router, prefix="/api/sensors", tags=["sensors"])
app.include_router(satellite_changes.router, prefix="/api/satellite-changes", tags=["satellite-changes"])
app.include_router(ndvi.router, prefix="/api/ndvi", tags=["ndvi"])
app.include_router(fusion.router, prefix="/api/fusion", tags=["fusion"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(clips.router, prefix="/api/clips", tags=["clips"])
