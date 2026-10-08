import json
from uuid import uuid4

import pytest
from redis import Redis

from app.config import settings
from app.realtime import realtime


def test_real_redis_counters_forecast_cache_and_pubsub(client):
    if not settings.redis_url:
        pytest.skip("Set FLOWCAST_TEST_REDIS_URL to test a real isolated Redis instance")
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    with client.websocket_connect("/ws") as socket:
        socket.receive_json()
        response = client.post("/api/checkins", headers={"X-Visitor-ID": str(uuid4())}, json={"location_id": "hub"})
        assert response.status_code == 200
        snapshot = socket.receive_json()
        hub = next(item for item in snapshot["data"]["locations"] if item["id"] == "hub")
        assert int(redis.get("flowcast:occupancy:hub")) == hub["occupancy"]
        assert redis.ttl("flowcast:occupancy:hub") > 0
        keys = list(redis.scan_iter("flowcast:forecast:*"))
        assert keys
        assert any(len(json.loads(redis.get(key))) == 8 for key in keys)
        # An event published outside the API reaches its WebSocket subscribers.
        redis.publish(realtime.channel, json.dumps({"type": "integration-probe"}))
        assert socket.receive_json() == {"type": "integration-probe"}
    redis.close()
