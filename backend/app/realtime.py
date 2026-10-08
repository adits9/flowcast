import asyncio
import json
import logging

from fastapi import WebSocket
from redis.asyncio import Redis
from redis.exceptions import RedisError

from .config import settings

logger = logging.getLogger(__name__)
CHANNEL = "flowcast:updates"


class Realtime:
    def __init__(self):
        self.redis: Redis | None = None
        self.subscriber: Redis | None = None
        self.channel: str = CHANNEL
        self.clients: set[WebSocket] = set()
        self.listener_task: asyncio.Task | None = None
        self.last_event: dict | None = None
        self.ready: asyncio.Event | None = None

    async def start(self):
        if not settings.redis_url:
            return
        self.redis = Redis.from_url(
            settings.redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=3
        )
        try:
            await self.redis.ping()
        except RedisError as exc:
            await self.redis.aclose()
            self.redis = None
            raise RuntimeError("Configured Redis is unreachable; check REDIS_URL") from exc
        # Pub/Sub is a long-lived stream: an idle stream must not hit the command read timeout.
        self.subscriber = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=None,
            socket_keepalive=True,
        )
        database = self.redis.connection_pool.connection_kwargs.get("db", 0)
        # Redis Pub/Sub ignores selected databases, so scope the channel explicitly.
        self.channel = f"{CHANNEL}:{database}"
        self.ready = asyncio.Event()
        self.listener_task = asyncio.create_task(self.listen())
        await asyncio.wait_for(self.ready.wait(), timeout=5)

    async def stop(self):
        if self.listener_task:
            self.listener_task.cancel()
            await asyncio.gather(self.listener_task, return_exceptions=True)
        if self.redis:
            await self.redis.aclose()
        if self.subscriber:
            await self.subscriber.aclose()
        self.redis = None
        self.subscriber = None
        self.listener_task = None

    async def listen(self):
        while True:
            try:
                async with self.subscriber.pubsub() as pubsub:
                    await pubsub.subscribe(self.channel)
                    async for message in pubsub.listen():
                        if message["type"] == "subscribe":
                            self.ready.set()
                        if message["type"] == "message":
                            await self.broadcast(json.loads(message["data"]))
            except RedisError:
                logger.warning("Redis subscription interrupted; retrying in two seconds")
                await asyncio.sleep(2)

    async def broadcast(self, payload):
        self.last_event = payload

        async def send(client):
            try:
                await asyncio.wait_for(client.send_json(payload), timeout=3)
            except Exception:
                self.clients.discard(client)

        await asyncio.gather(*(send(client) for client in list(self.clients)))

    async def publish(self, payload):
        if self.redis:
            try:
                await self.redis.publish(self.channel, json.dumps(payload))
                return
            except RedisError:
                logger.warning("Redis publish failed; delivering locally")
        await self.broadcast(payload)

    async def cache_counts(self, counts):
        if self.redis:
            try:
                async with self.redis.pipeline(transaction=True) as pipe:
                    for location_id, count in counts.items():
                        pipe.set(
                            f"flowcast:occupancy:{location_id}", count, ex=max(90, settings.simulation_interval * 3)
                        )
                    await pipe.execute()
            except RedisError:
                logger.warning("Occupancy cache unavailable")

    async def get_forecast(self, key):
        if self.redis:
            try:
                value = await self.redis.get(f"flowcast:forecast:{key}")
                return json.loads(value) if value else None
            except RedisError:
                pass
        return None

    async def set_forecast(self, key, value):
        if self.redis:
            try:
                await self.redis.set(f"flowcast:forecast:{key}", json.dumps(value), ex=60)
            except RedisError:
                pass


realtime = Realtime()
