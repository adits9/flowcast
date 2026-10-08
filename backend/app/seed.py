from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .config import settings
from .database import CampusEvent, Location, Session

# Example campus inventory. Replace this list for your campus, then use a fresh database.
LOCATIONS = [
    (
        "commons",
        "The Commons",
        "dining",
        "Student Union · Ground floor",
        "Fresh bowls, comfort food, and a table for everyone.",
        180,
        4,
        7,
        22,
        ["Meal swipes", "Vegetarian", "Grab & go"],
        48,
        56,
    ),
    (
        "roastery",
        "Campus Roastery",
        "dining",
        "Arts Building · Ground floor",
        "Your favorite coffee, a little sunlight, and room to recharge.",
        65,
        6,
        7,
        20,
        ["Coffee", "Pastries", "Outdoor seating"],
        24,
        42,
    ),
    (
        "garden",
        "Garden Kitchen",
        "dining",
        "West Hall · Level 1",
        "Seasonal plates and plant-forward lunches by the courtyard.",
        110,
        8,
        10,
        21,
        ["Plant-based", "Meal swipes", "Gluten-free options"],
        24,
        72,
    ),
    (
        "rec",
        "Campus Recreation",
        "fitness",
        "Recreation Center · East entrance",
        "Make room for movement with weights, cardio, and open courts.",
        140,
        7,
        6,
        23,
        ["Free weights", "Cardio", "Showers"],
        78,
        44,
    ),
    (
        "studio",
        "Movement Studio",
        "fitness",
        "Wellness Center · Level 2",
        "A calmer space for stretching, yoga, and a fresh start.",
        45,
        9,
        7,
        22,
        ["Yoga", "Stretching", "Mats provided"],
        79,
        71,
    ),
    (
        "library",
        "Wells Library",
        "study",
        "Wells Library · Levels 1–3",
        "Find your focus in a quiet corner, with a view of the quad.",
        240,
        3,
        0,
        24,
        ["Quiet zone", "Outlets", "Wi-Fi"],
        44,
        28,
    ),
    (
        "hub",
        "The Study Hub",
        "study",
        "Engineering Building · Level 2",
        "Bring your group and your big ideas. Whiteboards included.",
        85,
        5,
        7,
        23,
        ["Group study", "Whiteboards", "Wi-Fi"],
        64,
        25,
    ),
    (
        "reading",
        "North Reading Room",
        "study",
        "North Hall · Level 1",
        "A tucked-away reading room for your deepest work.",
        50,
        10,
        8,
        22,
        ["Silent zone", "Natural light", "Outlets"],
        27,
        19,
    ),
]


def seed():
    with Session.begin() as session:
        if session.scalar(select(Location.id).limit(1)):
            return
        for item in LOCATIONS:
            keys = [
                "id",
                "name",
                "category",
                "building",
                "description",
                "capacity",
                "walk_minutes",
                "opens",
                "closes",
                "tags",
                "x",
                "y",
            ]
            session.add(Location(**dict(zip(keys, item))))
        if settings.demo_mode:
            now = datetime.now(ZoneInfo(settings.campus_timezone))
            start = now.replace(hour=17, minute=0, second=0, microsecond=0)
            start = start.astimezone(timezone.utc)
            session.add_all(
                [
                    CampusEvent(
                        title="Fall club fair",
                        venue="Student Union",
                        starts_at=start,
                        ends_at=start + timedelta(hours=2),
                        impact=0.13,
                    ),
                    CampusEvent(
                        title="Evening yoga",
                        venue="Wellness Center",
                        starts_at=start + timedelta(hours=1),
                        ends_at=start + timedelta(hours=2),
                        impact=0.08,
                    ),
                ]
            )
