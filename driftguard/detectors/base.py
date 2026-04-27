from __future__ import annotations

from abc import ABC, abstractmethod


class Detector(ABC):
    @abstractmethod
    async def ready(self) -> bool:
        raise NotImplementedError

