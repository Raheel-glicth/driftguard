from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio

from driftguard.config import DriftGuardSettings
from driftguard.pipeline.queue import InMemoryQueue
from driftguard.sdk import DriftGuard
from driftguard.storage.db import DriftGuardDatabase


@pytest_asyncio.fixture
async def guard() -> DriftGuard:
    db_file = Path.cwd() / f"driftguard-test-{uuid4().hex}.db"
    settings = DriftGuardSettings(
        db_path=db_file.name,
        llm_judge_api_key=None,
    )
    instance = DriftGuard(
        settings=settings,
        queue=InMemoryQueue(),
        db=DriftGuardDatabase(settings.db_path),
    )
    await instance.start()
    yield instance
    await instance.stop()
    db_file.with_suffix(".db-wal").unlink(missing_ok=True)
    db_file.with_suffix(".db-shm").unlink(missing_ok=True)
    db_file.unlink(missing_ok=True)


async def wait_for_trace_count(guard: DriftGuard, expected: int, timeout: float = 2.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        traces = await guard.db.list_traces(limit=max(expected, 1))
        if len(traces) >= expected:
            return
        await asyncio.sleep(0.05)
    traces = await guard.db.list_traces(limit=max(expected, 1))
    raise AssertionError(f"Timed out waiting for {expected} traces, only found {len(traces)}")
