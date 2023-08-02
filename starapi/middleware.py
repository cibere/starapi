from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .requests import BaseRequest

__all__ = ("BaseMiddleware",)


class BaseMiddleware(ABC):
    @abstractmethod
    async def __call__(self, request: BaseRequest) -> None:
        ...
