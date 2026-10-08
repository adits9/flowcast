import csv
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.config import settings
from app.database import Location, Session
from app.forecast import Forecaster, demand, observed_rows, train, wait_for


def test_observed_training_and_inference(client, tmp_path, monkeypatch):
    csv_path = tmp_path / "observations.csv"
    with csv_path.open("w", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(
            ["location_id", "observed_at", "occupancy", "wait_minutes", "temperature_c", "rain_mm", "event_impact"]
        )
        start = datetime(2026, 9, 1, tzinfo=ZoneInfo("America/Chicago"))
        for slot in range(6 * 96):
            when = start + timedelta(minutes=slot * 15)
            ratio = demand("library", when)
            writer.writerow(["library", when.isoformat(), round(ratio * 240), wait_for("study", ratio), 19, 0, 0])
    model_path = tmp_path / "observed.joblib"
    artifact = train(model_path, csv_path)
    assert artifact["metadata"]["source"] == "observed"
    assert artifact["metadata"]["trained_location_ids"] == ["library"]
    assert artifact["metadata"]["validation_rows"] > 0
    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "model_path", model_path)
    model = Forecaster()
    with Session() as session:
        library, untrained = session.get(Location, "library"), session.get(Location, "hub")
        weather = {"temperature_c": 19, "rain_mm": 0}
        assert len(model.predict(library, start.replace(hour=12), 0.5, weather, 0)) == 8
        assert model.predict(untrained, start.replace(hour=12), 0.5, weather, 0) == []


def test_training_rejects_naive_times_and_insufficient_observations(tmp_path):
    assert wait_for("dining", 0.05) == 0
    csv_path = tmp_path / "invalid.csv"
    header = "location_id,observed_at,occupancy,wait_minutes,temperature_c,rain_mm,event_impact\n"
    csv_path.write_text(header + "library,2026-09-01T12:00:00,100,2,19,0,0\n")
    with pytest.raises(ValueError, match="timezone"):
        observed_rows(csv_path)
    csv_path.write_text(header + "library,2026-09-01T12:00:00-05:00,100,2,19,0,0\n")
    with pytest.raises(ValueError, match="five days"):
        observed_rows(csv_path)
