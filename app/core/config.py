from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    app_name: str = "GeoMeasure API"
    app_version: str = "1.0.0"
    debug: bool = False
    upload_dir: Path = Path("uploads")


settings = Settings()

# Ensure upload directory exists at import time
settings.upload_dir.mkdir(parents=True, exist_ok=True)
