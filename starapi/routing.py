from __future__ import annotations

import json
import re
import traceback
from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeAlias

from ._types import (
    Connection,
    Converter,
    GroupT,
    Lifespan,
    Receive,
    Scope,
    Send,
    WSMessage,
)
from .converters import builtin_converters
from .enums import Match, WSCodes, WSMessageType
from .requests import WebSocket
from .responses import Response
from .utils import MISSING, set_property

if TYPE_CHECKING:
    from .state import State


__all__ = ("route", "Route", "WebSocketRoute")

RouteType: TypeAlias = "Route | WebSocketRoute"
ResponseType: TypeAlias = Coroutine[Any, Any, Response]
HTTPRouteCallback: TypeAlias = Callable[..., ResponseType]
WSRouteCallback: TypeAlias = Callable[[WebSocket], Coroutine[Any, Any, None]]

RouteDecoCallbackType: TypeAlias = Callable[
    [HTTPRouteCallback],
    RouteType,
]

PARAM_REGEX = re.compile(
    r"{(?P<name>[a-zA-Z_][a-zA-Z0-9_]*):(?P<type>[a-zA-Z_-][a-zA-Z0-9_-]*)?}"
)


class _DefaultLifespan:
    def __init__(self, app) -> None:
        ...

    async def __aenter__(self) -> None:
        ...

    async def __aexit__(self, *exc_info: object) -> None:
        ...


class BaseRoute(ABC, Generic[GroupT]):
    _group: GroupT | None
    _state: State
    _path_data: list[tuple[str, Converter, str | None]]

    def __init__(self, *, path: str, prefix: bool) -> None:
        self.path = path
        self._add_prefix: bool = prefix

        self._group = None
        self._resolved = None

    @abstractmethod
    def _match(self, scope: Scope) -> tuple[Match, Scope]:
        raise NotImplementedError()

    @property
    def group(self) -> GroupT | None:
        return self._group

    @property
    def path(self) -> str:
        return self._path

    @path.setter
    def path(self, new_path: str):
        self._path = new_path
        self._compile_path()

    @property
    def add_prefix(self) -> bool:
        return self._add_prefix

    def _compile_path(self) -> None:
        path: list[tuple[str, Converter, str | None]] = []

        for endpoint in self.path.split("/"):
            convertor = None
            name = None
            regex = re.escape(endpoint)

            if data := PARAM_REGEX.fullmatch(endpoint):
                regex, convertor = builtin_converters.get(data["type"], (regex, None))
                name = data["name"]

            convertor = convertor or str
            path.append((regex, convertor, name))

        path.append(("", str, None))

        self._path_data = path


class Route(BaseRoute):
    def __init__(
        self,
        *,
        path: str,
        callback: HTTPRouteCallback,
        methods: list[str],
        prefix: bool = MISSING,
    ) -> None:
        self._callback: HTTPRouteCallback = callback
        super().__init__(path=path, prefix=prefix)
        self._methods = methods

    @property
    def callback(self) -> HTTPRouteCallback:
        return self._callback

    @property
    def methods(self) -> list[str]:
        return self._methods

    def _match(self, request: Connection) -> bool:
        if request._type != "http":
            return False

        client_path = request._scope["path"].split("/")

        if len(client_path) != len(self._path_data):
            return False

        params = {}

        for client_endpoint, server_endpoint in zip(client_path, self._path_data):
            regex, convertor, name = server_endpoint
            if not re.fullmatch(regex, client_endpoint):
                return False
            try:
                params[name] = convertor(client_endpoint)
            except ValueError:
                return False
        request._scope["path_params"] = params
        return True

    async def __call__(self, request: Connection) -> None:
        assert request._type == "http"

        if request.method not in self.methods:
            return await Response.method_not_allowed()(request)

        args = []

        response = None
        if self._group is not None:
            args.append(self._group)

            try:
                response = await self._group.group_check(request)
            except Exception as e:
                self._state.on_route_error(request, e)
                response = Response.internal()

        if response is None:
            args.append(request)

            try:
                response = await self._callback(*args)
            except Exception as e:
                self._state.on_route_error(request, e)
                response = Response.internal()

        await response(request)


