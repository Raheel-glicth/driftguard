from __future__ import annotations

import re

from driftguard.config import DriftGuardSettings
from driftguard.detectors.base import Detector
from driftguard.models import DriftResult, InjectionResult, TrustScoreResult


class TrustScoreDetector(Detector):
    def __init__(self, settings: DriftGuardSettings) -> None:
        self.settings = settings

    async def ready(self) -> bool:
        return True

    async def assess(
        self,
        prompt: str,
        response: str,
        injection: InjectionResult,
        drift: DriftResult,
    ) -> TrustScoreResult:
        hallucination_risk = self._hallucination_risk(prompt=prompt, response=response)
        weighted_average = (
            (injection.score * 0.5) + (drift.score * 0.3) + (hallucination_risk * 0.2)
        ) / 1.0
        trust_score = max(0.0, min(1.0, 1.0 - weighted_average))
        flag_reasons = list(injection.triggered_rules)

        if drift.alert:
            flag_reasons.append("drift:semantic_shift")
        if hallucination_risk >= 0.3:
            flag_reasons.append("trust:hallucination_risk")
        flagged = trust_score < self.settings.trust_threshold or injection.score > self.settings.injection_threshold

        return TrustScoreResult(
            trust_score=trust_score,
            hallucination_risk=hallucination_risk,
            flagged=flagged,
            flag_reasons=flag_reasons,
        )

    def _hallucination_risk(self, prompt: str, response: str) -> float:
        score = 0.0

        if self._asks_for_specifics_without_context(prompt):
            score += 0.3
        if self._response_introduces_new_urls(prompt, response):
            score += 0.2
        if re.search(r"\b(19|20)\d{2}\b", response) or re.search(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b", response):
            score += 0.25
        if re.search(r"\b\d+(?:\.\d+)?%\b", response):
            score += 0.25

        return min(0.8, score)

    def _asks_for_specifics_without_context(self, prompt: str) -> bool:
        lower_prompt = prompt.lower()
        asks_for_specifics = bool(
            re.search(r"\b(date|year|citation|citations|statistic|statistics|number|percentage|percent|exact)\b", lower_prompt)
        )
        has_context = any(token in lower_prompt for token in ("according to", "based on", "source:", "context:", "using this"))
        return asks_for_specifics and not has_context

    def _response_introduces_new_urls(self, prompt: str, response: str) -> bool:
        url_pattern = re.compile(r"https?://[^\s)]+")
        prompt_urls = set(url_pattern.findall(prompt))
        response_urls = set(url_pattern.findall(response))
        return bool(response_urls - prompt_urls)
