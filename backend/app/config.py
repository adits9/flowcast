from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: str = f"sqlite:///{ROOT / 'data/flowcast.db'}"
    redis_url: str = ""
    demo_mode: bool = True
    campus_name: str = "Northwood University"
    campus_timezone: str = "America/Chicago"
    simulation_interval: int = Field(default=20, ge=5, le=3600)
    checkin_expiry_hours: int = Field(default=3, ge=1, le=24)
    sensor_api_key: str = ""
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
    model_path: Path = ROOT / "artifacts/forecast.joblib"


settings = Settings()
