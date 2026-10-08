import asyncio
import hmac
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from . import service
from .config import ROOT, settings
from .database import Base, CampusEvent, Checkin, Session, Weather, engine, utcnow
from .forecast import Forecaster
from .realtime import realtime
from .seed import seed

logger = logging.getLogger(__name__)


def transitions(previous, current):
    prior = {location["id"]: location for location in previous.get("locations", [])} if previous else {}
    alerts = []
    for location in current["locations"]:
        old = prior.get(location["id"])
        if old and location["status"] != old["status"] and location["status"] in ["busy", "quiet"]:
            alerts.append(
                {
                    "location_id": location["id"],
                    "location_name": location["name"],
                    "kind": location["status"],
                    "at": current["updated_at"],
                    "message": f"{location['name']} is {'getting crowded' if location['status'] == 'busy' else 'quiet now'}.",
                }
            )
    return alerts


async def publish_snapshot():
    async with app.state.publish_lock:
        data = await asyncio.to_thread(service.snapshot)
        previous = realtime.last_event.get("data") if realtime.last_event else None
        payload = {"type": "snapshot", "data": data, "alerts": transitions(previous, data)}
        realtime.last_event = payload
        await realtime.cache_counts({item["id"]: item["occupancy"] for item in data["locations"]})
        # Forecasts are cached separately for API consumers; the database remains authoritative.
        await asyncio.gather(
            *(realtime.set_forecast(forecast_key(data, item), item["forecast"]) for item in data["locations"])
        )
        await realtime.publish(payload)
        return data


def forecast_key(data, location):
    # Context changes within the same minute must invalidate the shared cache too.
    import hashlib
    import json

    inputs = [
        location["id"],
        location["occupancy"],
        location["status"],
        data["demo_mode"],
        data["model"].get("trained_at"),
        data["updated_at"][:16],
        data["weather"],
        data["events"],
    ]
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


async def update_loop():
    while True:
        await asyncio.sleep(settings.simulation_interval)
        try:
            await asyncio.to_thread(service.tick)
            await publish_snapshot()
        except Exception:
            logger.exception("Occupancy update failed; retrying on next interval")


@asynccontextmanager
async def lifespan(app):
    app.state.publish_lock = asyncio.Lock()
    Base.metadata.create_all(engine)
    seed()
    service.forecaster = await asyncio.to_thread(Forecaster)
    await realtime.start()
    await asyncio.to_thread(service.tick)
    initial = await asyncio.to_thread(service.snapshot)
    realtime.last_event = {"type": "snapshot", "data": initial, "alerts": []}
    task = asyncio.create_task(update_loop())
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await realtime.stop()
    realtime.clients.clear()


app = FastAPI(title="FlowCast API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Visitor-ID", "X-API-Key"],
)


class CheckinRequest(BaseModel):
    location_id: str = Field(min_length=1, max_length=64)


class OccupancyRequest(BaseModel):
    occupancy: int = Field(ge=0, le=10000)


class WeatherRequest(BaseModel):
    temperature_c: float = Field(ge=-50, le=60)
    rain_mm: float = Field(ge=0, le=100)


class EventRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    venue: str = Field(min_length=1, max_length=120)
    starts_at: datetime
    ends_at: datetime
    impact: float = Field(ge=0, le=0.4)

    @model_validator(mode="after")
    def valid_times(self):
        if not self.starts_at.tzinfo or not self.ends_at.tzinfo:
            raise ValueError("Event times must include timezone offsets")
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


def visitor(x_visitor_id: UUID = Header()):
    return str(x_visitor_id)


def sensor_auth(x_api_key: str = Header(default="")):
    if not settings.sensor_api_key:
        raise HTTPException(503, "Sensor ingestion is disabled until SENSOR_API_KEY is configured")
    if not hmac.compare_digest(x_api_key, settings.sensor_api_key):
        raise HTTPException(401, "Invalid API key")


