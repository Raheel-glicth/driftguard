from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from driftguard.api.chatbot import create_chat_router
from driftguard.config import DriftGuardSettings
from driftguard.pipeline.queue import InMemoryQueue
from driftguard.sdk import DriftGuard
from driftguard.storage.db import DriftGuardDatabase


class _FakeResponseMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeResponseMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    async def create(self, *, model: str, messages: list[dict[str, str]]) -> _FakeResponse:
        assert model == "fake-model"
        assert messages[0]["role"] == "system"
        assert messages[-1]["role"] == "user"
        return _FakeResponse("Mocked assistant reply")


class _FakeChat:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()


class _FakeOpenAIClient:
    def __init__(self, *args, **kwargs) -> None:
        self.chat = _FakeChat()


def test_chat_api_returns_reply_and_creates_trace(monkeypatch) -> None:
    monkeypatch.setattr("driftguard.api.chatbot.AsyncOpenAI", _FakeOpenAIClient)

    db_file = Path.cwd() / f"driftguard-chat-test-{uuid4().hex}.db"
    settings = DriftGuardSettings(
        db_path=db_file.name,
        openai_api_key="test-key",
        chat_model="fake-model",
    )
    guard = DriftGuard(
        settings=settings,
        queue=InMemoryQueue(),
        db=DriftGuardDatabase(settings.db_path),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await guard.stop()

    app = FastAPI(lifespan=lifespan)
    app.include_router(create_chat_router(guard, settings))

    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "message": "Hello there",
                "history": [{"role": "assistant", "content": "Hi!"}],
                "session_id": "test-session",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["reply"] == "Mocked assistant reply"
        assert payload["model"] == "fake-model"
        assert payload["trace_id"]

        import time

        trace = None
        for _ in range(60):
            trace = asyncio.run(guard.db.get_trace(payload["trace_id"]))
            if trace is not None:
                break
            time.sleep(0.05)

        assert trace is not None
        assert trace.model == "fake-model"
        assert trace.metadata["session_id"] == "test-session"

    db_file.unlink(missing_ok=True)
    db_file.with_suffix(".db-wal").unlink(missing_ok=True)
    db_file.with_suffix(".db-shm").unlink(missing_ok=True)
