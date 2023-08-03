from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .converters import builtin_converters
from .errors import ConverterAlreadyAdded
from .routing import Route, Router
from .utils import MISSING

if TYPE_CHECKING:
    from ._types import Converter, Lifespan
    from .app import Application
    from .converters import CustomConverter
    from .groups import Group
    from .openapi import OpenAPI
    from .requests import BaseRequest


__all__ = ("State",)


class State:
    docs: OpenAPI | None
    converters: dict[str, tuple[str, Converter]]

    def __init__(
        self,
        app: Application,
        lifespan: Lifespan = MISSING,
        docs: OpenAPI = MISSING,
        converters: list[CustomConverter] = MISSING,
    ):
        self.app = app
        self.router = Router(lifespan=lifespan)
        self.cached_api_docs: dict | None = None

        self.groups: list[Group] = []
        self.docs = docs or None

        self.converters = {}
        self.converters.update(builtin_converters)

        for converter in converters or []:
            self.add_converter(converter)

    def add_converter(self, converter: CustomConverter, /) -> None:
        if converter.name in self.converters:
            raise ConverterAlreadyAdded(converter.name)
        self.converters[converter.name] = converter.regex, converter.convert

    async def _handle_route_error(self, request: BaseRequest, error: Exception) -> None:
        route = request.endpoint
        assert route is not None
        if route._group is not None:
            await route._group.on_error(request, error)
        await route._state.app.on_error(request, error)

    def on_route_error(self, request: BaseRequest, error: Exception) -> None:
        asyncio.create_task(self._handle_route_error(request, error))

    def get_docs(self) -> OpenAPI | None:
        if self.docs is None:
            return

        if self.docs.is_populated is False:
            for route in self.router.routes:
                if isinstance(route, Route):
                    self.docs.add_route(route)
            self.docs._add_models_from_queue()

        return self.docs
