from __future__ import annotations

import asyncio
from re import L
from typing import TYPE_CHECKING, Type

import msgspec

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

    def msgspec_inspect_type_to_python_type(self, type: Type) -> Type:
        python_type = type

        _msgspec_type = getattr(type, "__class__", None)
        match _msgspec_type:
            case msgspec.inspect.StrType:
                python_type = str
            case msgspec.inspect.NoneType:
                python_type = None
            case msgspec.inspect.IntType:
                python_type = int
            case msgspec.inspect.FloatType:
                python_type = float
            case msgspec.inspect.ListType:
                python_type = list[
                    self.msgspec_inspect_type_to_python_type(type.item_type)  # type: ignore
                ]

        return python_type

    def find_openapi_spec_type(self, python_type: Type, items_dict: dict) -> str:
        types: dict[Type, str] = {
            int: "number",
            float: "double",
            bool: "boolean",
            str: "string",
            list: "array",
            None: "null",
        }

        python_type = self.msgspec_inspect_type_to_python_type(python_type)

        typ = None
        try:
            if issubclass(python_type, msgspec.Struct):
                typ = "object"
                items_dict.update(self.model_to_component_object(python_type))
        except TypeError:
            pass

        if typ is None:
            typ = types[getattr(python_type, "__origin__", python_type)]

        if typ == "array":
            child_type = getattr(python_type, "__args__", None)
            if child_type is not None:
                childs_items_dict = {}
                items_dict["type"] = self.find_openapi_spec_type(
                    child_type[0], childs_items_dict
                )
                if childs_items_dict != {}:
                    items_dict["items"] = childs_items_dict

        return typ

    def model_to_component_object(self, model: Type[Struct]) -> dict:
        data = {
            "title": model.__name__,
            "type": "object",
            "required": [],
            "properties": {},
        }

        struct_info = msgspec.inspect.type_info(model)
        assert isinstance(struct_info, msgspec.inspect.StructType)

        for field in struct_info.fields:
            field_data = {}
            if field.required:
                data["required"].append(field.name)

            items_dict = {}
            field_data["type"] = self.find_openapi_spec_type(field.type, items_dict)
            if items_dict != {}:
                field_data["items"] = items_dict

            data["properties"][field.name] = field_data

        return data

    def construct_openapi_file(self, *, title: str, version: str) -> dict:
        data = {
            "openapi": "3.0.2",
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

        for model in objects:
            data["components"]["schemas"][
                model.__name__
            ] = self.model_to_component_object(model)

        self.cached_api_docs = data
        return data
