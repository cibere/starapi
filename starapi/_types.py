from typing import (
    TYPE_CHECKING,
    Any,
    AsyncContextManager,
    Callable,
    Coroutine,
    Mapping,
    MutableMapping,
    TypeVar,
)

from .middleware import BaseMiddleware
from .requests import Request

if TYPE_CHECKING:
    from typing_extensions import TypeVar

    from .app import Application
    from .groups import Group

    AppT = TypeVar("AppT", bound=Application)
    GroupT = TypeVar("GroupT", bound=Group, covariant=True, default=Group)
else:
    AppT = TypeVar("AppT")
    GroupT = TypeVar("GroupT", bound="Group")

AppType = TypeVar("AppType")

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]

Receive = Callable[[], Coroutine[Any, Any, Message]]
Send = Callable[[Message], Coroutine[Any, Any, None]]

ASGIApp = Callable[[Scope, Receive, Send], Coroutine[Any, Any, None]]

StatelessLifespan = Callable[[AppType], AsyncContextManager[None]]
StatefulLifespan = Callable[[AppType], AsyncContextManager[Mapping[str, Any]]]
Lifespan = StatelessLifespan[AppType] | StatefulLifespan[AppType]

Middleware = BaseMiddleware | Callable[[Request], Coroutine[Any, Any, Any]]

Converter = Callable[[str], Any]
