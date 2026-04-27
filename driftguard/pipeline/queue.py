from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any

import structlog

from driftguard.config import DriftGuardSettings
from driftguard.models import QueueTracePayload

try:
    from redis.asyncio import Redis
except Exception:  # pragma: no cover - exercised only when redis is unavailable.
    Redis = None  # type: ignore[assignment]

logger = structlog.get_logger(__name__)


class BaseQueue(ABC):
    @abstractmethod
    async def publish(self, payload: QueueTracePayload) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get(self) -> QueueTracePayload:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError


class InMemoryQueue(BaseQueue):
    def __init__(self) -> None:
        self._queue: asyncio.Queue[QueueTracePayload] = asyncio.Queue()

    async def publish(self, payload: QueueTracePayload) -> None:
        await self._queue.put(payload)

    async def get(self) -> QueueTracePayload:
        return await self._queue.get()

    async def close(self) -> None:
        while not self._queue.empty():
            self._queue.get_nowait()
            self._queue.task_done()


class RedisStreamQueue(BaseQueue):
    def __init__(self, client: Any, stream_name: str = "driftguard:traces") -> None:
        self._client = client
        self._stream_name = stream_name
        self._last_id = "0-0"

    async def publish(self, payload: QueueTracePayload) -> None:
        await self._client.xadd(self._stream_name, {"payload": payload.model_dump_json()})

    async def get(self) -> QueueTracePayload:
        while True:
            response = await self._client.xread({self._stream_name: self._last_id}, count=1, block=1000)
            if not response:
                await asyncio.sleep(0.05)
                continue
            _, messages = response[0]
            message_id, fields = messages[0]
            self._last_id = message_id
            raw_payload = fields.get(b"payload") if isinstance(next(iter(fields.keys())), bytes) else fields.get("payload")
            if isinstance(raw_payload, bytes):
                raw_payload = raw_payload.decode("utf-8")
            return QueueTracePayload.model_validate_json(raw_payload)

    async def close(self) -> None:
        await self._client.close()


async def create_queue(settings: DriftGuardSettings) -> BaseQueue:
    if Redis is None:
        logger.warning("queue_fallback", reason="redis_unavailable")
        return InMemoryQueue()

    try:
        client = Redis.from_url(settings.redis_url, decode_responses=False)
        await client.ping()
        logger.info("queue_backend", backend="redis", redis_url=settings.redis_url)
        return RedisStreamQueue(client=client)
    except Exception:
        logger.warning("queue_fallback", reason="redis_connection_failed", redis_url=settings.redis_url)
        return InMemoryQueue()

