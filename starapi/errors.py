import http

from .enums import WSMessageType

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

    def __str__(self) -> str:
        return f"{self.status_code}: {self.detail}"

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}(status_code={self.status_code!r}, detail={self.detail!r})"


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
