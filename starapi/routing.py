from __future__ import annotations

import inspect
import json
import re
import traceback
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, Generic, Literal, Type, TypeAlias, TypeVar, overload

from ._types import Connection, GroupT, Lifespan, Receive, Scope, Send, WSMessage
from .converters import Converter, builtin_converters
from .enums import WSCodes, WSMessageType
from .errors import ConverterEntryNotFound, ConverterNotFound, InvalidWebSocketRoute
from .parameters import Parameter, PathParameter
from .requests import WebSocket
from .responses import Response
from .utils import MISSING, mimmic, set_property

if TYPE_CHECKING:
    from msgspec import Struct

    from .state import State

    WSRouteT = TypeVar("WSRouteT", bound="WebSocketRoute")


__all__ = ("route", "Route", "WebSocketRoute")

RouteType: TypeAlias = "Route | WebSocketRoute"
ResponseType: TypeAlias = Coroutine[Any, Any, Response]
HTTPRouteCallback: TypeAlias = Callable[..., ResponseType]
WSRouteCallback: TypeAlias = (
    Callable[[WebSocket], Coroutine[Any, Any, None]] | Callable[[Any, WebSocket], Coroutine[Any, Any, None]]
)

RouteDecoCallbackType: TypeAlias = Callable[
    [HTTPRouteCallback],
    RouteType,
]

PATH_PARAM_REGEX = re.compile(r"{(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)}")


class _DefaultLifespan:
    def __init__(self, app) -> None:
        ...

    async def __aenter__(self) -> None:
        ...

    async def __aexit__(self, *exc_info: object) -> None:
        ...


class BaseRoute(Generic[GroupT]):
    _group: GroupT | None
    _state: State
    _path_data: list[tuple[str, tuple[Converter, str] | None]]
    description: str
    _parameters: list[Parameter]

    def __init__(self, *, path: str, prefix: bool) -> None:
        if not path.startswith("/"):
            raise ValueError(f"Route paths must start with '/'")

        self._path = path
        self._add_prefix: bool = prefix

        self._group = None
        self._resolved = None
        self._path_params_added: bool = False

    @property
    def group(self) -> GroupT | None:
        return self._group

    @property
    def path(self) -> str:
        return self._path

    @property
    def clean_path(self) -> str:
        x = []
        for regex, extra in self._path_data:
            if extra is None:
                x.append(regex)
            else:
                x.append(f"{{{extra[1]}}}")
        return "/".join(x)

    @property
    def add_prefix(self) -> bool:
        return self._add_prefix

    def _get_path_params(self, signature: inspect.Signature) -> dict[str, PathParameter]:
        params = {}
        skipped_conn: bool = False
        for name, arg in dict(signature.parameters).items():
            if name == "self":
                continue
            if skipped_conn is False:
                skipped_conn = True
                continue
            params[name] = PathParameter(required=True, name=name, converter=arg.annotation)
        if self._path_params_added is False:
            self._parameters.extend(params.values())
            self._path_params_added = True
        return params

    def _compile_path(self, signature: inspect.Signature) -> None:
        path: list[tuple[str, tuple[Converter, str] | None]] = []
        path_params = self._get_path_params(signature)

        for endpoint in self.path.split("/"):
            extra = None
            regex = re.escape(endpoint)

            if match := PATH_PARAM_REGEX.fullmatch(endpoint):
                name = match["name"]
                param = path_params.pop(name, None)
                if param is not None:
                    annotation = param.annotation
                    if not issubclass(annotation, Converter):
                        converter = builtin_converters.get(annotation, None)
                    else:
                        converter = annotation

                    if converter is None:
                        raise ConverterNotFound(
                            f"I found no converter for {annotation!r}. To impliment one yourself, have it override `starapi.Converter`, and override the `convert` method."
                        )
                    try:
                        converter = converter()
                    except TypeError as e:
                        if "missing 1 required positional argument" in str(
                            e
                        ) or "missing 1 required keyword-only argument" in str(e):
                            raise ConverterEntryNotFound(converter)
                        else:
                            raise
                    extra = converter, name
                    regex = converter.regex

            path.append((regex, extra))

        if path_params:
            raise RuntimeError(
                f"Unknown path parameters in '{self.path}': {', '.join(f'{param.name!r}' for param in path_params.values())}"
            )

        if path[-1][0] != "":
            path.append(("", None))

        self._path_data = path

    def _match(self, con: Connection) -> bool:
        client_path = con._scope["path"].split("/")

        if len(client_path) != len(self._path_data):
            return False

        params = {}

        for client_endpoint, server_endpoint in zip(client_path, self._path_data):
            regex, extra = server_endpoint
            if not re.fullmatch(regex, client_endpoint):
                return False
            if extra is not None:
                try:
                    params[extra[1]] = extra[0].convert(client_endpoint)
                except ValueError:
                    return False
        con._scope["path_params"] = params
        return True

    def __repr__(self, extras: list = MISSING) -> str:
        extras = extras or []
        extras.extend(
            (
                "path",
                "add_prefix",
            )
        )
        x = [f"{n}={getattr(self, n)!r}" for n in extras]
        return f"<{self.__class__.__name__} {' '.join(x)} >"


