from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app import Application
    from .requests import Request

__all__ = ("State",)


class State:
    def __init__(self, app: Application):
        self.app = app

    async def _handle_route_error(self, request: Request, error: Exception) -> None:
        route = request.endpoint
        assert route is not None
        if route._group is not None:
            await route._group.on_error(request, error)
        await route._state.app.on_error(request, error)

    def on_route_error(self, request: Request, error: Exception) -> None:
        asyncio.create_task(self._handle_route_error(request, error))
