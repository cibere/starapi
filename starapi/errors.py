from __future__ import annotations

import http
from ast import Str
from typing import TYPE_CHECKING

from .enums import WSMessageType

if TYPE_CHECKING:
    from .converters import Converter

__all__ = (
    "StarApiException",
    "GroupException",
    "GroupAlreadyAdded",
    "StartupException",
    "UvicornNotInstalled",
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
    "MsgSpecNotInstalled",
)


class StarApiException(Exception):
    ...


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


class UvicornNotInstalled(StartupException):
    def __init__(self) -> None:
        super().__init__(f"Uvicorn is not installed.")


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


class MsgSpecNotInstalled(PayloadException):
    def __init__(self) -> None:
        super().__init__(
            "'msgspec' is not installed. It is required for builtin payload functions."
        )


class InvalidBodyData(PayloadException):
    def __init__(self, body_format: str) -> None:
        super().__init__(f"Invalid {body_format!r} data received.")


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
