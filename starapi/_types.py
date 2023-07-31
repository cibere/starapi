from typing import TypeVar, Callable, Coroutine, MutableMapping, Any, AsyncContextManager, Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    from .app import Application
    from .routing import Route

    AppT = TypeVar("AppT", bound=Application)
else:
    AppT = TypeVar("AppT")

AppType = TypeVar("AppType")

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]

Receive = Callable[[], Coroutine[Any, Any, Message]]
Send = Callable[[Message], Coroutine[Any, Any, None]]

ASGIApp = Callable[[Scope, Receive, Send], Coroutine[Any, Any, None]]

StatelessLifespan = Callable[[AppType], AsyncContextManager[None]]
StatefulLifespan = Callable[
    [AppType], AsyncContextManager[Mapping[str, Any]]
]
Lifespan = StatelessLifespan[AppType] | StatefulLifespan[AppType]
