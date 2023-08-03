from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Any, Coroutine

from .errors import UvicornNotInstalled
from .requests import Request
from .responses import Response
from .utils import mimmic

if TYPE_CHECKING:
    import uvicorn

    from ._types import Receive, Scope, Send
    from .app import Application
else:

    class uvicorn:
        Config = Any
        run = Any


__all__ = ("Server",)


class BaseASGIApp:
    @mimmic(uvicorn.run, keep_return=True)
    def run(self, *args, **kwargs) -> None:
        """
        ! THIS REQUIRES 'uvicorn' TO BE INSTALLED

        This function is the default syncronous run method, which uses 'uvicorn'.
        See https://www.uvicorn.org/settings/ for more information on the kwargs that can be used.
        """

        try:
            import uvicorn
        except ImportError:
            raise UvicornNotInstalled() from None

        uvicorn.run(self, *args, **kwargs)

    @mimmic(uvicorn.Config, keep_return=True)
    async def start(self, *args, **kwargs) -> None:
        """
        ! THIS REQUIRES 'uvicorn' TO BE INSTALLED

        This function is the default asyncronous run method, which uses 'uvicorn'.
        See https://www.uvicorn.org/settings/ for more information on the kwargs that can be used.
        """

        try:
            import uvicorn
        except ImportError:
            raise UvicornNotInstalled() from None

        server = uvicorn.Server(uvicorn.Config(self, *args, **kwargs))
        await server.serve()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        ...


class Server(BaseASGIApp):
    def __init__(self, *, case_insensitive: bool = False) -> None:
        self._apps: dict[str, Application] = {}
        self.case_insensitive = case_insensitive

    async def handle_404(self, scope: Scope, receive: Receive, send: Send) -> None:
        print("App Not Found")
        request = Request(scope, receive, send)
        await Response.not_found()(request)

    def register_app(self, app: Application, *, prefix: str) -> None:
        if self.case_insensitive:
            prefix = prefix.strip().lower()

        if prefix in self._apps:
            raise ValueError(f"An app has already been registered with the '{prefix}'")

        self._apps[prefix] = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] in ("http", "lifespan", "websocket")

        print("-" * 10)

        path: str = scope["path"]
        endpoints: list[str] = path.split("/")
        print(path)
        print(endpoints)
        prefix = endpoints.pop(1)
        while len(endpoints) <= 1:
            endpoints.append("")
        print(endpoints)

        scope["path"] = "/".join(endpoints)
        print(scope["path"])

        if self.case_insensitive:
            prefix = prefix.lower()

        app = self._apps.get(prefix, None)
        if app is None:
            await self.handle_404(scope, receive, send)
        else:
            print(f"Sent to {app}")
            await app(scope, receive, send)
