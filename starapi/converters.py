from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ._types import Converter

al = r".*"

__all__ = ("CustomConverter",)


class CustomConverter(ABC):
    def __init__(self, *, regex: str, name: str) -> None:
        self.regex = regex
        self.name = name

    @abstractmethod
    def convert(self, value: str) -> Any:
        raise NotImplementedError("This should be overriden")


def float_convertor(inp: str) -> float:
    if "." in inp:
        return float(inp)
    else:
        raise ValueError("Invalid Float Given")


def epoch_convertor(inp: str) -> datetime.datetime:
    try:
        return datetime.datetime.fromtimestamp(float(inp))
    except OSError:
        raise ValueError("Invalid Epoch Timestamp Given") from None


def iso_convertor(inp: str) -> datetime.datetime:
    try:
        return datetime.datetime.fromisoformat(inp)
    except OSError:
        raise ValueError("Invalid ISO Timestamp Given") from None


builtin_converters: dict[str, tuple[str, Converter]] = {
    "int": (r"[0-9]*", int),
    "float": (r"[0-9]*.[0-9]*", float_convertor),
    "iso-timestamp": (al, iso_convertor),
    "epoch-timestamp": (r"[0-9]*", epoch_convertor),
}
