import os
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

TEST_DATA = tempfile.TemporaryDirectory(prefix="flowcast-tests-")
os.environ["DATABASE_URL"] = os.environ.get("FLOWCAST_TEST_DATABASE_URL", f"sqlite:///{TEST_DATA.name}/test.db")
os.environ["MODEL_PATH"] = str(Path(TEST_DATA.name) / "forecast.joblib")
os.environ["REDIS_URL"] = os.environ.get("FLOWCAST_TEST_REDIS_URL", "")
os.environ["DEMO_MODE"] = "true"

from fastapi.testclient import TestClient  # noqa: E402
from app import service  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    Base.metadata.drop_all(engine)
    monkeypatch.setattr(settings, "simulation_interval", 3600)
    monkeypatch.setattr(service, "local_now", lambda: datetime(2026, 10, 8, 12, 0, tzinfo=ZoneInfo("America/Chicago")))
    service.forecast_cache.clear()
    with TestClient(app) as test_client:
        yield test_client
