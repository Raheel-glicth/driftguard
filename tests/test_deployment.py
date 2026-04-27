from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from driftguard.config import DriftGuardSettings
from driftguard.sdk import DriftGuard
from driftguard.storage.db import DriftGuardDatabase
from server import app


def test_root_server_exports_fastapi_app() -> None:
    assert app.title == "DriftGuard"


@pytest.mark.asyncio
async def test_sync_processing_mode_persists_trace_without_background_worker() -> None:
    db_file = Path.cwd() / f"driftguard-sync-test-{uuid4().hex}.db"
    settings = DriftGuardSettings(
        db_path=db_file.name,
        sync_processing=True,
        llm_judge_api_key=None,
    )
    guard = DriftGuard(
        settings=settings,
        db=DriftGuardDatabase(settings.db_path),
    )

    await guard.start()
    try:
        result = await guard.wrap(
            prompt="Explain why serverless-safe processing matters.",
            call=lambda: "Because the trace must be stored before the function exits.",
            model="test-model",
        )
        assert "trace must be stored" in result

        traces = await guard.db.list_traces(limit=5)
        assert len(traces) == 1
        assert traces[0].model == "test-model"
    finally:
        await guard.stop()
        db_file.with_suffix(".db-wal").unlink(missing_ok=True)
        db_file.with_suffix(".db-shm").unlink(missing_ok=True)
        db_file.unlink(missing_ok=True)
