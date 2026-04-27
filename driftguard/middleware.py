from __future__ import annotations

import json
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from driftguard.sdk import DriftGuard, driftguard


class DriftGuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, guard: DriftGuard | None = None) -> None:
        super().__init__(app)
        self.guard = guard or driftguard

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        body = await request.body()
        prompt = self._extract_prompt(body)
        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": body, "more_body": False}
        request._receive = receive  # type: ignore[attr-defined]

        start = perf_counter()
        response = await call_next(request)
        elapsed_ms = (perf_counter() - start) * 1000.0
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        final_response = Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

        if prompt:
            await self.guard.start()
            await self.guard._enqueue_trace(
                trace_id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                prompt=prompt,
                response=response_body.decode("utf-8", errors="ignore"),
                model=request.headers.get("x-model", "http"),
                latency_ms=elapsed_ms,
                metadata={"path": request.url.path, "method": request.method},
            )
        return final_response

    def _extract_prompt(self, body: bytes) -> str | None:
        if not body:
            return None
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return None

        if isinstance(payload, dict):
            if "prompt" in payload:
                return str(payload["prompt"])
            if "messages" in payload and isinstance(payload["messages"], list):
                parts = [message.get("content", "") for message in payload["messages"] if isinstance(message, dict)]
                return "\n".join(str(part) for part in parts if part)
        return None
