from __future__ import annotations

from typing import TYPE_CHECKING, Any

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

        path: str = scope["path"]
        endpoints: list[str] = path.split("/")
        prefix = endpoints.pop(1)
        while len(endpoints) <= 1:
            endpoints.append("")

        scope["path"] = "/".join(endpoints)

        if self.case_insensitive:
            prefix = prefix.lower()

        app = self._apps.get(prefix, None)
        if app is None:
            await self.handle_404(scope, receive, send)
        else:
            print(f"Sent to {app}")
            await app(scope, receive, send)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} case_insensitive={self.case_insensitive!r} apps={len(self._apps)!r}>"