class WebSocketRoute(BaseRoute):
    encoding: Literal["text", "json", "bytes"] = "text"

    def __init__(
        self,
        *,
        path: str,
        prefix: bool = MISSING,
    ) -> None:
        super().__init__(path=path, prefix=prefix)

    def _match(self, ws: Connection) -> bool:
        if ws._type != "websocket":
            return False

        client_path = ws._scope["path"].split("/")

        if len(client_path) != len(self._path_data):
            return False

        params = {}

        for client_endpoint, server_endpoint in zip(client_path, self._path_data):
            regex, convertor, name = server_endpoint
            if not re.fullmatch(regex, client_endpoint):
                return False
            try:
                params[name] = convertor(client_endpoint)
            except ValueError:
                return False
        ws._scope["path_params"] = params
        return True

    async def __call__(self, ws: Connection) -> None:
        assert ws._type == "websocket"

        try:
            await self.on_connect(ws)
        except Exception as e:
            self._state.on_route_error(ws, e)
            await self.on_disconnect(ws, WSCodes.INTERNAL_ERROR)

        if getattr(self.on_receive, "__starapi_original__", False) is True:
            return

        close_code = WSCodes.NORMAL_CLOSURE
        try:
            while 1:
                msg = await ws.receive()
                match WSMessageType(msg["type"]):
                    case WSMessageType.receive:
                        await self._dispatch_receive(ws, msg)
                    case WSMessageType.disconnect:
                        code = msg.get("code", None)
                        close_code = (
                            WSCodes(code)
                            if code is not None
                            else WSCodes.NORMAL_CLOSURE
                        )
                        break
        except Exception as e:
            self._state.on_route_error(ws, e)
            close_code = WSCodes.INTERNAL_ERROR
        finally:
            await self.on_disconnect(ws, close_code)

    async def _dispatch_receive(self, ws: WebSocket, msg: WSMessage) -> None:
        match self.encoding:
            case "bytes":
                data = msg.get("bytes", None)
            case "text":
                data = msg.get("text", None)
            case "json":
                data = msg.get("text", msg.get("bytes"))
                if data is not None:
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        await ws.close(WSCodes.UNSUPPORTED_DATA)
                        raise RuntimeError("Malformed JSON data received")

        if data is None:
            await ws.close(code=WSCodes.UNSUPPORTED_DATA)

            if "text" in msg:
                x = "text"
            elif "bytes" in msg:
                x = "bytes"
            else:
                x = "nothing"
            raise RuntimeError(f"Expected {self.encoding} ws message, received {x}.")
        await self.on_receive(ws, data)  # type: ignore

    async def on_connect(self, ws: WebSocket) -> None:
        await ws.accept()

    async def on_disconnect(self, ws: WebSocket, code: WSCodes) -> None:
        ...

    @set_property("__starapi_original__", True)
    async def on_receive(self, ws: WebSocket, data: Any) -> None:
        ...


class RouteSelector:
    def __call__(
        self,
        path: str,
        /,
        *,
        methods: list[str],
        prefix: bool = ...,
    ) -> RouteDecoCallbackType:
        def decorator(callback: HTTPRouteCallback) -> RouteType:
            return Route(path=path, callback=callback, methods=methods, prefix=prefix)

        return decorator

    def get(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["GET"], prefix=prefix)

    def post(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["POST"], prefix=prefix)

    def put(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["PUT"], prefix=prefix)

    def delete(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["DELETE"], prefix=prefix)

    def patch(self, path: str, /, *, prefix: bool = True) -> RouteDecoCallbackType:
        return self.__call__(path, methods=["PATCH"], prefix=prefix)


route = RouteSelector()


class Router:
    routes: list[RouteType]
    lifespan_context: Lifespan

    def __init__(self, *, lifespan: Lifespan = MISSING) -> None:
        self.routes = []

        self.lifespan_context = lifespan or _DefaultLifespan

    async def lifespan(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Handle ASGI lifespan messages, which allows us to manage application
        startup and shutdown events.
        """
        started = False
        await receive()
        try:
            async with self.lifespan_context(scope.get("app")) as maybe_state:
                if maybe_state is not None:
                    if "state" not in scope:
                        raise RuntimeError(
                            'The server does not support "state" in the lifespan scope.'
                        )
                    scope["state"].update(maybe_state)
                await send({"type": "lifespan.startup.complete"})
                started = True
                await receive()
        except Exception:
            exc_text = traceback.format_exc()
            if started:
                await send({"type": "lifespan.shutdown.failed", "message": exc_text})
            else:
                await send({"type": "lifespan.startup.failed", "message": exc_text})
            raise
        else:
            await send({"type": "lifespan.shutdown.complete"})

    async def __call__(self, request: Connection) -> None:
        assert request._scope["type"] in ("http", "websocket")

        if not request._scope["path"].endswith("/"):
            request._scope["path"] += "/"

        for route in self.routes:
            if route._match(request) is True:
                return await route(request)

        if isinstance(request, WebSocket):
            await request.send(
                {
                    "type": "websocket.close",
                    "code": WSCodes.NORMAL_CLOSURE.value,
                    "reason": "",
                }
            )
        else:
            await Response.not_found()(request)
