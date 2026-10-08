"""Time-split training and inference. Demo training data is explicitly synthetic."""

import csv
import math
from bisect import bisect_left
from datetime import datetime, timedelta
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error

from .config import settings
from .seed import LOCATIONS

LOCATION_IDS = [item[0] for item in LOCATIONS]
FEATURES = [
    "location",
    "hour_sin",
    "hour_cos",
    "weekday",
    "temperature_c",
    "rain_mm",
    "event_impact",
    "current_ratio",
    "horizon_minutes",
]


def features(location_id, future, current_ratio, temperature, rain, event_impact, horizon):
    hour = future.hour + future.minute / 60
    return [
        LOCATION_IDS.index(location_id),
        math.sin(hour / 24 * math.tau),
        math.cos(hour / 24 * math.tau),
        future.weekday(),
        temperature,
        rain,
        event_impact,
        current_ratio,
        horizon,
    ]


def demand(location_id: str, when: datetime, temperature=19.0, rain=0.0, event_impact=0.0):
    item = LOCATIONS[LOCATION_IDS.index(location_id)]
    category, opens, closes = item[2], item[7], item[8]
    hour = when.hour + when.minute / 60
    if not opens <= hour < closes:
        return 0.0

    def peak(center, width):
        return math.exp(-0.5 * ((hour - center) / width) ** 2)

    if category == "dining":
        ratio = 0.14 + 0.67 * peak(12.3, 1.0) + 0.58 * peak(18.1, 1.2)
    elif category == "fitness":
        ratio = 0.17 + 0.38 * peak(8.0, 1.5) + 0.68 * peak(17.5, 1.9)
    else:
        ratio = 0.16 + 0.42 * peak(14.2, 2.8) + 0.51 * peak(20.0, 2.0)
    offsets = {
        "commons": 0.12,
        "roastery": 0.02,
        "garden": -0.10,
        "rec": 0.07,
        "studio": -0.13,
        "library": 0.06,
        "hub": -0.09,
        "reading": -0.18,
    }
    ratio += offsets[location_id] + min(rain, 10) * 0.008 + event_impact
    if when.weekday() >= 5:
        ratio *= 0.72
    return float(np.clip(ratio, 0.04, 0.99))


def wait_for(category, ratio):
    multiplier = {"dining": 42, "fitness": 30, "study": 18}[category]
    return max(0.0, ratio - 0.28) ** 2 * multiplier


def synthetic_rows():
    rng = np.random.default_rng(42)
    start = datetime(2026, 3, 1)
    rows = []
    for day in range(35):
        temperature = 12 + 10 * math.sin(day / 9)
        rain = float(rng.choice([0, 0, 0, 1, 4, 8]))
        for item in LOCATIONS:
            for hour in range(7, 23):
                observed = start + timedelta(days=day, hours=hour)
                event = 0.12 if day % 5 == 0 and 16 <= hour <= 19 else 0.0
                noise = float(rng.normal(0, 0.04))
                current = np.clip(demand(item[0], observed, temperature, rain, event) + noise, 0, 1)
                for horizon in [15, 30, 60, 90, 120]:
                    future = observed + timedelta(minutes=horizon)
                    target = float(
                        np.clip(
                            demand(item[0], future, temperature, rain, event) + noise * 0.65 + rng.normal(0, 0.02), 0, 1
                        )
                    )
                    if not item[7] <= future.hour + future.minute / 60 < item[8]:
                        target = 0.0
                    wait = max(0, wait_for(item[2], target) + rng.normal(0, 0.6))
                    rows.append(
                        (observed, features(item[0], future, current, temperature, rain, event, horizon), target, wait)
                    )
    return rows


