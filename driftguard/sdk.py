from __future__ import annotations

import asyncio
import functools
import inspect
import uuid
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Awaitable, Callable, ParamSpec, TypeVar

import structlog

from driftguard.config import DriftGuardSettings, get_settings
from driftguard.detectors.drift import DriftDetector
from driftguard.detectors.injection import InjectionDetector
from driftguard.detectors.trust import TrustScoreDetector
from driftguard.models import QueueTracePayload
from driftguard.pipeline.queue import BaseQueue, create_queue
from driftguard.pipeline.worker import SpawnWorker
from driftguard.storage.db import DriftGuardDatabase

P = ParamSpec("P")
R = TypeVar("R")

logger = structlog.get_logger(__name__)


class TraceContext(AbstractAsyncContextManager["TraceHandle"]):
    def __init__(self, guard: "DriftGuard", prompt: str, model: str = "unknown", metadata: dict[str, Any] | None = None) -> None:
        self.guard = guard
        self.prompt = prompt
        self.model = model
        self.metadata = metadata or {}
        self.trace_id = str(uuid.uuid4())
        self.timestamp = datetime.now(timezone.utc)
        self._start = perf_counter()
        self._response: Any = ""

    async def __aenter__(self) -> "TraceHandle":
        await self.guard.start()
        return TraceHandle(context=self)

    async def __aexit__(self, exc_type: object, exc: BaseException | None, tb: object) -> None:
        if exc is not None:
            self.metadata = {**self.metadata, "error": repr(exc)}
        await self.guard._enqueue_trace(
            trace_id=self.trace_id,
            timestamp=self.timestamp,
            prompt=self.prompt,
            response=self._response,
            model=self.model,
            latency_ms=(perf_counter() - self._start) * 1000.0,
            metadata=self.metadata,
        )

    def set_response(self, response: Any) -> None:
        self._response = response


class TraceHandle:
    def __init__(self, context: TraceContext) -> None:
        self._context = context

    def set_response(self, response: Any) -> None:
        self._context.set_response(response)

    @property
    def trace_id(self) -> str:
        return self._context.trace_id


class DriftGuard:
    def __init__(
        self,
        settings: DriftGuardSettings | None = None,
        queue: BaseQueue | None = None,
        db: DriftGuardDatabase | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.db = db or DriftGuardDatabase(self.settings.db_path)
        self.queue = queue
        self.injection_detector = InjectionDetector(self.settings)
        self.drift_detector = DriftDetector(self.settings)
        self.trust_detector = TrustScoreDetector(self.settings)
        self.worker: SpawnWorker | None = None
        self._start_lock = asyncio.Lock()
        self._started = False
        self._shutdown = False
        self._configure_logging()

    async def start(self) -> None:
        if self._started:
            return
        async with self._start_lock:
            if self._started:
                return
            await self.db.initialize()
            if self.queue is None:
                self.queue = await create_queue(self.settings)
            self.worker = SpawnWorker(
                queue=self.queue,
                db=self.db,
                injection_detector=self.injection_detector,
                drift_detector=self.drift_detector,
                trust_detector=self.trust_detector,
            )
            await self.worker.start()
            self._started = True
            self._shutdown = False

    async def stop(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        if self.worker is not None:
            await self.worker.stop()
        self.worker = None
        self.queue = None
        self._started = False

    def monitor(
        self,
        func: Callable[P, Awaitable[R]] | None = None,
        *,
        prompt_arg: str = "prompt",
        model: str = "unknown",
        metadata: dict[str, Any] | None = None,
    ) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]] | Callable[P, Awaitable[R]]:
        def decorator(target: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
            @functools.wraps(target)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                prompt = self._extract_prompt(target, prompt_arg, args, kwargs)
                return await self.wrap(
                    prompt=prompt,
                    call=lambda: target(*args, **kwargs),
                    model=model,
                    metadata=metadata,
                )

            return wrapper

        if func is not None:
            return decorator(func)
        return decorator

    def trace(self, prompt: str, model: str = "unknown", metadata: dict[str, Any] | None = None) -> TraceContext:
        return TraceContext(guard=self, prompt=prompt, model=model, metadata=metadata)

    async def wrap(
        self,
        prompt: str,
        call: Callable[[], Awaitable[R] | R],
        model: str = "unknown",
        metadata: dict[str, Any] | None = None,
    ) -> R:
        await self.start()
        trace_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        start = perf_counter()
        result = call()
        if inspect.isawaitable(result):
            response = await result
        else:
            response = result
        latency_ms = (perf_counter() - start) * 1000.0
        await self._enqueue_trace(
            trace_id=trace_id,
            timestamp=timestamp,
            prompt=prompt,
            response=response,
            model=model,
            latency_ms=latency_ms,
            metadata=metadata or {},
        )
        return response

    async def _enqueue_trace(
        self,
        *,
        trace_id: str,
        timestamp: datetime,
        prompt: str,
        response: Any,
        model: str,
        latency_ms: float,
        metadata: dict[str, Any],
    ) -> None:
        if self.queue is None:
            raise RuntimeError("DriftGuard queue is not initialized")
        payload = QueueTracePayload(
            trace_id=trace_id,
            timestamp=timestamp,
            prompt=prompt,
            response=self._stringify_response(response),
            model=model,
            latency_ms=latency_ms,
            metadata=metadata,
        )
        await self.queue.publish(payload)

    def _stringify_response(self, response: Any) -> str:
        if isinstance(response, str):
            return response
        if hasattr(response, "model_dump_json"):
            return response.model_dump_json()
        if hasattr(response, "model_dump"):
            return str(response.model_dump())
        if hasattr(response, "text"):
            return str(getattr(response, "text"))
        if hasattr(response, "content"):
            return str(getattr(response, "content"))
        return str(response)

    def _extract_prompt(
        self,
        target: Callable[P, Awaitable[R]],
        prompt_arg: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> str:
        signature = inspect.signature(target)
        bound = signature.bind_partial(*args, **kwargs)
        if prompt_arg not in bound.arguments:
            raise ValueError(f"Prompt argument '{prompt_arg}' was not provided to monitored function")
        return str(bound.arguments[prompt_arg])

    def _configure_logging(self) -> None:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(getattr(__import__("logging"), self.settings.log_level, 20)),
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.EventRenamer("event"),
                structlog.processors.JSONRenderer(),
            ],
        )


driftguard = DriftGuard()


def monitor(
    func: Callable[P, Awaitable[R]] | None = None,
    *,
    prompt_arg: str = "prompt",
    model: str = "unknown",
    metadata: dict[str, Any] | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]] | Callable[P, Awaitable[R]]:
    return driftguard.monitor(func=func, prompt_arg=prompt_arg, model=model, metadata=metadata)


def trace(prompt: str, model: str = "unknown", metadata: dict[str, Any] | None = None) -> TraceContext:
    return driftguard.trace(prompt=prompt, model=model, metadata=metadata)


async def wrap(
    prompt: str,
    call: Callable[[], Awaitable[R] | R],
    model: str = "unknown",
    metadata: dict[str, Any] | None = None,
) -> R:
    return await driftguard.wrap(prompt=prompt, call=call, model=model, metadata=metadata)
