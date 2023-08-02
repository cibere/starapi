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
from yarl import URL

from starapi.enums import WSState

from .errors import ClientDisconnect, HTTPException
from .utils import (
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
    from ._types import Message, Receive, Scope, Send
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


class BaseRequest(Generic[AppT]):
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


class WebSocket(BaseRequest):
    def __init__(self, scope: Scope, receive: Receive, send: Send) -> None:
        super().__init__(scope, receive, send)

        self.client_state = WSState.connecting
        self.application_state = WSState.connecting

    async def receive(self) -> Message:
        match self.client_state:
            case WSState.connecting:
                msg = await self._receive()
                if msg["type"] != "websocket.connect":
                    raise RuntimeError(
                        f"Expected ASGI message type 'websocket.connect', received {msg['type']!r} instead."
                    )
                self.client_state = WSState.connected
                return msg
            case WSState.connected:
                msg = await self._receive()
                if msg["type"] == "websocket.disconnect":
                    self.client_state = WSState.disconnected
                elif msg["type"] not in ("websocket.disconnect", "websocket.receive"):
                    raise RuntimeError(
                        f"Expected ASGI message type 'websocket.disconnect' or 'websocket.receive', received {msg['type']!r} instead."
                    )
                return msg
            case other:
                raise RuntimeError("Disconnect message has already been received")

    async def send(self, message: Message) -> None:
        if self.application_state == WebSocketState.CONNECTING:
            message_type = message["type"]
            if message_type not in {"websocket.accept", "websocket.close"}:
                raise RuntimeError(
                    'Expected ASGI message "websocket.accept" or '
                    f'"websocket.close", but got {message_type!r}'
                )
            if message_type == "websocket.close":
                self.application_state = WebSocketState.DISCONNECTED
            else:
                self.application_state = WebSocketState.CONNECTED
            await self._send(message)
        elif self.application_state == WebSocketState.CONNECTED:
            message_type = message["type"]
            if message_type not in {"websocket.send", "websocket.close"}:
                raise RuntimeError(
                    'Expected ASGI message "websocket.send" or "websocket.close", '
                    f"but got {message_type!r}"
                )
            if message_type == "websocket.close":
                self.application_state = WebSocketState.DISCONNECTED
            await self._send(message)
        else:
            raise RuntimeError('Cannot call "send" once a close message has been sent.')

    async def accept(
        self,
        subprotocol: typing.Optional[str] = None,
        headers: typing.Optional[typing.Iterable[typing.Tuple[bytes, bytes]]] = None,
    ) -> None:
        headers = headers or []

        if self.client_state == WebSocketState.CONNECTING:
            # If we haven't yet seen the 'connect' message, then wait for it first.
            await self.receive()
        await self.send(
            {"type": "websocket.accept", "subprotocol": subprotocol, "headers": headers}
        )

    def _raise_on_disconnect(self, message: Message) -> None:
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(message["code"])

    async def receive_text(self) -> str:
        if self.application_state != WebSocketState.CONNECTED:
            raise RuntimeError(
                'WebSocket is not connected. Need to call "accept" first.'
            )
        message = await self.receive()
        self._raise_on_disconnect(message)
        return typing.cast(str, message["text"])

    async def receive_bytes(self) -> bytes:
        if self.application_state != WebSocketState.CONNECTED:
            raise RuntimeError(
                'WebSocket is not connected. Need to call "accept" first.'
            )
        message = await self.receive()
        self._raise_on_disconnect(message)
        return typing.cast(bytes, message["bytes"])

    async def receive_json(self, mode: str = "text") -> typing.Any:
        if mode not in {"text", "binary"}:
            raise RuntimeError('The "mode" argument should be "text" or "binary".')
        if self.application_state != WebSocketState.CONNECTED:
            raise RuntimeError(
                'WebSocket is not connected. Need to call "accept" first.'
            )
        message = await self.receive()
        self._raise_on_disconnect(message)

        if mode == "text":
            text = message["text"]
        else:
            text = message["bytes"].decode("utf-8")
        return json.loads(text)

    async def iter_text(self) -> typing.AsyncIterator[str]:
        try:
            while True:
                yield await self.receive_text()
        except WebSocketDisconnect:
            pass

    async def iter_bytes(self) -> typing.AsyncIterator[bytes]:
        try:
            while True:
                yield await self.receive_bytes()
        except WebSocketDisconnect:
            pass

    async def iter_json(self) -> typing.AsyncIterator[typing.Any]:
        try:
            while True:
                yield await self.receive_json()
        except WebSocketDisconnect:
            pass

    async def send_text(self, data: str) -> None:
        await self.send({"type": "websocket.send", "text": data})

    async def send_bytes(self, data: bytes) -> None:
        await self.send({"type": "websocket.send", "bytes": data})

    async def send_json(self, data: typing.Any, mode: str = "text") -> None:
        if mode not in {"text", "binary"}:
            raise RuntimeError('The "mode" argument should be "text" or "binary".')
        text = json.dumps(data, separators=(",", ":"))
        if mode == "text":
            await self.send({"type": "websocket.send", "text": text})
        else:
            await self.send({"type": "websocket.send", "bytes": text.encode("utf-8")})

    async def close(
        self, code: int = 1000, reason: typing.Optional[str] = None
    ) -> None:
        await self.send(
            {"type": "websocket.close", "code": code, "reason": reason or ""}
        )


class Request(BaseRequest):
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
