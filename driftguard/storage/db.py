from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite
import structlog

from driftguard.models import TraceEvent, TraceFeedback, TraceStats

logger = structlog.get_logger(__name__)


class DriftGuardDatabase:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    response TEXT NOT NULL,
                    model TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    injection_score REAL NOT NULL,
                    drift_score REAL NOT NULL,
                    hallucination_risk REAL NOT NULL,
                    trust_score REAL NOT NULL,
                    flagged INTEGER NOT NULL,
                    flag_reasons TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    prompt_length INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_traces_timestamp ON traces(timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_traces_flagged ON traces(flagged);
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL,
                    correct_label INTEGER NOT NULL,
                    notes TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(trace_id) REFERENCES traces(trace_id)
                );
                """
            )
            await conn.commit()

    async def insert_trace(self, trace: TraceEvent) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO traces (
                    trace_id, timestamp, prompt, response, model, latency_ms,
                    injection_score, drift_score, hallucination_risk, trust_score,
                    flagged, flag_reasons, metadata, prompt_length
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace.trace_id,
                    trace.timestamp.isoformat(),
                    trace.prompt,
                    trace.response,
                    trace.model,
                    trace.latency_ms,
                    trace.injection_score,
                    trace.drift_score,
                    trace.hallucination_risk,
                    trace.trust_score,
                    int(trace.flagged),
                    json.dumps(trace.flag_reasons),
                    json.dumps(trace.metadata),
                    len(trace.prompt.split()),
                ),
            )
            await conn.commit()

    async def update_trace_metadata(self, trace_id: str, metadata_patch: dict[str, Any]) -> None:
        trace = await self.get_trace(trace_id)
        if trace is None:
            return
        merged = dict(trace.metadata)
        merged.update(metadata_patch)
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "UPDATE traces SET metadata = ? WHERE trace_id = ?",
                (json.dumps(merged), trace_id),
            )
            await conn.commit()

    async def list_traces(self, limit: int = 50, offset: int = 0, flagged_only: bool = False) -> list[TraceEvent]:
        query = """
            SELECT trace_id, timestamp, prompt, response, model, latency_ms,
                   injection_score, drift_score, hallucination_risk, trust_score,
                   flagged, flag_reasons, metadata
            FROM traces
        """
        params: list[Any] = []
        if flagged_only:
            query += " WHERE flagged = 1"
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
        return [self._row_to_trace(row) for row in rows]

    async def get_trace(self, trace_id: str) -> TraceEvent | None:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT trace_id, timestamp, prompt, response, model, latency_ms,
                       injection_score, drift_score, hallucination_risk, trust_score,
                       flagged, flag_reasons, metadata
                FROM traces WHERE trace_id = ?
                """,
                (trace_id,),
            )
            row = await cursor.fetchone()
        return self._row_to_trace(row) if row else None

    async def add_feedback(self, trace_id: str, feedback: TraceFeedback) -> None:
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO feedback (trace_id, correct_label, notes, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (trace_id, int(feedback.correct_label), feedback.notes, datetime.now(timezone.utc).isoformat()),
            )
            await conn.commit()

    async def get_prompt_lengths(self, limit: int = 1000) -> list[int]:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT prompt_length FROM traces ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
        return [int(row[0]) for row in rows]

    async def get_stats(self) -> TraceStats:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(flagged), 0), COALESCE(AVG(trust_score), 0.0),
                       COALESCE(AVG(CASE WHEN injection_score > 0.7 THEN 1.0 ELSE 0.0 END), 0.0),
                       COALESCE(AVG(CASE WHEN drift_score > 0.35 THEN 1.0 ELSE 0.0 END), 0.0)
                FROM traces
                """
            )
            total_requests, flagged_count, avg_trust_score, injection_rate, drift_rate = await cursor.fetchone()
            reason_cursor = await conn.execute("SELECT flag_reasons FROM traces WHERE flagged = 1")
            reason_rows = await reason_cursor.fetchall()

        reason_counter: Counter[str] = Counter()
        for row in reason_rows:
            for reason in json.loads(row[0]):
                reason_counter[reason] += 1

        top_flag_reasons = [
            {"reason": reason, "count": count}
            for reason, count in reason_counter.most_common(5)
        ]
        return TraceStats(
            total_requests=int(total_requests),
            flagged_count=int(flagged_count),
            avg_trust_score=float(avg_trust_score),
            injection_rate=float(injection_rate),
            drift_rate=float(drift_rate),
            top_flag_reasons=top_flag_reasons,
        )

    def _row_to_trace(self, row: aiosqlite.Row) -> TraceEvent:
        return TraceEvent(
            trace_id=row["trace_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            prompt=row["prompt"],
            response=row["response"],
            model=row["model"],
            latency_ms=float(row["latency_ms"]),
            injection_score=float(row["injection_score"]),
            drift_score=float(row["drift_score"]),
            hallucination_risk=float(row["hallucination_risk"]),
            trust_score=float(row["trust_score"]),
            flagged=bool(row["flagged"]),
            flag_reasons=json.loads(row["flag_reasons"]),
            metadata=json.loads(row["metadata"]),
        )
