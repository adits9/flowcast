# FlowCast

A campus companion for finding a good time to eat, work out, and study. Built with **React + TypeScript, FastAPI, scikit-learn, PostgreSQL, and Redis**.

## Start it

```bash
./start.sh
```

Open **http://127.0.0.1:8000**. The script installs dependencies, builds the interface, and starts the API. The first launch trains the demo models automatically. Requires Python 3.12+ and Node.js 22.12+; Python 3.14 and Node 24 are also tested. No accounts, API keys, or external services are needed for the demo. Stop with Ctrl+C.

The local demo uses persistent SQLite and an in-process event bus. To run **PostgreSQL and Redis** too, install Docker Desktop and use:

```bash
docker compose up --build
```

The same URL serves the application. PostgreSQL and Redis stay on the internal Docker network, and the application binds to localhost. The Compose database credentials are development defaults. Run one application worker in demo mode so one simulator owns occupancy updates.

## What works

- Eight sample dining, fitness, and study spaces with opening hours, capacity, occupancy, and estimated waits.
- Automatic occupancy updates and crowd transitions over WebSockets. Redis provides occupancy counters, forecast caches with TTLs, and Pub/Sub when configured.
- Forecasts every 15 minutes for the next two hours, with an estimated error range, arrival suggestions, and a selectable planning horizon.
- Anonymous browser check-ins and check-outs, capacity enforcement, safe repeated requests, location switching, and automatic expiry after three hours.
- Persistent favorites and alert preferences, search, category filters, sorting, and an interactive illustrated campus map.
- Responsive desktop and mobile layouts, keyboard-accessible dialogs, and reduced-motion support. Fonts and illustrations are bundled locally.
- Protected APIs for occupancy measurements, weather, and campus events; interactive API documentation at **/docs**.

**Northwood University is fictional. Demo occupancy, weather, events, and model training observations are simulated.** Demo metrics describe performance on simulated observations, not accuracy at a real campus. Crowd alerts are delivered while the app is open; they are not background push notifications. The illustrated map is not a navigation map.

## How forecasting works

Two histogram gradient boosting regressors predict occupancy ratio and future wait minutes. Inputs include location, cyclical time of day, weekday, temperature, rainfall, active event impact, current check-in/occupancy ratio, and forecast horizon. Current wait estimates use a category-specific occupancy heuristic; future wait estimates use the trained regressor.

Training holds out the final 20% of dates and removes training targets that overlap that boundary. Metadata records training and validation sample counts, occupancy MAE in percentage points, and wait MAE in minutes. The shaded chart range uses the 80th percentile of absolute validation errors; it is an illustrative error band, not a calibrated confidence interval.

Models persist in `artifacts/forecast.joblib` and load on restart. The database is authoritative for occupancy. Redis caches can expire or reconnect without becoming the source of truth. Missing or stale sensor data is shown as unavailable, and its forecasts are suppressed. Sensors become stale after five minutes; weather after one hour.

## Connect a real campus

The one thing needed from you for real operation is **a campus inventory and an authorized source of occupancy observations** (sensors, campus APIs, or historical exports). Weather and campus event data can be supplied through the same protected ingestion API. No vendor accounts are needed to develop or explore the demo.

1. Replace the example inventory in `backend/app/seed.py` with the actual spaces, capacities, hours, and map coordinates. The current model treats these location IDs as its known inventory; train again after changing it.
2. Copy `.env.example` to `.env`, set `DEMO_MODE=false`, configure a **fresh PostgreSQL database** rather than reusing the demo database, and set `REDIS_URL`. Set `CAMPUS_NAME`, `CAMPUS_TIMEZONE`, and a long random `SENSOR_API_KEY`.
3. Post absolute occupancy totals to `POST /api/ingest/{location_id}` with `X-API-Key`. Totals should include people who already checked in; the API reconciles those check-ins to avoid double-counting. Later check-ins adjust that baseline until the next sensor observation.
4. Supply weather with `POST /api/weather` and events with `POST /api/events`; both require the same API key. The `/docs` page documents all fields.
5. Train on observed data with the command below, then restart the application. Live mode never serves forecasts from a synthetic model, and locations without observed training data have no forecasts.

Example occupancy ingestion:

```bash
curl -X POST http://127.0.0.1:8000/api/ingest/library \
  -H "X-API-Key: $SENSOR_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"occupancy": 142}'
```

Historical training CSV (15-minute samples, timezone-aware timestamps):

```csv
location_id,observed_at,occupancy,wait_minutes,temperature_c,rain_mm,event_impact
library,2026-09-01T12:00:00-05:00,142,3,19,0,0
library,2026-09-01T12:15:00-05:00,149,4,19,0,0
```

```bash
.venv/bin/python backend/train.py --csv /path/to/observations.csv
```

Provide at least five days and 150 paired observations; several weeks spanning weekdays, weekends, weather, and events will be more useful. Rows from the same location are paired at future horizons. Only train from trusted CSVs and load trusted local model artifacts. For Compose, copy the CSV into the running app container and execute `python backend/train.py --csv /app/observations.csv` there so the model is written to its mounted model volume.

For a public rollout, configure HTTPS and `ALLOWED_ORIGINS` for the deployed origin, private database credentials, and campus authentication or gateway controls for check-in abuse prevention. Browser UUIDs currently identify anonymous sessions; favorites and alert preferences are stored on that browser. Schema creation is automatic for a fresh installation; versioned database migrations will be needed as an existing deployment evolves.

## Development and checks

For hot reload, run the API and frontend in two terminals:

```bash
.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload
```

```bash
cd frontend
npm run dev
```

Open http://127.0.0.1:5173; Vite proxies API and WebSocket requests to FastAPI.

```bash
.venv/bin/pytest -q
.venv/bin/ruff check backend
cd frontend && npm run build
```

Tests isolate their database and model files. To test PostgreSQL and Redis, point the following variables at **dedicated test services** (the PostgreSQL tables will be recreated):

```bash
FLOWCAST_TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/flowcast_test \
FLOWCAST_TEST_REDIS_URL=redis://localhost:6379/15 \
.venv/bin/pytest -q
```

Optional browser smoke test, while the app is running:

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
python3 scripts/browser_smoke.py
```

Use `FLOWCAST_BROWSER=chrome` to test with an installed Google Chrome or `FLOWCAST_URL` to select another local URL. Screenshots are saved in `test-results/`. The test covers desktop/mobile layouts, search, category filters, persisted favorites, forecast views, check-in/out, alert subscription, dialogs, and map selection.

GitHub Actions runs the backend tests with SQLite and PostgreSQL/Redis, Python lint, and the TypeScript/production build. Integration and browser checks were also verified locally; Docker itself is not installed in the development environment, so the image build has not been executed here.

## Code map

| Path | Responsibility |
| --- | --- |
| `backend/app/main.py` | API routes, authentication for ingestion, lifecycle, WebSockets |
| `backend/app/service.py` | Occupancy transactions, expiry, simulation, snapshots |
| `backend/app/database.py` | PostgreSQL/SQLite schema |
| `backend/app/forecast.py` | Feature extraction, temporal training, inference |
| `backend/app/realtime.py` | Redis counters, TTL caches, Pub/Sub, local event delivery |
| `frontend/src/App.tsx` | Dashboard, favorites, map, planning, alerts, and check-ins |
| `frontend/src/visuals.tsx` | Local campus illustrations and forecast charts |

Implementation references: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/), [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/), [scikit-learn histogram gradient boosting](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html), and [Vite](https://vite.dev/guide/).
