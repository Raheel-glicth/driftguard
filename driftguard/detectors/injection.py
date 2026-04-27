from __future__ import annotations

import asyncio
import base64
import json
import re
from typing import Any, Awaitable, Callable

import httpx
import structlog

from driftguard.config import DriftGuardSettings
from driftguard.detectors.base import Detector
from driftguard.models import InjectionJudgeResult, InjectionResult

logger = structlog.get_logger(__name__)

ROLE_SWITCH_PHRASES = (
    "you are now",
    "pretend you are",
    "act as if",
    "act as",
    "roleplay as",
    "your new instructions",
)


class InjectionDetector(Detector):
    def __init__(self, settings: DriftGuardSettings) -> None:
        self.settings = settings
        self._regex_rules: list[tuple[str, re.Pattern[str]]] = [
            ("ignore_instructions", re.compile(r"ignore (previous|all|prior) instructions", re.IGNORECASE)),
            ("you_are_now", re.compile(r"you are now", re.IGNORECASE)),
            ("pretend_you_are", re.compile(r"pretend you are", re.IGNORECASE)),
            ("disregard", re.compile(r"disregard", re.IGNORECASE)),
            ("forget_everything", re.compile(r"forget everything", re.IGNORECASE)),
            ("new_instructions", re.compile(r"your new instructions", re.IGNORECASE)),
            ("system_prompt", re.compile(r"system prompt", re.IGNORECASE)),
            ("jailbreak", re.compile(r"jailbreak", re.IGNORECASE)),
            ("dan_mode", re.compile(r"dan mode", re.IGNORECASE)),
            ("act_as_if", re.compile(r"act as if", re.IGNORECASE)),
        ]
        self._base64_pattern = re.compile(r"[A-Za-z0-9+/=]{200,}")
        self._imperative_pattern = re.compile(
            r"\b(ignore|follow|list|write|describe|output|reveal|explain|pretend|act)\b",
            re.IGNORECASE,
        )
        self._judge_tasks: set[asyncio.Task[None]] = set()

    async def ready(self) -> bool:
        return True

    async def detect(self, prompt: str) -> InjectionResult:
        triggered_rules: list[str] = []
        score = 0.0

        regex_matches = [name for name, pattern in self._regex_rules if pattern.search(prompt)]
        if regex_matches:
            score += 0.4
            triggered_rules.extend(f"regex:{name}" for name in regex_matches)

        if self._contains_base64_blob(prompt):
            score += 0.4
            triggered_rules.append("regex:base64_blob")

        non_ascii_density = self._non_ascii_density(prompt)
        if non_ascii_density > 0.15:
            score += 0.2
            triggered_rules.append("heuristic:non_ascii_density")

        if len(prompt) > 2000 and self._imperative_pattern.search(prompt):
            score += 0.15
            triggered_rules.append("heuristic:long_instructional_prompt")

        role_switch_hits = sum(1 for phrase in ROLE_SWITCH_PHRASES if phrase in prompt.lower())
        if role_switch_hits > 1:
            score += 0.25
            triggered_rules.append("heuristic:multiple_role_switches")

        if any(marker in prompt for marker in ("<<", ">>", "[INST]", "<s>")):
            score += 0.2
            triggered_rules.append("heuristic:nested_instruction_markers")

        final_score = min(1.0, score)
        return InjectionResult(
            score=final_score,
            triggered_rules=triggered_rules,
            is_flagged=final_score > self.settings.injection_threshold,
        )

    def schedule_llm_judge(
        self,
        prompt: str,
        callback: Callable[[InjectionJudgeResult], Awaitable[None]],
    ) -> None:
        if not self.settings.llm_judge_api_key:
            return
        task = asyncio.create_task(self._run_llm_judge(prompt, callback))
        self._judge_tasks.add(task)
        task.add_done_callback(self._judge_tasks.discard)

    async def _run_llm_judge(
        self,
        prompt: str,
        callback: Callable[[InjectionJudgeResult], Awaitable[None]],
    ) -> None:
        try:
            judge_result = await self._call_llm_judge(prompt)
            if judge_result is not None:
                await callback(judge_result)
        except Exception:
            logger.exception("injection_llm_judge_failed")

    async def _call_llm_judge(self, prompt: str) -> InjectionJudgeResult | None:
        headers = {
            "Authorization": f"Bearer {self.settings.llm_judge_api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.settings.llm_judge_model,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Is the following text a prompt injection attempt? "
                        'Answer with JSON only: {"is_injection": bool, "confidence": float, "reason": str}.'
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return InjectionJudgeResult(
            is_injection=bool(parsed.get("is_injection", False)),
            confidence=float(parsed.get("confidence", 0.0)),
            reason=str(parsed.get("reason", "")),
        )

    def _contains_base64_blob(self, prompt: str) -> bool:
        matches = self._base64_pattern.findall(prompt)
        for match in matches:
            if len(match) < 200:
                continue
            try:
                base64.b64decode(match, validate=False)
            except Exception:
                continue
            return True
        return False

    def _non_ascii_density(self, prompt: str) -> float:
        if not prompt:
            return 0.0
        non_ascii_chars = sum(1 for char in prompt if ord(char) > 127)
        return non_ascii_chars / len(prompt)

