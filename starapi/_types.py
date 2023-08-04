from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    AsyncContextManager,
    Callable,
    Coroutine,
    Literal,
    Mapping,
    MutableMapping,
    Protocol,
    Type,
    TypeAlias,
    TypedDict,
    TypeVar,
)

from .middleware import BaseMiddleware
from .requests import Request, WebSocket

if TYPE_CHECKING:
    from msgspec import Struct
    from typing_extensions import TypeVar

    from .app import Application
    from .groups import Group

    AppT = TypeVar("AppT", bound=Application, default=Application)
    GroupT = TypeVar("GroupT", bound=Group, covariant=True, default=Group)
    StructT = TypeVar("StructT", bound=Type[Struct], default=Type[Struct])
else:
    AppT = TypeVar("AppT")
    GroupT = TypeVar("GroupT", bound="Group")
    StructT = TypeVar("StructT", bound="Struct")

AppType = TypeVar("AppType")
Connection = Request | WebSocket

Scope = MutableMapping[str, Any]

Receive: TypeAlias = """
Callable[
    [], Coroutine[Any, Any, WSMessage | HTTPMessage | LifespanMessage]
]
"""
Send: TypeAlias = """
Callable[
    [WSMessage | HTTPMessage | LifespanMessage], Coroutine[Any, Any, None]
]
"""

ASGIApp = Callable[[Scope, Receive, Send], Coroutine[Any, Any, None]]

StatelessLifespan = Callable[[AppType], AsyncContextManager[None]]
StatefulLifespan = Callable[[AppType], AsyncContextManager[Mapping[str, Any]]]
Lifespan = StatelessLifespan[AppType] | StatefulLifespan[AppType]

Middleware = BaseMiddleware | Callable[[Request | WebSocket], Coroutine[Any, Any, Any]]

Headers = list[tuple[bytes, bytes]]


class Decoder(Protocol):
    def __call__(self, body: bytes | str, *, type: StructT) -> StructT:
        ...


Encoder = Callable[[StructT], bytes]


class WSCloseMessage(TypedDict):
    type: Literal["websocket.close"]
    code: int
    reason: str


class WSAcceptMessage(TypedDict):
    type: Literal["websocket.accept"]
    subprotocol: str | None
    headers: Headers


class _WSSendDataMessage(TypedDict):
    type: Literal["websocket.send"]


class WSSendTextMessage(_WSSendDataMessage):
    text: str


class WSSendBytesMessage(_WSSendDataMessage):
    bytes: bytes


class WSSendJSONMessage(_WSSendDataMessage):
    json: dict | list


WSMessage: TypeAlias = (
    WSCloseMessage
    | WSAcceptMessage
    | WSSendTextMessage
    | WSSendBytesMessage
    | WSSendJSONMessage
)


class StartResponseMessage(TypedDict):
    type: Literal["http.response.start"]
    status: int
    headers: Headers


class BodyResponseMessage(TypedDict):
    type: Literal["http.response.body"]
    body: bytes


HTTPMessage: TypeAlias = StartResponseMessage | BodyResponseMessage


class LifespanStartupCompleteMessage(TypedDict):
    type: Literal["lifespan.startup.complete"]


class LifespanShutdownCompleteMessage(TypedDict):
    type: Literal["lifespan.shutdown.complete"]


class LifespanStartupFailed(TypedDict):
    type: Literal["lifespan.startup.failed"]
    message: str


class LifespanShutdownFailed(TypedDict):
    type: Literal["lifespan.shutdown.failed"]
    message: str


LifespanMessage: TypeAlias = (
    LifespanStartupCompleteMessage
    | LifespanShutdownCompleteMessage
    | LifespanStartupFailed
    | LifespanShutdownFailed
)
