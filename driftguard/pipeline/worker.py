from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Callable

import structlog

from driftguard.detectors.drift import DriftDetector
from driftguard.detectors.injection import InjectionDetector
from driftguard.detectors.trust import TrustScoreDetector
from driftguard.models import QueueTracePayload, TraceEvent
from driftguard.pipeline.queue import BaseQueue
from driftguard.storage.db import DriftGuardDatabase

logger = structlog.get_logger(__name__)


class TraceProcessor:
    def __init__(
        self,
        db: DriftGuardDatabase,
        injection_detector: InjectionDetector,
        drift_detector: DriftDetector,
        trust_detector: TrustScoreDetector,
    ) -> None:
        self.db = db
        self.injection_detector = injection_detector
        self.drift_detector = drift_detector
        self.trust_detector = trust_detector

    async def process_payload(self, payload: QueueTracePayload) -> None:
        injection_result, drift_result = await asyncio.gather(
            self.injection_detector.detect(payload.prompt),
            self.drift_detector.detect(payload.prompt),
        )
        trust_result = await self.trust_detector.assess(
            prompt=payload.prompt,
            response=payload.response,
            injection=injection_result,
            drift=drift_result,
        )
        psi = await self.drift_detector.compute_psi_if_due(self.db)
        metadata = dict(payload.metadata)
        if psi is not None:
            metadata["prompt_length_psi"] = psi
        metadata["embedding_backend"] = (
            "hash_fallback" if self.drift_detector.using_fallback_encoder else self.drift_detector.settings.embedding_model
        )

        trace = TraceEvent(
            trace_id=payload.trace_id,
            timestamp=payload.timestamp,
            prompt=payload.prompt,
            response=payload.response,
            model=payload.model,
            latency_ms=payload.latency_ms,
            injection_score=injection_result.score,
            drift_score=drift_result.score,
            hallucination_risk=trust_result.hallucination_risk,
            trust_score=trust_result.trust_score,
            flagged=trust_result.flagged,
            flag_reasons=trust_result.flag_reasons,
            metadata=metadata,
        )
        await self.db.insert_trace(trace)

        if trace.flagged:
            logger.warning(
                "trace_flagged",
                trace_id=trace.trace_id,
                model=trace.model,
                trust_score=trace.trust_score,
                reasons=trace.flag_reasons,
            )

        self.injection_detector.schedule_llm_judge(
            prompt=payload.prompt,
            callback=self.judge_callback(payload.trace_id),
        )

    def judge_callback(self, trace_id: str) -> Callable[[object], Awaitable[None]]:
        async def callback(judge_result: object) -> None:
            if hasattr(judge_result, "model_dump"):
                payload = {"llm_judge": judge_result.model_dump()}
            else:
                payload = {"llm_judge": judge_result}
            await self.db.update_trace_metadata(trace_id, payload)

        return callback


class SpawnWorker:
    def __init__(
        self,
        queue: BaseQueue,
        db: DriftGuardDatabase,
        injection_detector: InjectionDetector,
        drift_detector: DriftDetector,
        trust_detector: TrustScoreDetector,
    ) -> None:
        self.queue = queue
        self.processor = TraceProcessor(
            db=db,
            injection_detector=injection_detector,
            drift_detector=drift_detector,
            trust_detector=trust_detector,
        )
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.queue.close()

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                payload = await self.queue.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("worker_queue_read_failed")
                await asyncio.sleep(0.5)
                continue

            try:
                await self._process_payload(payload)
            except Exception:
                logger.exception("worker_process_failed", trace_id=payload.trace_id)

    async def _process_payload(self, payload: QueueTracePayload) -> None:
        await self.processor.process_payload(payload)

