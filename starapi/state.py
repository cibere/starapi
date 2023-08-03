from __future__ import annotations

import asyncio
from re import L
from typing import TYPE_CHECKING, Generator, Iterable, Iterator, Type

import msgspec
import msgspec._json_schema

from .routing import Router, WebSocketRoute
from .utils import MISSING

if TYPE_CHECKING:
    from msgspec import Struct

    from ._types import Lifespan
    from .app import Application
    from .groups import Group
    from .requests import BaseRequest


__all__ = ("State",)


class State:
    def __init__(self, app: Application, lifespan: Lifespan = MISSING):
        self.app = app
        self.router = Router(lifespan=lifespan)
        self.cached_api_docs: dict | None = None

        self.groups: list[Group] = []

    async def _handle_route_error(self, request: BaseRequest, error: Exception) -> None:
        route = request.endpoint
        assert route is not None
        if route._group is not None:
            await route._group.on_error(request, error)
        await route._state.app.on_error(request, error)

    def on_route_error(self, request: BaseRequest, error: Exception) -> None:
        asyncio.create_task(self._handle_route_error(request, error))

    def convert_to_openapi_type(self, python_type: Type) -> dict:
        translator = msgspec.inspect._Translator([python_type])
        t, args, _ = msgspec.inspect._origin_args_metadata(python_type)
        msgspec_type = translator._translate_inner(t, args)
        return msgspec._json_schema._to_schema(
            msgspec_type, {}, "#/$defs/{name}", False
        )

    def construct_openapi_file(self, *, title: str, version: str) -> dict:
        data = {
            "openapi": "3.1.0",
            "info": {"title": title, "version": version},
            "paths": {},
            "components": {"schemas": {}},
        }
        objects: list[Type[Struct]] = []

        for route in self.router.routes:
            if isinstance(route, WebSocketRoute):
                continue  # ws isnt supported yet, focus is http
            if route.hidden is True:
                continue

            if route.path not in data["paths"]:
                data["paths"][route.path] = {}

            models, route_data = route._generate_openapi_spec("")

            objects.extend(models)
            for method in route.methods:
                route_data["operationId"] = f"[{method}]_{route.path}"
                data["paths"][route.path][method.lower()] = route_data

        data["components"]["schemas"] = msgspec.json.schema_components(objects)[1]

        self.cached_api_docs = data

        with open("openapi_schema.json", "w", encoding="utf-8") as f:
            import json

            json.dump(self.cached_api_docs, f, indent=4)

        return data
