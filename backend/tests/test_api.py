from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from starlette.websockets import WebSocketDisconnect

from app import service
from app.config import settings
from app.database import Checkin, Location, Session, utcnow
from app.main import transitions


def visitor():
    return {"X-Visitor-ID": str(uuid4())}


def occupancy(client, location_id):
    return next(item for item in client.get("/api/overview").json()["locations"] if item["id"] == location_id)[
        "occupancy"
    ]


def test_overview_forecast_and_health(client):
    response = client.get("/api/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["demo_mode"] is True
    assert len(data["locations"]) == 8
    assert data["model"]["source"] == "synthetic"
    assert data["model"]["occupancy_mae_pp"] < 10
    assert data["model"]["wait_mae_minutes"] < 2
    for location in data["locations"]:
        assert 0 <= location["occupancy"] <= location["capacity"]
        assert len(location["forecast"]) == 8
        for point in location["forecast"]:
            assert 0 <= point["lower_percent"] <= point["percent"] <= point["upper_percent"] <= 100
            assert point["wait_minutes"] >= 0
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/locations/missing/forecast").status_code == 404
    assert len(client.get("/api/locations/library/forecast").json()["forecast"]) == 8


def test_checkin_idempotency_move_and_checkout(client):
    headers = visitor()
    before, other_before = occupancy(client, "library"), occupancy(client, "hub")
    for _ in range(2):
        assert client.post("/api/checkins", headers=headers, json={"location_id": "library"}).status_code == 200
    assert occupancy(client, "library") == before + 1
    assert client.get("/api/checkins/me", headers=headers).json()["location_id"] == "library"
    assert client.post("/api/checkins", headers=headers, json={"location_id": "hub"}).status_code == 200
    assert occupancy(client, "library") == before
    assert occupancy(client, "hub") == other_before + 1
    for _ in range(2):
        assert client.delete("/api/checkins/me", headers=headers).status_code == 200
    assert occupancy(client, "hub") == other_before
    assert client.get("/api/checkins/me", headers=headers).json()["location_id"] is None


def test_capacity_race_and_rejected_moves_preserve_checkin(client):
    with Session.begin() as session:
        location = session.get(Location, "library")
        location.base_occupancy = location.capacity - 1
    visitors = [visitor(), visitor()]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda headers: client.post(
                    "/api/checkins", headers=headers, json={"location_id": "library"}
                ).status_code,
                visitors,
            )
        )
    assert sorted(results) == [200, 409]
    assert occupancy(client, "library") == 240
    headers = visitor()
    client.post("/api/checkins", headers=headers, json={"location_id": "hub"})
    assert client.post("/api/checkins", headers=headers, json={"location_id": "library"}).status_code == 409
    assert client.get("/api/checkins/me", headers=headers).json()["location_id"] == "hub"


def test_expiry_validation_and_closed_spaces(client):
    headers = visitor()
    baseline = occupancy(client, "hub")
    client.post("/api/checkins", headers=headers, json={"location_id": "hub"})
    with Session.begin() as session:
        session.get(Checkin, headers["X-Visitor-ID"]).created_at = utcnow() - timedelta(hours=4)
        session.get(Location, "studio").closes = 10
    assert occupancy(client, "hub") == baseline
    assert client.get("/api/checkins/me", headers=headers).json()["location_id"] is None
    assert client.post("/api/checkins", headers=headers, json={"location_id": "studio"}).status_code == 409
    assert client.post("/api/checkins", headers=headers, json={"location_id": "missing"}).status_code == 404
    assert (
        client.post("/api/checkins", headers={"X-Visitor-ID": "bad"}, json={"location_id": "library"}).status_code
        == 422
    )
    assert client.post("/api/checkins", json={"location_id": "library"}).status_code == 422


