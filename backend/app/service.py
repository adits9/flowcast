import math
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, or_, select

from .config import settings
from .database import CampusEvent, Checkin, Location, Observation, Session, Weather, utcnow
from .forecast import Forecaster, demand, wait_for

write_lock = threading.RLock()
forecaster: Forecaster | None = None
forecast_cache = {}


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def local_now():
    return datetime.now(ZoneInfo(settings.campus_timezone))


def expire_checkins(session):
    session.execute(
        delete(Checkin).where(Checkin.created_at < utcnow() - timedelta(hours=settings.checkin_expiry_hours))
    )


def context(session):
    now = local_now()
    record = session.get(Weather, 1)
    weather = {
        "temperature_c": record.temperature_c if record else 19,
        "rain_mm": record.rain_mm if record else 0,
        "source": record.source if record else "unavailable",
    }
    weather["description"] = "Rainy" if weather["rain_mm"] else "Partly cloudy"
    weather["stale"] = bool(record and (utcnow() - aware(record.updated_at)).total_seconds() > 3600)
    events = session.scalars(
        select(CampusEvent).where(CampusEvent.ends_at > now.astimezone(timezone.utc)).order_by(CampusEvent.starts_at)
    ).all()
    impact = sum(event.impact for event in events if aware(event.starts_at) <= now <= aware(event.ends_at))
    return now, weather, events, min(impact, 0.4)


def counts(session):
    active = dict(
        session.execute(
            select(Checkin.location_id, func.count())
            .join(Location, Checkin.location_id == Location.id)
            .where(Checkin.created_at >= utcnow() - timedelta(hours=settings.checkin_expiry_hours))
            .where(or_(Location.data_source != "sensor", Checkin.created_at > Location.updated_at))
            .group_by(Checkin.location_id)
        ).all()
    )
    return {
        location.id: min(location.capacity, location.base_occupancy + active.get(location.id, 0))
        for location in session.scalars(select(Location))
    }


def snapshot():
    with Session() as session:
        now, weather, events, impact = context(session)
        current = counts(session)
        locations = []
        for location in session.scalars(select(Location).order_by(Location.id)):
            hour = now.hour + now.minute / 60
            is_open = location.opens <= hour < location.closes
            occupied = current[location.id] if is_open else 0
            ratio = occupied / location.capacity
            stale = (
                location.data_source == "awaiting"
                or (not settings.demo_mode and location.data_source == "demo")
                or (location.data_source == "sensor" and (utcnow() - aware(location.updated_at)).total_seconds() > 300)
            )
            percent = round(ratio * 100)
            status = (
                "closed"
                if not is_open
                else "unknown"
                if stale
                else "busy"
                if percent >= 75
                else "moderate"
                if percent >= 35
                else "quiet"
            )
            forecast_unavailable = stale or (
                not settings.demo_mode and (weather["source"] in ["unavailable", "demo"] or weather["stale"])
            )
            cache_key = (
                location.id,
                occupied,
                now.strftime("%Y-%m-%dT%H:%M"),
                weather["temperature_c"],
                weather["rain_mm"],
                impact,
                forecast_unavailable,
                settings.demo_mode,
                forecaster.metadata.get("trained_at"),
            )
            points = forecast_cache.get(cache_key)
            if points is None:
                points = forecaster.predict(location, now, ratio, weather, impact) if not forecast_unavailable else []
                if len(forecast_cache) > 256:
                    forecast_cache.clear()
                forecast_cache[cache_key] = points
            locations.append(
                {
                    "id": location.id,
                    "name": location.name,
                    "category": location.category,
                    "building": location.building,
                    "description": location.description,
                    "capacity": location.capacity,
                    "occupancy": occupied,
                    "percent": percent,
                    "available": location.capacity - occupied,
                    "walk_minutes": location.walk_minutes,
                    "opens": location.opens,
                    "closes": location.closes,
                    "is_open": is_open,
                    "status": status,
                    "tags": location.tags,
                    "x": location.x,
                    "y": location.y,
                    "wait_minutes": round(wait_for(location.category, ratio)) if is_open and not stale else None,
                    "updated_at": aware(location.updated_at).isoformat(),
                    "source": location.data_source,
                    "forecast": points,
                    "stale": stale,
                }
            )
        return {
            "campus": settings.campus_name,
            "timezone": settings.campus_timezone,
            "demo_mode": settings.demo_mode,
            "updated_at": now.isoformat(),
            "weather": weather,
            "checkin_expiry_hours": settings.checkin_expiry_hours,
            "events": [
                {
                    "id": event.id,
                    "title": event.title,
                    "venue": event.venue,
                    "starts_at": aware(event.starts_at).isoformat(),
                    "ends_at": aware(event.ends_at).isoformat(),
                }
                for event in events
            ],
            "locations": locations,
            "model": forecaster.metadata,
        }


