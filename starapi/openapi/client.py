import json
from typing import Any


class OpenAPIClient:
    def __init__(self, *, title: str, version: str) -> None:
        self.title = title
        self.version = version


class Response:
    def __init__(self, *, code: int, description: str, body: Any) -> None:
        self.code = code
        self.description = description
        self.body = body

    def to_dict(self) -> dict:
        return {"description": self.description, "content": content}


class Parameter:
    def __init__(self, *, required: bool, name: str, type: str, where: str) -> None:
        self.required = required
        self.name = name
        self.type = type
        self.where = where


class EndpointMethod:
    def __init__(
        self,
        *,
        description: str,
        summary: str,
        responses: list[Response],
        parameters: list[Parameter]
    ) -> None:
        self.description = description
        self.summary = summary
        self.responses = responses
        self.parameters = parameters