def test_sensor_auth_capacity_weather_events_and_stale_data(client, monkeypatch):
    assert client.post("/api/ingest/library", json={"occupancy": 190}).status_code == 503
    monkeypatch.setattr(settings, "sensor_api_key", "test-secret")
    assert client.post("/api/ingest/library", json={"occupancy": 190}).status_code == 401
    headers = {"X-API-Key": "test-secret"}
    assert client.post("/api/ingest/library", headers=headers, json={"occupancy": -1}).status_code == 422
    assert client.post("/api/ingest/library", headers=headers, json={"occupancy": 241}).status_code == 422
    assert client.post("/api/ingest/missing", headers=headers, json={"occupancy": 10}).status_code == 404
    own = visitor()
    client.post("/api/checkins", headers=own, json={"location_id": "library"})
    assert client.post("/api/ingest/library", headers=headers, json={"occupancy": 190}).status_code == 200
    assert occupancy(client, "library") == 190  # Sensor totals already include active check-ins.
    assert client.post("/api/weather", headers=headers, json={"temperature_c": 17, "rain_mm": 3}).status_code == 200
    assert client.get("/api/overview").json()["weather"]["source"] == "observed"
    event = {
        "title": "Test event",
        "venue": "Union",
        "starts_at": "2026-10-08T12:00:00-05:00",
        "ends_at": "2026-10-08T14:00:00-05:00",
        "impact": 0.2,
    }
    assert client.post("/api/events", headers=headers, json=event).status_code == 200
    saved_event = next(item for item in client.get("/api/overview").json()["events"] if item["title"] == "Test event")
    assert saved_event["starts_at"] == "2026-10-08T17:00:00+00:00"
    assert client.post("/api/events", headers=headers, json={**event, "ends_at": event["starts_at"]}).status_code == 422
    with Session.begin() as session:
        session.get(Location, "library").updated_at = utcnow() - timedelta(minutes=10)
    location = next(item for item in client.get("/api/overview").json()["locations"] if item["id"] == "library")
    assert location["status"] == "unknown"
    assert location["forecast"] == []


def test_websocket_broadcast_and_origin_rejection(client):
    with client.websocket_connect("/ws", headers={"origin": "http://localhost:8000"}) as socket:
        initial = socket.receive_json()
        assert initial["type"] == "snapshot"
        client.post("/api/checkins", headers=visitor(), json={"location_id": "hub"})
        update = socket.receive_json()
        assert update["type"] == "snapshot"
        before = next(item for item in initial["data"]["locations"] if item["id"] == "hub")["occupancy"]
        after = next(item for item in update["data"]["locations"] if item["id"] == "hub")["occupancy"]
        assert after == before + 1
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/ws", headers={"origin": "https://untrusted.example"}),
    ):
        pass


def test_alert_thresholds_and_live_mode_do_not_use_synthetic_model(client, monkeypatch):
    previous = {"locations": [{"id": "hub", "status": "moderate"}]}
    current = {"updated_at": "2026-10-08T12:00:00-05:00", "locations": [{"id": "hub", "name": "Hub", "status": "busy"}]}
    assert transitions(previous, current)[0]["kind"] == "busy"
    assert transitions(current, current) == []
    monkeypatch.setattr(settings, "demo_mode", False)
    assert all(not item["forecast"] for item in service.snapshot()["locations"])


def test_sensor_baselines_do_not_double_count_or_drop_on_expiry(client, monkeypatch):
    monkeypatch.setattr(settings, "sensor_api_key", "test-secret")
    sensor = {"X-API-Key": "test-secret"}
    first, second = visitor(), visitor()
    client.post("/api/checkins", headers=first, json={"location_id": "hub"})
    client.post("/api/ingest/hub", headers=sensor, json={"occupancy": 20})
    assert occupancy(client, "hub") == 20
    client.post("/api/checkins", headers=second, json={"location_id": "hub"})
    assert occupancy(client, "hub") == 21
    client.delete("/api/checkins/me", headers=first)
    assert occupancy(client, "hub") == 20
    client.post("/api/ingest/hub", headers=sensor, json={"occupancy": 0})
    assert occupancy(client, "hub") == 0
    with Session.begin() as session:
        session.get(Checkin, second["X-Visitor-ID"]).created_at = utcnow() - timedelta(hours=4)
    assert occupancy(client, "hub") == 0
