from __future__ import annotations

import pytest

from driftguard.config import DriftGuardSettings
from driftguard.detectors.drift import DriftDetector


@pytest.mark.asyncio
async def test_baseline_builds_correctly_from_100_prompts() -> None:
    detector = DriftDetector(DriftGuardSettings())
    for index in range(100):
        result = await detector.detect(f"Summarize customer support ticket #{index} about refund timing and billing issues.")
    assert detector.baseline_size == 100
    assert result.baseline_size == 100


@pytest.mark.asyncio
async def test_on_topic_prompts_score_below_point_two() -> None:
    detector = DriftDetector(DriftGuardSettings())
    for index in range(100):
        await detector.detect(f"Weather forecast summary for Seattle day {index} with rain and temperature notes.")
    result = await detector.detect("Provide a weather forecast summary for Seattle with rain chances and temperature.")
    assert result.score < 0.2


@pytest.mark.asyncio
async def test_off_topic_prompts_score_above_point_four() -> None:
    detector = DriftDetector(DriftGuardSettings())
    for index in range(100):
        await detector.detect(f"Weather forecast summary for Seattle day {index} with rain and temperature notes.")
    result = await detector.detect("Draft a legal indemnification clause for a software reseller agreement.")
    assert result.score > 0.4

