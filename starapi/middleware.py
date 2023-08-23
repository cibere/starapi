from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .requests import Request, WebSocket

__all__ = ("BaseMiddleware",)


class BaseMiddleware:
    async def handle_http(self, request: Request) -> None:
        ...

    async def handle_ws(self, ws: WebSocket) -> None:
        ...

    async def handle(self, connection: Request | WebSocket) -> None:
        ...

    async def __call__(self, connection: Request | WebSocket) -> None:
        if connection._type == 'http':
            await self.handle_http(connection)
        else:
            await self.handle_ws(connection)
        await self.handle(connection)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"
