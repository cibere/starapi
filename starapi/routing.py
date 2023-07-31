from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, Generic, Literal, Type, TypeAlias, TypeVar, Self
from re import Pattern
import traceback
from .requests import Request
from .responses import Response
from .utils import MISSING, url_from_scope
from yarl import URL
from starlette.routing import compile_path
from .enums import Match
if TYPE_CHECKING:
    from typing_extensions import TypeVar

    from .groups import Group
    from .state import State
    from ._types import Receive, Scope, Send, Lifespan, AppT

    GroupT = TypeVar("GroupT", bound=Group, covariant=True, default=Group)
else:
    GroupT = TypeVar("GroupT", bound="Group")


__all__ = ("route", "Route")

RouteType: TypeAlias = "Route"
ResponseType: TypeAlias = Coroutine[Any, Any, Response]
HTTPRouteCallback: TypeAlias = Callable[..., ResponseType]

RouteDecoCallbackType: TypeAlias = (
    Callable[
        [HTTPRouteCallback],
        RouteType,
    ]
)



class _DefaultLifespan:
    def __init__(self, app: AppT) -> None:
        ...

    async def __aenter__(self) -> None:
        ...

    async def __aexit__(self, *exc_info: object) -> None:
        ...

class BaseRoute(ABC, Generic[GroupT]):
    _group: GroupT | None
    _state: State
    _path_regex: Pattern

    def __init__(self, *, path: str, prefix: bool) -> None:
        self._path: str = path
        self._add_prefix: bool = prefix

        self._group = None
        self._resolved = None
        self._path_regex, _, self._path_convertors = compile_path(path)

    @abstractmethod
    def _match(self, scope: Scope) -> tuple[Match, Scope]:
        raise NotImplementedError()
    
    @property
    def group(self) -> GroupT | None:
        return self._group

    @property
    def path(self) -> str:
        return self._path

    @path.setter
    def path(self, new_path: str):
        self._path = new_path
        self._path_regex = compile_path(new_path)

    @property
    def add_prefix(self) -> bool:
        return self._add_prefix


class Route(BaseRoute):
    def __init__(
        self,
        *,
        path: str,
        callback: HTTPRouteCallback,
        methods: list[str],
        prefix: bool = MISSING,
    ) -> None:
        self._callback: HTTPRouteCallback = callback
        super().__init__(path=path, prefix=prefix)
        self._methods = methods

    @property
    def callback(self) -> HTTPRouteCallback:
        return self._callback

    @property
    def methods(self) -> list[str]:
        return self._methods

    def _match(self, scope: Scope) -> tuple[Match, Scope]:
        match = self._path_regex.match(scope['path'])
        if match:
            data = match.groupdict()
            for key, value in data.items():
                data[key] = self._path_convertors[key].convert(value)

            path_params = dict(scope.get("path_params", {}))
            path_params.update(data)
            child_scope = {"path_params": path_params}
            
            if self.methods and scope["method"] not in self.methods:
                return Match.PARTIAL, child_scope
            else:
                return Match.FULL, child_scope
        return Match.NONE, {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)

        args = []

        response = None
        if self._group is not None:
            args.append(self._group)

            try:
                response = await self._group.group_check(request)
            except Exception as e:
                self._state.on_route_error(request, e)
                response = Response.internal()

        if response is None:
            args.append(request)

            try:
                response = await self._callback(*args)
            except Exception as e:
                self._state.on_route_error(request, e)
                response = Response.internal()

        await response(scope, receive, send)

class RouteSelector:
    def __call__(
        self,
        path: str,
        /,
        *,
        methods: list[str],
        prefix: bool = ...,
    ) -> RouteDecoCallbackType:
        def decorator(callback: HTTPRouteCallback) -> RouteType:
            return Route(path=path, callback=callback, methods=methods, prefix=prefix)

        return decorator

    def get(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["GET"], prefix=prefix)

    def post(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["POST"], prefix=prefix)

    def put(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["PUT"], prefix=prefix)

    def delete(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["DELETE"], prefix=prefix)

    def patch(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["PATCH"], prefix=prefix)


route = RouteSelector()

class Router:
    routes: list[RouteType]
    lifespan_context: Lifespan

    def __init__(self, *, lifespan: Lifespan = MISSING) -> None:
        self.routes = []

        self.lifespan_context = lifespan or _DefaultLifespan

    async def lifespan(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Handle ASGI lifespan messages, which allows us to manage application
        startup and shutdown events.
        """
        started = False
        app: AppT = scope.get("app")
        await receive()
        try:
            async with self.lifespan_context(app) as maybe_state:
                if maybe_state is not None:
                    if "state" not in scope:
                        raise RuntimeError(
                            'The server does not support "state" in the lifespan scope.'
                        )
                    scope["state"].update(maybe_state)
                await send({"type": "lifespan.startup.complete"})
                started = True
                await receive()
        except Exception:
            exc_text = traceback.format_exc()
            if started:
                await send({"type": "lifespan.shutdown.failed", "message": exc_text})
            else:
                await send({"type": "lifespan.startup.failed", "message": exc_text})
            raise
        else:
            await send({"type": "lifespan.shutdown.complete"})


    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] in ("http", "websocket", "lifespan")

        if "router" not in scope:
            scope["router"] = self

        if scope["type"] == "lifespan":
            await self.lifespan(scope, receive, send)
            return

        partial = None

        for route in self.routes:
            # Determine if any route matches the incoming scope,
            # and hand over to the matching route if found.
            match, child_scope = route._match(scope)
            if match == Match.FULL:
                scope.update(child_scope)
                await route(scope, receive, send)
                return
            elif match == Match.PARTIAL and partial is None:
                partial = route
                partial_scope = child_scope

        if partial is not None:
            #  Handle partial matches. These are cases where an endpoint is
            # able to handle the request, but is not a preferred option.
            # We use this in particular to deal with "405 Method Not Allowed".
            scope.update(partial_scope)
            await partial(scope, receive, send)
            return

        """if scope["type"] == "http" and self.redirect_slashes and scope["path"] != "/":
            redirect_scope = dict(scope)
            if scope["path"].endswith("/"):
                redirect_scope["path"] = redirect_scope["path"].rstrip("/")
            else:
                redirect_scope["path"] = redirect_scope["path"] + "/"

            for route in self.routes:
                match, child_scope = route.matches(redirect_scope)
                if match != Match.NONE:
                    response = Response.redirect(str(url_from_scope(redirect_scope)))
                    await response(scope, receive, send)
                    return"""

        await Response.not_found()(scope, receive, send)