def tick():
    with write_lock, Session.begin() as session:
        expire_checkins(session)
        now, _, _, impact = context(session)
        if settings.demo_mode:
            if not session.get(Weather, 1):
                session.add(Weather(id=1, temperature_c=19, rain_mm=0, source="demo"))
            for location in session.scalars(select(Location).order_by(Location.id).with_for_update()):
                wave = 0.035 * math.sin(now.timestamp() / 100 + sum(map(ord, location.id)))
                ratio = demand(location.id, now, event_impact=impact) + wave
                location.base_occupancy = (
                    max(0, min(location.capacity, round(ratio * location.capacity)))
                    if location.opens <= now.hour + now.minute / 60 < location.closes
                    else 0
                )
                location.updated_at = utcnow()
                location.data_source = "demo"
                session.add(Observation(location_id=location.id, occupancy=location.base_occupancy, source="demo"))
        # Keep a month of raw samples; longer-term storage is a deployment choice.
        session.execute(delete(Observation).where(Observation.observed_at < utcnow() - timedelta(days=30)))


def checkin(visitor_id, location_id):
    with write_lock, Session.begin() as session:
        expire_checkins(session)
        # Ordered row locks serialize capacity changes across PostgreSQL workers.
        locked = list(session.scalars(select(Location).order_by(Location.id).with_for_update()))
        location = next((item for item in locked if item.id == location_id), None)
        if not location:
            return 404, "Location not found"
        now = local_now()
        if not location.opens <= now.hour + now.minute / 60 < location.closes:
            return 409, "This location is currently closed"
        existing = session.get(Checkin, visitor_id)
        if existing and existing.location_id == location_id:
            return 200, "Already checked in"
        if counts(session)[location_id] >= location.capacity:
            return 409, "This location is at capacity. Try another space."
        if existing:
            reconcile_departure(session, existing)
            session.delete(existing)
            session.flush()
        session.add(Checkin(visitor_id=visitor_id, location_id=location_id))
        if location.data_source == "awaiting":
            location.data_source = "checkins"
        session.add(Observation(location_id=location_id, occupancy=counts(session)[location_id], source="checkin"))
    return 200, "Checked in"


def checkout(visitor_id):
    with write_lock, Session.begin() as session:
        list(session.scalars(select(Location).order_by(Location.id).with_for_update()))
        existing = session.get(Checkin, visitor_id)
        if existing:
            reconcile_departure(session, existing)
            session.delete(existing)


def reconcile_departure(session, existing):
    location = session.get(Location, existing.location_id)
    # A sensor reading already includes check-ins older than that measurement.
    if location.data_source == "sensor" and aware(existing.created_at) <= aware(location.updated_at):
        location.base_occupancy = max(0, location.base_occupancy - 1)


def ingest(location_id, occupancy):
    with write_lock, Session.begin() as session:
        location = session.scalar(select(Location).where(Location.id == location_id).with_for_update())
        if not location:
            return 404, "Location not found"
        if occupancy > location.capacity:
            return 422, f"Occupancy cannot exceed capacity ({location.capacity})"
        location.base_occupancy = occupancy
        location.data_source = "sensor"
        location.updated_at = utcnow()
        session.add(Observation(location_id=location_id, occupancy=occupancy, source="sensor"))
    return 200, "Occupancy recorded"