def observed_rows(csv_path: Path):
    groups = {location_id: [] for location_id in LOCATION_IDS}
    capacities = {item[0]: item[5] for item in LOCATIONS}
    with csv_path.open(newline="") as source:
        for row in csv.DictReader(source):
            location_id = row["location_id"]
            if location_id not in groups:
                raise ValueError(f"Unknown location_id: {location_id}")
            timestamp = datetime.fromisoformat(row["observed_at"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                raise ValueError("observed_at must include a timezone offset")
            from zoneinfo import ZoneInfo

            timestamp = timestamp.astimezone(ZoneInfo(settings.campus_timezone))
            occupancy = int(row["occupancy"])
            wait = float(row["wait_minutes"])
            if not 0 <= occupancy <= capacities[location_id] or wait < 0:
                raise ValueError("Occupancy or wait_minutes is outside its valid range")
            groups[location_id].append(
                (
                    timestamp,
                    occupancy / capacities[location_id],
                    wait,
                    float(row["temperature_c"]),
                    float(row["rain_mm"]),
                    float(row["event_impact"]),
                )
            )
    rows = []
    for location_id, values in groups.items():
        values.sort(key=lambda item: item[0])
        timestamps = [item[0] for item in values]
        for current in values:
            for horizon in [15, 30, 60, 90, 120]:
                target_time = current[0] + timedelta(minutes=horizon)
                index = bisect_left(timestamps, target_time)
                if index < len(values) and abs((values[index][0] - target_time).total_seconds()) <= 420:
                    target = values[index]
                    rows.append(
                        (
                            current[0],
                            features(location_id, target_time, current[1], current[3], current[4], current[5], horizon),
                            target[1],
                            target[2],
                        )
                    )
    if len(rows) < 150 or len({row[0].date() for row in rows}) < 5:
        raise ValueError("Provide at least five days and 150 paired observations, sampled every 15 minutes")
    return rows


def train(destination: Path, csv_path: Path | None = None):
    rows = sorted(observed_rows(csv_path) if csv_path else synthetic_rows(), key=lambda row: row[0])
    dates = sorted({row[0].date() for row in rows})
    boundary = dates[int(len(dates) * 0.8)]
    # Purge overlapping targets at the time boundary to prevent future leakage.
    training = [row for row in rows if (row[0] + timedelta(minutes=row[1][-1])).date() < boundary]
    validation = [row for row in rows if row[0].date() >= boundary]
    x_train = np.array([row[1] for row in training])
    x_valid = np.array([row[1] for row in validation])
    occupancy = HistGradientBoostingRegressor(max_iter=90, max_leaf_nodes=20, l2_regularization=1.0, random_state=42)
    wait = HistGradientBoostingRegressor(max_iter=90, max_leaf_nodes=20, l2_regularization=1.0, random_state=42)
    occupancy.fit(x_train, [row[2] for row in training])
    wait.fit(x_train, [row[3] for row in training])
    predicted_ratio, predicted_wait = occupancy.predict(x_valid), wait.predict(x_valid)
    true_ratio, true_wait = np.array([row[2] for row in validation]), np.array([row[3] for row in validation])
    metadata = {
        "source": "observed" if csv_path else "synthetic",
        "algorithm": "Histogram gradient boosting",
        "training_rows": len(training),
        "validation_rows": len(validation),
        "occupancy_mae_pp": round(mean_absolute_error(true_ratio, predicted_ratio) * 100, 2),
        "wait_mae_minutes": round(mean_absolute_error(true_wait, predicted_wait), 2),
        "ratio_error_band": float(np.quantile(np.abs(true_ratio - predicted_ratio), 0.8)),
        "wait_error_band": float(np.quantile(np.abs(true_wait - predicted_wait), 0.8)),
        "trained_at": datetime.now().astimezone().isoformat(),
        "features": FEATURES,
        "version": 1,
        "trained_location_ids": sorted({LOCATION_IDS[int(row[1][0])] for row in training}),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    artifact = {"occupancy": occupancy, "wait": wait, "metadata": metadata}
    temporary = destination.with_suffix(".tmp")
    joblib.dump(artifact, temporary)
    temporary.replace(destination)
    return artifact


class Forecaster:
    def __init__(self):
        # Artifacts must be trusted local files; joblib is not a safe upload format.
        if settings.model_path.exists():
            artifact = joblib.load(settings.model_path)
        elif settings.demo_mode:
            artifact = train(settings.model_path)
        else:
            artifact = None
        self.artifact = artifact
        self.metadata = artifact["metadata"] if artifact else {"source": "unavailable", "features": FEATURES}

    def predict(self, location, now, current_ratio, weather, event_impact):
        if not self.artifact or (not settings.demo_mode and self.metadata["source"] != "observed"):
            return []
        if location.id not in self.metadata["trained_location_ids"]:
            return []
        horizons = list(range(15, 121, 15))
        inputs = [
            features(
                location.id,
                now + timedelta(minutes=h),
                current_ratio,
                weather["temperature_c"],
                weather["rain_mm"],
                event_impact,
                h,
            )
            for h in horizons
        ]
        ratios = self.artifact["occupancy"].predict(inputs)
        waits = self.artifact["wait"].predict(inputs)
        points = []
        for horizon, ratio, wait in zip(horizons, ratios, waits):
            future = now + timedelta(minutes=horizon)
            is_open = location.opens <= future.hour + future.minute / 60 < location.closes
            ratio = float(np.clip(ratio, 0, 1)) if is_open else 0.0
            wait = max(0, round(float(wait))) if is_open else 0
            band = self.metadata["ratio_error_band"]
            points.append(
                {
                    "at": future.isoformat(),
                    "minutes_ahead": horizon,
                    "occupancy": round(ratio * location.capacity),
                    "percent": round(ratio * 100),
                    "wait_minutes": wait,
                    "lower_percent": max(0, round((ratio - band) * 100)) if is_open else 0,
                    "upper_percent": min(100, round((ratio + band) * 100)) if is_open else 0,
                    "is_open": is_open,
                }
            )
        return points
