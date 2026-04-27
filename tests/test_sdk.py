from __future__ import annotations

import asyncio
from time import perf_counter

import pytest

from driftguard.sdk import DriftGuard


async def wait_for_trace_count(guard: DriftGuard, expected: int, timeout: float = 2.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        traces = await guard.db.list_traces(limit=max(expected, 1))
        if len(traces) >= expected:
            return
        await asyncio.sleep(0.05)
    traces = await guard.db.list_traces(limit=max(expected, 1))
    raise AssertionError(f"Timed out waiting for {expected} traces, only found {len(traces)}")


@pytest.mark.asyncio
async def test_all_three_sdk_patterns_return_original_response(guard: DriftGuard) -> None:
    @guard.monitor(model="decorator-model")
    async def decorated_call(prompt: str) -> str:
        return f"decorated:{prompt}"

    decorator_result = await decorated_call("hello")

    async with guard.trace(prompt="context prompt", model="context-model") as trace:
        context_result = "context-response"
        trace.set_response(context_result)

    wrapped_result = await guard.wrap(
        prompt="wrap prompt",
        call=lambda: asyncio.sleep(0, result={"status": "ok"}),
        model="wrap-model",
    )

    assert decorator_result == "decorated:hello"
    assert context_result == "context-response"
    assert wrapped_result == {"status": "ok"}

    await wait_for_trace_count(guard, expected=3)
    traces = await guard.db.list_traces(limit=3)
    assert len(traces) == 3


@pytest.mark.asyncio
async def test_hot_path_latency_overhead_is_below_ten_ms(guard: DriftGuard) -> None:
    async def bare(prompt: str) -> str:
        return prompt.upper()

    @guard.monitor(model="latency-model")
    async def monitored(prompt: str) -> str:
        return await bare(prompt)

    await monitored("warmup")
    await wait_for_trace_count(guard, expected=1)

    iterations = 25
    bare_start = perf_counter()
    for _ in range(iterations):
        await bare("latency")
    bare_elapsed = (perf_counter() - bare_start) / iterations

    monitored_start = perf_counter()
    for _ in range(iterations):
        await monitored("latency")
    monitored_elapsed = (perf_counter() - monitored_start) / iterations

    assert (monitored_elapsed - bare_elapsed) * 1000.0 < 10.0


@pytest.mark.asyncio
async def test_wrap_returns_unmodified_non_string_response(guard: DriftGuard) -> None:
    payload = {"answer": 42, "ok": True}
    result = await guard.wrap(
        prompt="Return a payload",
        call=lambda: asyncio.sleep(0, result=payload),
        model="json-model",
        metadata={"source": "unit-test"},
    )
    assert result is payload
    await wait_for_trace_count(guard, expected=1)
    traces = await guard.db.list_traces(limit=1)
    assert traces[0].metadata["source"] == "unit-test"
