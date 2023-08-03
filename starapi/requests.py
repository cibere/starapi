from __future__ import annotations

import json
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Callable,
    Generic,
    Literal,
    Self,
    Sequence,
    TypeVar,
    overload,
)
from urllib.parse import parse_qs

from starlette.datastructures import FormData
from starlette.formparsers import FormParser, MultiPartException, MultiPartParser
from yarl import URL

from starapi import app

from .enums import WSCodes, WSMessageType, WSState
from .errors import (
    ClientDisconnect,
    HTTPException,
    UnexpectedASGIMessageType,
    WebSocketDisconnect,
    WebSocketDisconnected,
)
from .utils import (
    MISSING,
    AsyncIteratorProxy,
    cached_coro,
    cached_gen,
    cached_property,
    parse_cookies,
    url_from_scope,
)

try:
    from multipart.multipart import parse_options_header
except ModuleNotFoundError:
    parse_options_header = None

if TYPE_CHECKING:
    from typing_extensions import TypeVar

    from ._types import Receive, Scope, Send, WSMessage
    from .app import Application
    from .routing import Route

    AppT = TypeVar("AppT", bound=Application, default=Application)
    FuncT = TypeVar("FuncT", bound=Callable)
else:
    AppT = TypeVar("AppT")

__all__ = ("Request", "WebSocket")


class Address:
    def __init__(self, data: Sequence):
        self.host: str = data[0]
        self.port: int = data[1]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} host={self.host!r} port={self.port!r}>"


def _ws_must_be_connected(func: FuncT) -> FuncT:
    def decorated(*args, **kwargs):
        ws: WebSocket = args[0]
        if ws.application_state != WSState.connected:
            raise WebSocketDisconnected()
        return func(*args, **kwargs)

    return decorated  # type: ignore


class BaseRequest(Generic[AppT]):
    _type: str

    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self._scope = scope
        self._receive = receive
        self._send = send
        self._type = scope["type"]

        self._stream_consumed = False

    @property
    def app(self) -> AppT:
        return self._scope["app"]

    @property
    def endpoint(self) -> Route:
        return self._scope["endpoint"]

    @property
    def schema(self) -> Literal["http", "https"]:
        return self._scope["schema"]

    @property
    def http_version(self) -> int:
        return self._scope["http_version"]

    @property
    def path_params(self) -> dict[str, Any]:
        return self._scope.get("path_params", {})

    @cached_property
    def url(self) -> URL:
        return url_from_scope(self._scope)

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
            cookies = parse_cookies(cookie_header)
        return cookies

    @cached_property
    def client(self) -> Address | None:
        if data := self._scope.get("client"):
            return Address(data)

    @cached_property
    def headers(self) -> dict[str, str]:
        return {name.decode(): value.decode() for name, value in self._scope["headers"]}

    def __repr__(self, extras: list = MISSING) -> str:
        extras = extras or []
        extras.extend(
            (
                "app",
                "endpoint",
                "schema",
            )
        )
        x = [f"{n}={getattr(self, n)!r}" for n in extras]
        return f"<{self.__class__.__name__} {' '.join(x)} >"


