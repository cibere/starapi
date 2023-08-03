from __future__ import annotations

from typing import Literal, Type

__all__ = ("Parameter",)


class Parameter:
    where: Literal["header", "query", "path", "cookie"]

    def __init__(
        self,
        *,
        required: bool,
        name: str,
        type: Type,
        deprecated: bool = False,
    ) -> None:
        self.required = required
        self.name = name
        self.annotation = type
        self.deprecated = deprecated
