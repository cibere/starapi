from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .formatters import ResponseFormatter
from .responses import Response
from .routing import Route, Router
from .utils import MISSING

try:
    import msgspec
except ImportError:
    msgspec = None

if TYPE_CHECKING:
    from ._types import Decoder, Encoder, Lifespan
    from .app import Application
    from .groups import Group
    from .openapi import OpenAPI
    from .requests import BaseRequest


__all__ = ("State",)


class State:
    docs: OpenAPI | None
    default_encoder: Encoder
    default_decoder: Decoder
    formatter: ResponseFormatter

    def __init__(
        self,
        app: Application,
        *,
        lifespan: Lifespan = MISSING,
        docs: OpenAPI = MISSING,
        default_encoder: Encoder = MISSING,
        default_decoder: Decoder = MISSING,
        formatter: ResponseFormatter = MISSING,
    ):
        self.app = app
        self.router = Router(lifespan=lifespan)
        self.cached_api_docs: dict | None = None
        self.formatter = formatter or ResponseFormatter()

        self.groups: list[Group] = []
        self.docs = docs or None

        if msgspec is not None:
            self.default_decoder = default_decoder or msgspec.json.decode  # type: ignore
            self.default_encoder = default_encoder or msgspec.json.encode

    async def on_route_error(self, request: BaseRequest, error: Exception) -> Response:
        route = request.endpoint
        assert route is not None

        response = None
        if route._group is not None:
            response = await route._group.on_error(request, error)

        if response is None:
            response = await route._state.app.on_error(request, error)

        if response is None:
            return Response.internal()
        return response

    def get_docs(self) -> OpenAPI | None:
        if self.docs is None:
            return

        if self.docs.is_populated is False:
            for route in self.router.routes:
                if isinstance(route, Route):
                    self.docs.add_route(route)
            self.docs._add_models_from_queue()

        return self.docs
