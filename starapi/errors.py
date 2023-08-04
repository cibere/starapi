from __future__ import annotations

import http
from typing import TYPE_CHECKING, Type

from .enums import WSMessageType

if TYPE_CHECKING:
    from .converters import Converter

__all__ = (
    "StarApiException",
    "GroupException",
    "GroupAlreadyAdded",
    "StartupException",
    "ClientException",
    "ClientDisconnect",
    "ASGIException",
    "UnexpectedASGIMessageType",
    "WebSocketException",
    "WebSocketDisconnected",
    "WebSocketDisconnect",
    "RoutingException",
    "InvalidWebSocketRoute",
    "ConverterException",
    "ConverterAlreadyAdded",
    "ConverterNotFound",
    "PayloadException",
    "InvalidBodyData",
    "PayloadValidationException",
    "ConverterEntryNotFound",
    "DependencyException",
)


class StarApiException(Exception):
    ...


class DependencyException(StarApiException):
    def __init__(self, library: str, reason: str) -> None:
        super().__init__(f"{library!r} is not installed. {reason}")


class ClientException(StarApiException):
    ...


class ClientDisconnect(ClientException):
    ...


class GroupException(StarApiException):
    ...


class GroupAlreadyAdded(GroupException):
    name: str

    def __init__(self, name: str) -> None:
        super().__init__(f"The '{name}' group was already added")
        self.name = name


class StartupException(StarApiException):
    ...


class HTTPException(StarApiException):
    def __init__(
        self,
        status_code: int,
        detail: str | None = None,
        headers: dict | None = None,
    ) -> None:
        if detail is None:
            detail = http.HTTPStatus(status_code).phrase
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
        super().__init__(f"{status_code}: {detail}")


class PayloadException(StarApiException):
    ...


class InvalidBodyData(PayloadException):
    def __init__(self, body_format: str | None) -> None:
        if body_format is None:
            msg = "Invalid body received."
        else:
            msg = f"Invalid {body_format!r} data received."
        super().__init__(msg)


class PayloadValidationException(PayloadException):
    ...


class ASGIException(StarApiException):
    ...


class UnexpectedASGIMessageType(ASGIException):
    def __init__(
        self, expected: list[str | WSMessageType] | str | WSMessageType, received: str
    ) -> None:
        if isinstance(expected, str):
            expected = [expected]
        elif isinstance(expected, WSMessageType):
            expected = [expected.value]

        e = [f"{ex!r}" if isinstance(ex, str) else f"{ex.value!r}" for ex in expected]
        super().__init__(
            f"Expected ASGI message type {' or '.join(e)},"
            f"received {received!r} instead."
        )


class WebSocketException(StarApiException):
    ...


class WebSocketDisconnected(WebSocketException):
    def __init__(self) -> None:
        super().__init__("WebSocket is already disconnected")


class WebSocketDisconnect(WebSocketException):
    def __init__(self, code: int) -> None:
        super().__init__(f"WebSocket has disconnected with code {code}")


class RoutingException(StarApiException):
    ...


class InvalidWebSocketRoute(RoutingException):
    ...


class ConverterException(StarApiException):
    ...


class ConverterAlreadyAdded(ConverterException):
    def __init__(self, converter: Converter) -> None:
        super().__init__(f"The {converter!r} converter was already added")


class ConverterNotFound(ConverterException):
    def __init__(self, name: str) -> None:
        super().__init__(f"Converter {name!r} was not found")


class ConverterEntryNotFound(ConverterException):
    def __init__(self, converter: Type[Converter]) -> None:
        super().__init__(
            f"Converter {converter!r} has no valid entrypoint. Make sure the __new__ and __init__ take no required arguments"
        )
