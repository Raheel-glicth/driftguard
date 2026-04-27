from __future__ import annotations

import asyncio
import hashlib
import importlib
import math
import re
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

import numpy as np
import structlog

from driftguard.config import DriftGuardSettings
from driftguard.detectors.base import Detector
from driftguard.models import DriftResult
from driftguard.storage.db import DriftGuardDatabase

logger = structlog.get_logger(__name__)


class EmbeddingModel(Protocol):
    def encode(self, texts: list[str], normalize_embeddings: bool = True) -> np.ndarray:
        ...


class HashEmbeddingModel:
    def __init__(self, dimensions: int = 512) -> None:
        self.dimensions = dimensions

    def encode(self, texts: list[str], normalize_embeddings: bool = True) -> np.ndarray:
        vectors = [self._encode_text(text) for text in texts]
        matrix = np.vstack(vectors)
        if normalize_embeddings:
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0.0] = 1.0
            matrix = matrix / norms
        return matrix

    def _encode_text(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dimensions, dtype=np.float32)
        normalized = text.lower()
        for token in re.findall(r"[A-Za-z_']+", normalized):
            vector[self._stable_index(f"tok:{token}")] += 1.5
        for token in re.findall(r"\d+", normalized):
            vector[self._stable_index(f"num:{token}")] += 0.25

        collapsed = re.sub(r"\s+", " ", normalized).strip()
        padded = f"  {collapsed}  "
        for ngram_size in (3, 4):
            for index in range(max(len(padded) - ngram_size + 1, 0)):
                ngram = padded[index : index + ngram_size]
                vector[self._stable_index(f"ng:{ngram}")] += 0.35
        return vector

    def _stable_index(self, value: str) -> int:
        digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "little") % self.dimensions


class DriftDetector(Detector):
    def __init__(self, settings: DriftGuardSettings) -> None:
        self.settings = settings
        self._baseline: deque[np.ndarray] = deque(maxlen=1000)
        self._centroid: np.ndarray | None = None
        self._seen_prompts = 0
        self._model: EmbeddingModel | None = None
        self._load_lock = asyncio.Lock()
        self._last_psi_run: datetime | None = None
        self._using_fallback_encoder = False

    async def ready(self) -> bool:
        await self._ensure_model()
        return self._model is not None

    async def detect(self, prompt: str) -> DriftResult:
        embedding = await self.embed(prompt)
        baseline_size = len(self._baseline)
        if baseline_size == 0 or self._centroid is None:
            score = 0.0
        else:
            score = 1.0 - self._cosine_similarity(embedding, self._centroid)
            if self._using_fallback_encoder:
                # The hash fallback is less semantically faithful than the real embedding model,
                # so we lightly calibrate its output to reduce false-positive drift locally.
                score *= 0.8

        self._baseline.append(embedding)
        self._seen_prompts += 1
        if self._centroid is None or self._seen_prompts % 100 == 0 or len(self._baseline) == 1:
            self._recompute_centroid()

        return DriftResult(
            score=max(0.0, min(1.0, float(score))),
            baseline_size=len(self._baseline),
            alert=score > self.settings.drift_threshold,
        )

    async def embed(self, prompt: str) -> np.ndarray:
        model = await self._ensure_model()
        encoded = model.encode([prompt], normalize_embeddings=True)
        return np.asarray(encoded[0], dtype=np.float32)

    async def compute_psi_if_due(self, db: DriftGuardDatabase) -> float | None:
        now = datetime.now(timezone.utc)
        if self._last_psi_run and now - self._last_psi_run < timedelta(hours=1):
            return None

        lengths = await db.get_prompt_lengths(limit=1000)
        if len(lengths) < 100:
            self._last_psi_run = now
            return 0.0

        midpoint = len(lengths) // 2
        recent = lengths[:midpoint]
        previous = lengths[midpoint:]
        psi = self._population_stability_index(previous, recent)
        self._last_psi_run = now
        return psi

    @property
    def baseline_size(self) -> int:
        return len(self._baseline)

    @property
    def using_fallback_encoder(self) -> bool:
        return self._using_fallback_encoder

    async def _ensure_model(self) -> EmbeddingModel:
        if self._model is not None:
            return self._model
        async with self._load_lock:
            if self._model is not None:
                return self._model
            if not self._embedding_model_available_locally():
                logger.warning("embedding_model_fallback", reason="model_not_cached_locally", model=self.settings.embedding_model)
                self._using_fallback_encoder = True
                self._model = HashEmbeddingModel()
                return self._model
            try:
                sentence_transformers = importlib.import_module("sentence_transformers")
                sentence_transformer_cls = getattr(sentence_transformers, "SentenceTransformer")
            except Exception:
                logger.warning("embedding_model_fallback", reason="sentence_transformers_unavailable")
                self._using_fallback_encoder = True
                self._model = HashEmbeddingModel()
                return self._model
            try:
                self._model = await asyncio.to_thread(
                    sentence_transformer_cls,
                    self.settings.embedding_model,
                    local_files_only=True,
                )
            except Exception:
                logger.exception("embedding_model_load_failed", model=self.settings.embedding_model)
                self._using_fallback_encoder = True
                self._model = HashEmbeddingModel()
            return self._model

    def _embedding_model_available_locally(self) -> bool:
        model_path = Path(self.settings.embedding_model)
        if model_path.exists():
            return True
        try:
            huggingface_hub = importlib.import_module("huggingface_hub")
            try_to_load_from_cache = getattr(huggingface_hub, "try_to_load_from_cache")
            cached_file = try_to_load_from_cache(self.settings.embedding_model, "config.json")
            return bool(cached_file)
        except Exception:
            return False

    def _recompute_centroid(self) -> None:
        matrix = np.vstack(self._baseline)
        centroid = np.mean(matrix, axis=0)
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm
        self._centroid = centroid.astype(np.float32)

    def _cosine_similarity(self, left: np.ndarray, right: np.ndarray) -> float:
        denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
        if denominator == 0.0:
            return 0.0
        return float(np.dot(left, right) / denominator)

    def _population_stability_index(self, baseline: list[int], current: list[int], bins: int = 10) -> float:
        min_value = min(baseline + current)
        max_value = max(baseline + current)
        if min_value == max_value:
            return 0.0

        edges = np.linspace(min_value, max_value, bins + 1)
        baseline_counts, _ = np.histogram(baseline, bins=edges)
        current_counts, _ = np.histogram(current, bins=edges)
        baseline_ratio = np.clip(baseline_counts / max(sum(baseline_counts), 1), 1e-6, 1.0)
        current_ratio = np.clip(current_counts / max(sum(current_counts), 1), 1e-6, 1.0)
        psi = np.sum((current_ratio - baseline_ratio) * np.log(current_ratio / baseline_ratio))
        if math.isnan(float(psi)):
            return 0.0
        return float(psi)
