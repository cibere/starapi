from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

from starlette import routing as _routing

from .routing import Route, WSRoute

if TYPE_CHECKING:
    from .app import Application
    from .requests import Request
    from .responses import Response


class Group:
    prefix: str
    __routes__: list[_routing.Route | _routing.WebSocketRoute]
    app: Application

    def __init_subclass__(cls, prefix: str | None = None) -> None:
        cls.prefix = prefix or cls.__name__

    def __init__(self, app: Application) -> None:
        self.__routes__ = []
        self.app = app

        for _, member in inspect.getmembers(
            self, predicate=lambda m: isinstance(m, (Route, WSRoute))
        ):
            member: Route | WSRoute

            member._group = self
            path: str = member._path

            if member._prefix:
                path = (
                    f'/{self.prefix.lower()}/{path.lstrip("/")}'
                    if self.prefix
                    else f'/{path.lstrip("/")}'
                )

            for method in member._methods:
                method = method.lower()

                setattr(member, method, member._callback)

            name = (
                f"{self.prefix}.{member._callback.__name__}"
                if self.prefix
                else member._callback.__name__
            )

            if isinstance(member, WSRoute):
                route = _routing.WebSocketRoute(
                    path=path, endpoint=member._callback, name=name
                )
            else:
                route = _routing.Route(
                    path=path, endpoint=member, methods=member._methods, name=name
                )

            self.__routes__.append(route)

    @property
    def name(self) -> str:
        return self.__class__.__name__.lower()

    async def group_check(self, request: Request) -> Response | None:
        return
