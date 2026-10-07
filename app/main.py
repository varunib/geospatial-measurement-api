from fastapi import FastAPI
from app.core.config import settings
from app.api.routes import files

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A REST API for processing geospatial files and calculating geographic measurements.",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(files.router, prefix="/api/files", tags=["Files"])


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}
