from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._types import Converter

al = r".*"

builtin_converters: dict[str, tuple[str, Converter]] = {
    "int": (r"[0-9]*", int),
    "float": (r"[0-9]*.[0-9]*", float),
    "iso-datetime": (al, datetime.datetime.fromisoformat),
    "epoch-timestamp": (r"[0-9]*", lambda e: datetime.datetime.fromtimestamp(float(e))),
}
