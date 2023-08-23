from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from typing import Any, Type

from .utils import MISSING

al = r".*"

__all__ = ("Converter",)


class Converter(ABC):
    regex: str

    def __init__(self, *, regex: str = MISSING) -> None:
        if regex:
            self.regex = regex

    def __init_subclass__(cls, *, regex: str = MISSING) -> None:
        if regex is MISSING:
            cls.regex = r".*"
        else:
            cls.regex = regex

    @abstractmethod
    def convert(self, value: str) -> Any:
        raise NotImplementedError("This should be overriden")

    @classmethod
    def decode(cls, value: Any) -> Any:
        return value

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}> regex={self.regex!r}"


class FloatConverter(Converter, regex=r"[0-9]*.[0-9]*"):
    def convert(self, value: str) -> float:
        if "." in value:
            return float(value)
        else:
            raise ValueError("Invalid Float Given")


class IntConverter(Converter, regex=r"[0-9]*"):
    def convert(self, value: str) -> int:
        return int(value)


class DatetimeConverter(Converter):
    def convert(self, inp: str) -> datetime.datetime:
        try:
            return datetime.datetime.fromtimestamp(float(inp))
        except (OSError, ValueError):
            pass
        try:
            return datetime.datetime.fromisoformat(inp)
        except OSError:
            pass
        try:
            return datetime.datetime.fromordinal(int(inp))
        except OSError:
            pass
        raise ValueError()


builtin_converters: dict[Type, Type[Converter]] = {
    int: IntConverter,
    float: FloatConverter,
    datetime.datetime: DatetimeConverter,
}
