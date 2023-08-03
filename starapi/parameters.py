from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, TypeAlias

ValidAnnotations: TypeAlias = Any

if TYPE_CHECKING:
    from .state import State

__all__ = ("Parameter",)


class Parameter:
    where: Literal["header", "query", "path", "cookie"]

    def __init__(
        self,
        *,
        required: bool,
        name: str,
        type: ValidAnnotations,
        deprecated: bool = False,
    ) -> None:
        self.required = required
        self.name = name
        self.annotation = type
        self.deprecated = deprecated

    def _to_openapi_spec(self, state: State) -> dict:
        schema = {"title": self.name.title()}
        schema["type"] = state.find_openapi_spec_type(self.annotation, schema)
        return {
            "required": self.required,
            "name": self.name,
            "in": self.where,
            "deprecated": self.deprecated,
            "schema": schema,
        }
