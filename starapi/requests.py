from __future__ import annotations

from typing import TYPE_CHECKING, Generic

from starlette.requests import Request as _Request
from starlette.websockets import WebSocket as _WS

if TYPE_CHECKING:
    from typing import TypeVar

    from .app import Application

    UserT = TypeVar("UserT")
    AppT = TypeVar("AppT", bound=Application)

__all__ = ("Request", "WebSocket")


class Request(_Request, Generic[AppT, UserT]):
    app: AppT
    user: UserT


class WebSocket(_WS, Generic[AppT, UserT]):
    app: AppT
    user: UserT
