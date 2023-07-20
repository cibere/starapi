from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

from .routing import Route, RouteType, WSRoute
from .utils import MISSING

if TYPE_CHECKING:
    from .app import Application
    from .requests import Request
    from .responses import Response


__all__ = ("Group",)


class Group:
    prefix: str
    __routes__: list[RouteType]
    app: Application

    def __init_subclass__(cls, prefix: str = MISSING) -> None:
        cls.prefix = prefix or cls.__name__
        if cls.prefix and not cls.prefix.startswith("/"):
            cls.prefix = f"/{cls.prefix}"

    def __init__(self, app: Application) -> None:
        self.__routes__ = []
        self.app = app

        for _, route in inspect.getmembers(
            self, predicate=lambda m: isinstance(m, Route | WSRoute)
        ):
            route: Route | WSRoute

            route._group = self
            route._path = f'{self.prefix.lower()}/{route.path.lstrip("/")}'
            self.__routes__.append(route)

            """for method in route._methods:
                method = method.lower()

                setattr(member, method, member._callback)"""

    @property
    def name(self) -> str:
        return self.__class__.__name__.lower()

    @property
    def routes(self) -> list[RouteType]:
        return self.__routes__

    async def group_check(self, request: Request) -> Response | None:
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

    async def on_error(self, request: Request, exec: Exception) -> None:
        ...