class WebSocket(BaseRequest):
    _type: Literal["websocket"]

    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        super().__init__(scope, receive, send)

        self.client_state = WSState.connecting
        self.application_state = WSState.connecting

    async def receive(self) -> WSMessage:
        match self.client_state:
            case WSState.connecting:
                msg = await self._receive()
                if msg["type"] != WSMessageType.connect.value:
                    raise UnexpectedASGIMessageType(WSMessageType.connect, msg["type"])
                self.client_state = WSState.connected
                return msg
            case WSState.connected:
                msg = await self._receive()
                typ = WSMessageType(msg["type"])
                if typ == WSMessageType.disconnect:
                    self.client_state = WSState.disconnected
                elif typ not in (
                    WSMessageType.disconnect,
                    WSMessageType.receive,
                ):
                    raise UnexpectedASGIMessageType(
                        [WSMessageType.disconnect, WSMessageType.receive], typ.value
                    )
                return msg  # type: ignore
            case other:
                raise RuntimeError("Disconnect message has already been received")

    async def send(self, msg: WSMessage) -> None:
        match self.application_state:
            case WSState.connecting:
                match WSMessageType(msg["type"]):
                    case WSMessageType.accept:
                        self.application_state = WSState.connected
                    case WSMessageType.close:
                        self.application_state = WSState.disconnected
                    case other:
                        raise UnexpectedASGIMessageType(
                            [WSMessageType.close, WSMessageType.accept], msg["type"]
                        )
                await self._send(msg)
            case WSState.connected:
                match WSMessageType(msg["type"]):
                    case WSMessageType.close:
                        self.application_state = WSState.disconnected
                    case WSMessageType.send:
                        pass
                    case other:
                        raise UnexpectedASGIMessageType(
                            [WSMessageType.close, WSMessageType.send], other.value
                        )
                await self._send(msg)
            case other:
                raise RuntimeError("Websocket has already been closed")

    async def accept(
        self,
        subprotocol: str | None = None,
        headers: dict[str, str] = MISSING,
    ) -> None:
        if headers is MISSING:
            headers = {}
        raw_headers: list[tuple[bytes, bytes]] = [
            (k.encode(), v.encode()) for k, v in headers.items()
        ]

        if self.client_state == WSState.connecting:
            await self.receive()

        await self.send(
            {
                "type": "websocket.accept",
                "subprotocol": subprotocol,
                "headers": raw_headers,
            }
        )

    def _raise_on_disconnect(self, message: WSMessage) -> None:
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(message["code"])

    @_ws_must_be_connected
    async def receive_text(self) -> str:
        while 1:
            msg = await self.receive()
            assert msg["type"] == "websocket.send"
            self._raise_on_disconnect(msg)
            try:
                return msg["text"]  # type: ignore
            except KeyError:
                ...
        raise RuntimeError("How did we get here")

    @_ws_must_be_connected
    async def receive_bytes(self) -> bytes:
        while 1:
            msg = await self.receive()
            assert msg["type"] == "websocket.send"
            self._raise_on_disconnect(msg)
            try:
                return msg["bytes"]  # type: ignore
            except KeyError:
                ...
        raise RuntimeError("How did we get here")

    @_ws_must_be_connected
    async def receive_json(self) -> dict | list:
        while 1:
            msg = await self.receive()
            assert msg["type"] == "websocket.send"
            self._raise_on_disconnect(msg)
            try:
                return json.loads(msg["text"])  # type: ignore
            except KeyError:
                ...
        raise RuntimeError("How did we get here")

    @overload
    async def iter(self, encoding: Literal["bytes"]) -> AsyncIteratorProxy[bytes]:
        ...

    @overload
    async def iter(self, encoding: Literal["text"]) -> AsyncIteratorProxy[str]:
        ...

    @overload
    async def iter(self, encoding: Literal["json"]) -> AsyncIteratorProxy[dict | list]:
        ...

    async def iter(
        self, encoding: Literal["bytes", "text", "json"]
    ) -> AsyncIteratorProxy:
        match encoding:
            case "bytes":
                coro = self.receive_bytes
            case "text":
                coro = self.receive_text
            case "json":
                coro = self.receive_json
            case other:
                raise ValueError(
                    f"Expected 'bytes', 'text', or 'json' for encoding. Received {other!r} instead"
                )
        return AsyncIteratorProxy(coro)

    async def send_text(self, content: str) -> None:
        await self.send({"type": "websocket.send", "text": content})

    async def send_bytes(self, content: bytes) -> None:
        await self.send({"type": "websocket.send", "bytes": content})

    async def send_json(self, data: list | dict) -> None:
        text = json.dumps(data, separators=(",", ":"))
        await self.send({"type": "websocket.send", "text": text})

    async def close(self, code: WSCodes = MISSING, reason: str = MISSING) -> None:
        await self.send(
            {
                "type": "websocket.close",
                "code": (code or WSCodes.NORMAL_CLOSURE).value,
                "reason": reason or "",
            }
        )


class Request(BaseRequest):
    _type: Literal["http"]

    @property
    def is_disconnected(self) -> bool:
        return self._is_disconnected

    @property
    def method(self) -> str:
        return self._scope["method"]

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

    def __repr__(self) -> str:
        return super().__repr__(["method", "is_disconnected"])
