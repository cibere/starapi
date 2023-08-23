from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

from .routing import Route, RouteType, WebSocketRoute
from .utils import MISSING

if TYPE_CHECKING:
    from .app import Application
    from .requests import BaseRequest, Request, WebSocket
    from .responses import Response


__all__ = ("Group",)


class Group:
    prefix: str
    __routes__: list[RouteType]
    app: Application
    _deprecated: bool

    def __init_subclass__(
        cls, prefix: str = MISSING, deprecated: bool = MISSING
    ) -> None:
        cls.prefix = prefix or cls.__name__
        cls._deprecated = deprecated
        if cls.prefix and not cls.prefix.startswith("/"):
            cls.prefix = f"/{cls.prefix}"

    def __init__(self, app: Application, deprecated: bool = MISSING) -> None:
        self.__routes__ = []
        self.app = app

        for _, route in inspect.getmembers(
            self, predicate=lambda m: isinstance(m, (Route, WebSocketRoute))
        ):
            route: RouteType

            route._group = self
            route._path = f'{self.prefix.lower()}/{route.path.lstrip("/")}'

            if isinstance(route, WebSocketRoute):
                before = route.on_connect
                route.on_connect = lambda ws: before(self, ws)  # type: ignore # this allows for non-subclassed websockets in groups

            self.__routes__.append(route)

        if deprecated is MISSING and self._deprecated is MISSING:
            self.deprecated = False
        elif deprecated is not MISSING:
            self.deprecated = deprecated
        else:
            self.deprecated = self._deprecated

    @property
    def deprecated(self) -> bool:
        return self._deprecated

    @deprecated.setter
    def deprecated(self, new: bool):
        for route in self.__routes__:
            if isinstance(route, Route):
                route.deprecated = new
        self._deprecated = new

    @property
    def name(self) -> str:
        return self.__class__.__name__.lower()

    @property
    def routes(self) -> list[RouteType]:
        return self.__routes__

    async def group_check(self, request: BaseRequest) -> Response | None:
        """
        Group check. Before routes in this group are executed, this gets called.
        If a response is returned, the route will not be executed and the response will be sent.
        If None is returned, the route will be executed.

        Parameters
        -----------
        request: Request
            The request

        Returns
        -----------
        Response | None
            The response or None
        """

        ...

    async def on_route_error(
        self, request: Request, error: Exception
    ) -> Response | None:
        ...

    async def on_ws_error(self, request: WebSocket, error: Exception) -> None:
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} prefix={self.prefix!r} routes={len(self.routes)}>"
