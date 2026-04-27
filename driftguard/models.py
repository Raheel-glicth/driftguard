from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    trace_id: str
    timestamp: datetime
    prompt: str
    response: str
    model: str
    latency_ms: float
    injection_score: float
    drift_score: float
    hallucination_risk: float
    trust_score: float
    flagged: bool
    flag_reasons: list[str]
    metadata: dict[str, Any]


class InjectionJudgeResult(BaseModel):
    is_injection: bool
    confidence: float
    reason: str


class InjectionResult(BaseModel):
    score: float
    triggered_rules: list[str] = Field(default_factory=list)
    is_flagged: bool = False
    llm_judge: InjectionJudgeResult | None = None


class DriftResult(BaseModel):
    score: float
    baseline_size: int
    alert: bool
    psi: float | None = None


class TrustScoreResult(BaseModel):
    trust_score: float
    hallucination_risk: float
    flagged: bool
    flag_reasons: list[str] = Field(default_factory=list)


class TraceFeedback(BaseModel):
    correct_label: bool
    notes: str = ""


class QueueTracePayload(BaseModel):
    trace_id: str
    timestamp: datetime
    prompt: str
    response: str
    model: str
    latency_ms: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceStats(BaseModel):
    total_requests: int
    flagged_count: int
    avg_trust_score: float
    injection_rate: float
    drift_rate: float
    top_flag_reasons: list[dict[str, Any]]


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    model: str | None = None
    system_prompt: str | None = None
    session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    reply: str
    model: str
    trace_id: str
    created_at: datetime
