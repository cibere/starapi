from __future__ import annotations

import json
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Generic,
    Literal,
    Sequence,
    TypeVar,
)
from urllib.parse import parse_qs

from starlette.datastructures import FormData
from starlette.formparsers import FormParser, MultiPartException, MultiPartParser
from starlette.requests import Request as _R
from starlette.requests import cookie_parser
from starlette.types import Receive, Scope, Send
from yarl import URL

from starapi.errors import ClientDisconnect, HTTPException

from .utils import cached_coro, cached_gen, cached_property

try:
    from multipart.multipart import parse_options_header
except ModuleNotFoundError:  # pragma: nocover
    parse_options_header = None

if TYPE_CHECKING:
    from .app import Application
    from .routing import Route

    AppT = TypeVar("AppT", bound=Application)
else:
    AppT = TypeVar("AppT")

__all__ = ("Request",)


class Address:
    def __init__(self, data: Sequence):
        self.host: str = data[0]
        self.port: int = data[1]


class Request(Generic[AppT]):
    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self._scope = scope
        self._receive = receive
        self._send = send

        self._stream_consumed = False

    @property
    def app(self) -> AppT:
        return self._scope["app"]

    @property
    def endpoint(self) -> Route:
        return self._scope["endpoint"]

    @property
    def scheme(self) -> Literal["http", "https"]:
        return self._scope["schema"]

    @property
    def http_version(self) -> int:
        return self._scope["http_version"]

    @property
    def method(self) -> str:
        return self._scope["method"]

    @property
    def path_params(self) -> dict[str, Any]:
        return self._scope.get("path_params", {})

    @property
    def is_disconnected(self) -> bool:
        return self._is_disconnected

    @cached_property
    def url(self) -> URL:
        scheme = self._scope.get("scheme", "http")
        server = self._scope.get("server", None)
        path = self._scope.get("root_path", "") + self._scope["path"]
        query_string = self._scope.get("query_string", b"")

        host_header = None
        for key, value in self._scope["headers"]:
            if key == b"host":
                host_header = value.decode("latin-1")
                break

        if host_header is not None:
            url = f"{scheme}://{host_header}{path}"
        elif server is None:
            url = path
        else:
            host, port = server
            default_port = {"http": 80, "https": 443, "ws": 80, "wss": 443}[scheme]
            if port == default_port:
                url = f"{scheme}://{host}{path}"
            else:
                url = f"{scheme}://{host}:{port}{path}"

        if query_string:
            url += "?" + query_string.decode()
        return URL(url)

    @cached_property
    def base_url(self) -> URL:
        return self.url.with_path("/").with_query("")

    @cached_property
    def query_params(self) -> dict[str, list[str]] | None:
        return (
            parse_qs(self._scope["query_string"].decode())
            if self._scope["query_string"]
            else None
        )

    @cached_property
    def cookies(self) -> dict[str, str]:
        cookies = {}
        cookie_header = self.headers.get("cookie")

        if cookie_header:
            cookies = cookie_parser(cookie_header)
        return cookies

    @cached_property
    def client(self) -> Address | None:
        if data := self._scope.get("client"):
            return Address(data)

    @cached_property
    def headers(self) -> dict[str, str]:
        return {name.decode(): value.decode() for name, value in self._scope["headers"]}

    @cached_gen
    async def stream(self) -> AsyncGenerator[bytes, None]:
        if self._stream_consumed:
            raise RuntimeError("Stream consumed")
        while not self._stream_consumed:
            message = await self._receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                if not message.get("more_body", False):
                    self._stream_consumed = True
                if body:
                    yield body
            elif message["type"] == "http.disconnect":
                self._is_disconnected = True
                raise ClientDisconnect()
        yield b""

    @cached_coro
    async def body(self) -> bytes:
        chunks = []
        async for chunk in self.stream():
            chunks.append(chunk)
        return b"".join(chunks)

    @cached_coro
    async def json(self) -> dict | list:
        return json.loads(await self.body())

    @cached_coro
    async def form(
        self,
        *,
        max_files: int | float = 1000,
        max_fields: int | float = 1000,
    ) -> FormData:
        assert (
            parse_options_header is not None
        ), "The `python-multipart` library must be installed to use form parsing."
        content_type_header = self.headers.get("Content-Type")
        content_type: bytes
        content_type, _ = parse_options_header(content_type_header)
        if content_type == b"multipart/form-data":
            try:
                multipart_parser = MultiPartParser(
                    self.headers,  # type: ignore
                    self.stream(),
                    max_files=max_files,
                    max_fields=max_fields,
                )
                return await multipart_parser.parse()
            except MultiPartException as exc:
                if "app" in self._scope:
                    raise HTTPException(status_code=400, detail=exc.message)
                raise exc
        elif content_type == b"application/x-www-form-urlencoded":
            form_parser = FormParser(self.headers, self.stream())  # type: ignore
            return await form_parser.parse()
        else:
            return FormData()

    async def close(self) -> None:
        cache = getattr(self, "__cached_properties", {})
        form = cache.get("form", None)
        if form:
            await cache["form"].close()