class Route(BaseRoute):
    callback: HTTPRouteCallback

    def __init__(
        self,
        path: str,
        *,
        methods: list[str] = MISSING,
        prefix: bool = MISSING,
        responses: dict[int, Type[Struct]] = MISSING,
        query_parameters: list[Parameter] = MISSING,
        cookies: list[Parameter] = MISSING,
        headers: list[Parameter] = MISSING,
        tags: list[str] = MISSING,
        payload: Type[Struct] = MISSING,
        deprecated: bool = False,
        hidden: bool = False,
    ) -> None:
        super().__init__(path=path, prefix=prefix)
        self._methods = methods or []
        if methods is MISSING:
            self._methods = ["GET", "HEAD"]

        self.hidden = hidden

        self._responses = responses or {}
        self._tags = tags or []
        self._payload: Type[Struct] | None = payload or None
        self.deprecated = deprecated

        self._parameters: list[Parameter] = []
        for where, params in [
            ("query", query_parameters),
            ("header", headers),
            ("cookie", cookies),
        ]:
            for param in params or []:
                param.where = where
                self._parameters.append(param)

    @property
    def description(self) -> str:
        return self.callback.__doc__ or ""

    @property
    def methods(self) -> list[str]:
        return self._methods

    def _match(self, request: Connection) -> bool:
        if request._type != "http":
            return False

        return super()._match(request)

    async def __call__(self, request: Connection) -> None:
        assert request._type == "http"

        if request.method not in self.methods:
            return await Response.method_not_allowed()(request)

        request._scope["endpoint"] = self

        args = []

        response = None
        if self._group is not None:
            args.append(self._group)

            try:
                response = await self._group.group_check(request)
            except Exception as e:
                response = await self._state.on_route_error(request, e)

        if response is None:
            args.append(request)

            try:
                response = await self.callback(*args, **request._scope["path_params"])
            except Exception as e:
                response = await self._state.on_route_error(request, e)

        await response(request)

    def __repr__(self) -> str:
        return super().__repr__(["methods", "hidden"])


class WebSocketRoute(BaseRoute):
    encoding: Literal["text", "json", "bytes"] = "text"
    _init_subclass_kwarg_data: tuple[str, bool]

    def __init__(
        self,
        *,
        path: str = MISSING,
        prefix: bool = MISSING,
    ) -> None:
        if hasattr(self, "_init_subclass_kwarg_data"):
            p1, p2 = self._init_subclass_kwarg_data
        else:
            p1 = p2 = MISSING

        if path is MISSING:
            if p1 is MISSING:
                raise ValueError("'path' kwarg not passed")
            path = p1

        if prefix is MISSING:
            prefix = False if p2 == MISSING else p2

        self._parameters = []

        super().__init__(path=path, prefix=prefix)

    def __init_subclass__(
        cls,
        *,
        path: str = MISSING,
        prefix: bool = MISSING,
    ) -> None:
        cls._init_subclass_kwarg_data = path, prefix

    def _match(self, ws: Connection) -> bool:
        if ws._type != "websocket":
            return False

        return super()._match(ws)

    @property
    def description(self) -> str:
        return self.__doc__ or ""

    async def __call__(self, ws: Connection) -> None:
        assert ws._type == "websocket"

        ws._scope["endpoint"] = self

        try:
            await self.on_connect(ws)
        except Exception as e:
            await self._state.on_ws_error(ws, e)
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
                        close_code = WSCodes(code) if code is not None else WSCodes.NORMAL_CLOSURE
                        break
        except Exception as e:
            await self._state.on_ws_error(ws, e)
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
        await self.on_receive(ws, data)

    async def on_connect(self, ws: WebSocket) -> None:
        await ws.accept()

    async def on_disconnect(self, ws: WebSocket, code: WSCodes) -> None:
        ...

    @set_property("__starapi_original__", True)
    async def on_receive(self, ws: WebSocket, data: Any) -> None:
        ...


