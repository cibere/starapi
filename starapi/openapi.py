from __future__ import annotations

import json
from typing import TYPE_CHECKING, Type

from .utils import MISSING

try:
    import msgspec
    import msgspec._json_schema
except ImportError:
    msgspec = MISSING

if TYPE_CHECKING:
    from msgspec import Struct

    from .parameters import Parameter
    from .routing import Route

__all__ = ("OpenAPI", "Contact")


class Contact:
    def __init__(self, name: str, email: str, url: str) -> None:
        self.name = name
        self.email = email
        self.url = url

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "email": self.email,
            "url": self.url,
        }


class OpenAPI:
    def __init__(
        self,
        *,
        title: str,
        version: str,
        summary: str = MISSING,
        description: str = MISSING,
        TOS_url: str = MISSING,
        license: str = MISSING,
        contact: Contact = MISSING,
        external_docs_link: str = MISSING,
    ) -> None:
        if msgspec is MISSING:
            raise RuntimeError("'msgspec' must be installed for openapi doc generation")

        self._current: dict = {
            "info": {},
            "openapi": "3.1.0",
            "paths": {},
            "components": {"schemas": {}},
        }

        self.title = title
        self.version = version
        self.summary = summary or None
        self.description = description or None
        self.TOS_url = TOS_url or None
        self.license = license or None
        self.external_docs_link = external_docs_link or None
        self.contact = contact or None

        self._objects_queue: list[Type[Struct]] = []
        self._status: bool = False

    @property
    def contact(self) -> Contact | None:
        return self._contact

    @contact.setter
    def contact(self, new: Contact | None):
        self._contact = new

        if new:
            self._current["info"]["contact"] = new.to_dict()

    @property
    def description(self) -> str | None:
        return self._description

    @description.setter
    def description(self, new: str | None):
        self._description = new
        self._current["info"]["description"] = new

    @property
    def TOS_url(self) -> str | None:
        return self._TOS_url

    @TOS_url.setter
    def TOS_url(self, new: str | None):
        self._TOS_url = new
        self._current["info"]["termsOfService"] = new

    @property
    def license(self) -> str | None:
        return self._license

    @license.setter
    def license(self, new: str | None):
        self._license = new

        if new:
            self._current["info"]["license"] = {
                "name": new,
                "identifier": new.replace(" ", "-"),
            }

    @property
    def summary(self) -> str | None:
        return self._summary

    @summary.setter
    def summary(self, new: str | None):
        self._summary = new
        self._current["info"]["summary"] = new

    @property
    def is_populated(self) -> bool:
        return self._status

    @property
    def current(self) -> dict:
        return self._current

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, new: str):
        self._title = new
        self._current["info"]["title"] = new

    @property
    def version(self) -> str:
        return self._version

    @version.setter
    def version(self, new: str):
        self._version = new
        self._current["info"]["version"] = new

    def _convert_to_openapi_type(self, python_type: Type) -> dict:
        translator = msgspec.inspect._Translator([python_type])
        t, args, _ = msgspec.inspect._origin_args_metadata(python_type)
        msgspec_type = translator._translate_inner(t, args)
        return msgspec._json_schema._to_schema(
            msgspec_type, {}, "#/$defs/{name}", False
        )

    def generate_param_spec(self, param: Parameter) -> dict:
        schema = {"title": param.name.title()}
        schema.update(self._convert_to_openapi_type(param.annotation))
        return {
            "required": param.required,
            "name": param.name,
            "in": param.where,
            "deprecated": param.deprecated,
            "schema": schema,
        }

    def generate_route_spec(self, route: Route) -> tuple[list[Type[Struct]], dict]:
        objects: list[Type[Struct]] = []

        def conv(model: Type[Struct]) -> dict:
            objects.append(model)
            return {
                "description": model.__doc__ or "",
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{model.__name__}"}
                    }
                },
            }

        data = {
            "description": route.description,
            "summary": "",
            "responses": {code: conv(m) for code, m in route._responses.items()},
            "tags": route._tags,
            "deprecated": route.deprecated,
            "parameters": [self.generate_param_spec(p) for p in route._parameters],
            "operationId": f"{route.clean_path}",
        }
        if route._payload is not None:
            data["requestBody"] = conv(route._payload)

        return objects, data

    def _add_models_from_queue(self) -> None:
        self._current["components"]["schemas"] = msgspec.json.schema_components(
            self._objects_queue
        )[1]

    def add_route(self, route: Route) -> None:
        if route.hidden is True:
            return

        paths = self._current["paths"]

        if route.clean_path not in paths:
            paths[route.clean_path] = {}

        models, route_data = self.generate_route_spec(route)

        self._objects_queue.extend(models)
        for method in route.methods:
            route_data["operationId"] = f"[{method}]_{route.clean_path}"
            paths[route.clean_path][method.lower()] = route_data

    def save(self, fp: str, *, indent: int = 4) -> None:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(self.current, f, indent=indent)

    def __repr__(self) -> str:
        x = [
            f"{n}={getattr(self, n)!r}"
            for n in (
                "title",
                "version",
                "summary",
                "description",
                "TOS_url",
                "license",
                "external_docs_link",
                "contact",
            )
        ]
        return f"<{self.__class__.__name__} {' '.join(x)} >"
