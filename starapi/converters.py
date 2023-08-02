from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._types import Converter

al = r".*"


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