def _create_http_route(
    self: Any,
    path: str,
    *,
    methods: list[str] = MISSING,
    prefix: bool = MISSING,
    responses: dict[int, Type[Struct]] = MISSING,
    query_parameters: list[Parameter] = MISSING,
    path_parameters: list[Parameter] = MISSING,
    cookies: list[Parameter] = MISSING,
    headers: list[Parameter] = MISSING,
    tags: list[str] = MISSING,
    payload: Type[Struct] = MISSING,
    deprecated: bool = False,
    hidden: bool = False,
) -> Route:
    ...


class RouteSelector:
    def __call__(
        self, *args, **kwargs
    ) -> Callable[[HTTPRouteCallback], Route,]:
        methods = kwargs.pop("methods", [])
        kwargs["methods"] = methods

        if "prefix" not in kwargs:
            kwargs["prefix"] = True

        def decorator(callback: HTTPRouteCallback) -> Route:
            route = Route(*args, **kwargs)
            route.callback = callback
            return route

        return decorator

    @staticmethod
    def _quick_gen(method: str):
        @mimmic(_create_http_route, keep_return=True)
        def func(
            *args, **kwargs
        ) -> Callable[[HTTPRouteCallback], Route,]:
            kwargs.setdefault("methods", [])
            kwargs["methods"].append(method)
            return RouteSelector.__call__(*args, **kwargs)

        return func

    get = _quick_gen("GET")
    post = _quick_gen("POST")
    put = _quick_gen("PUT")
    patch = _quick_gen("PATCH")
    options = _quick_gen("OPTIONS")
    head = _quick_gen("HEAD")

    @overload
    def ws(
        self,
        func: Type[WSRouteT],
        /,
    ) -> WSRouteT:
        ...

    @overload
    def ws(self, /, *, path: str, prefix: bool = ...) -> Callable[[WSRouteCallback], WebSocketRoute]:
        ...

    @overload
    def ws(
        self,
        func: Type[WSRouteT] = MISSING,
        /,
        *,
        path: str = MISSING,
        prefix: bool = MISSING,
    ) -> Callable[[WSRouteCallback], WebSocketRoute] | WSRouteT:
        ...

    def ws(
        self,
        func: Type[WSRouteT] = MISSING,
        /,
        *,
        path: str = MISSING,
        prefix: bool = MISSING,
    ) -> Callable[[WSRouteCallback], WebSocketRoute] | WSRouteT:
        try:
            is_subclassed_route = issubclass(func, WebSocketRoute)
        except TypeError:
            is_subclassed_route = False
        if is_subclassed_route:
            try:
                route = func()
            except Exception:
                raise InvalidWebSocketRoute(
                    "When using the 'Application.ws' decorator with a subclassed route, the __init__ should take 0 arguments"
                )
            return route

        def decorator(callback: WSRouteCallback) -> WebSocketRoute:
            route = WebSocketRoute(path=path)
            route.on_connect = callback  # type: ignore
            route.__doc__ = callback.__doc__
            return route

        return decorator


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
                        raise RuntimeError('The server does not support "state" in the lifespan scope.')
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

        if request._scope["path"] == "/openapi.json/":
            if await self.handle_openapi_route(request) is True:
                return

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

    async def handle_openapi_route(self, request: Connection) -> bool:
        assert request._type == "http"

        docs = request.app._state.get_docs()

        if docs is None:
            return False

        await Response(
            docs.current,
            headers={"Access-Control-Allow-Origin": "*"},
        )(request, bypass_formatter=True)
        return True