@app.get("/api/health")
async def health():
    with Session() as session:
        session.execute(select(1))
    redis_ok = False
    if realtime.redis:
        try:
            redis_ok = bool(await realtime.redis.ping())
        except Exception:
            pass
    return {
        "status": "ok" if not settings.redis_url or redis_ok else "degraded",
        "database": "postgresql" if settings.database_url.startswith("postgresql") else "sqlite",
        "realtime": "redis" if redis_ok else "local",
        "demo_mode": settings.demo_mode,
        "model_source": service.forecaster.metadata["source"],
    }


@app.get("/api/overview")
def overview():
    return service.snapshot()


@app.get("/api/locations/{location_id}/forecast")
async def forecast(location_id: str):
    data = await asyncio.to_thread(service.snapshot)
    location = next((item for item in data["locations"] if item["id"] == location_id), None)
    if not location:
        raise HTTPException(404, "Location not found")
    key = forecast_key(data, location)
    points = await realtime.get_forecast(key)
    if points is None:
        points = location["forecast"]
        await realtime.set_forecast(key, points)
    return {"location_id": location_id, "forecast": points, "model_source": data["model"]["source"]}


@app.get("/api/checkins/me")
def my_checkin(visitor_id: str = Depends(visitor)):
    with Session() as session:
        record = session.get(Checkin, visitor_id)
        if not record or service.aware(record.created_at) < utcnow() - timedelta(hours=settings.checkin_expiry_hours):
            return {"location_id": None, "expires_at": None}
        return {
            "location_id": record.location_id,
            "expires_at": (
                service.aware(record.created_at) + timedelta(hours=settings.checkin_expiry_hours)
            ).isoformat(),
        }


@app.post("/api/checkins")
async def checkin(body: CheckinRequest, visitor_id: str = Depends(visitor)):
    code, message = await asyncio.to_thread(service.checkin, visitor_id, body.location_id)
    if code != 200:
        raise HTTPException(code, message)
    await publish_snapshot()
    return my_checkin(visitor_id)


@app.delete("/api/checkins/me")
async def checkout(visitor_id: str = Depends(visitor)):
    await asyncio.to_thread(service.checkout, visitor_id)
    await publish_snapshot()
    return {"location_id": None, "expires_at": None}


@app.post("/api/ingest/{location_id}", dependencies=[Depends(sensor_auth)])
async def ingest(location_id: str, body: OccupancyRequest):
    code, message = await asyncio.to_thread(service.ingest, location_id, body.occupancy)
    if code != 200:
        raise HTTPException(code, message)
    await publish_snapshot()
    return {"message": message}


@app.post("/api/weather", dependencies=[Depends(sensor_auth)])
async def weather(body: WeatherRequest):
    def save():
        with Session.begin() as session:
            session.merge(Weather(id=1, **body.model_dump(), source="observed", updated_at=utcnow()))

    await asyncio.to_thread(save)
    await publish_snapshot()
    return {"message": "Weather updated"}


@app.post("/api/events", dependencies=[Depends(sensor_auth)])
async def event(body: EventRequest):
    def save():
        with Session.begin() as session:
            fields = body.model_dump()
            fields["starts_at"] = fields["starts_at"].astimezone(timezone.utc)
            fields["ends_at"] = fields["ends_at"].astimezone(timezone.utc)
            record = CampusEvent(**fields)
            session.add(record)
            session.flush()
            return record.id

    event_id = await asyncio.to_thread(save)
    await publish_snapshot()
    return {"id": event_id}


@app.websocket("/ws")
async def websocket(websocket: WebSocket):
    origin = websocket.headers.get("origin")
    if origin and origin not in settings.allowed_origins.split(","):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    data = await asyncio.to_thread(service.snapshot)
    await websocket.send_json({"type": "snapshot", "data": data, "alerts": []})
    realtime.clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        realtime.clients.discard(websocket)


DIST = ROOT / "frontend/dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{route:path}", include_in_schema=False)
    def frontend(route: str):
        if route.startswith(("api/", "ws")):
            raise HTTPException(404, "Not found")
        target = (DIST / route).resolve()
        if target.is_relative_to(DIST.resolve()) and target.is_file():
            return FileResponse(target)
        return FileResponse(DIST / "index.html")
