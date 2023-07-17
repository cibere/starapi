from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket as _WS

if TYPE_CHECKING:
    from .groups import Group

__all__ = ("Application",)


class Application(Starlette):
    def __init__(self, initial_routes: list[Route] | None = None) -> None:
        middleware: list[Middleware] = [
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
            ),
            Middleware(AuthenticationMiddleware, backend=AuthBackend(self)),
        ]

        super().__init__(middleware=middleware, routes=initial_routes)

    _groups: list[Group] = []

    def add_group(self, group: Group, *, prefix: str = "") -> None:
        if group in self._groups:
            raise RuntimeError(f"The {group.name} group was already added.")

        for route_ in group.__routes__:
            path = f"/{prefix}{route_.path}"

            if isinstance(route_, WebSocketRoute):
                new = WebSocketRoute(path, route_.endpoint, name=route_.name)
            else:
                new = Route(path, endpoint=route_.endpoint, methods=route_.methods, name=route_.name)  # type: ignore

            self.router.routes.append(new)
        self._groups.append(group)
