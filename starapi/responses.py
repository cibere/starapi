from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Optional, Self
from urllib.parse import quote

try:
    import msgspec
except ImportError:
    msgspec = None

if TYPE_CHECKING:
    from msgspec import Struct

    from ._types import Encoder
    from .requests import BaseRequest
    from .state import State

    DataType = list | str | dict | None | Struct
else:
    DataType = list | str | dict | None

__all__ = ("Response",)


class Response:
    charset = "utf-8"

    def __init__(
        self,
        data: Any = None,
        status_code: int = 200,
        headers: Optional[dict[str, str]] = None,
        media_type: Optional[str] = None,
    ) -> None:
        self.body = data
        self.__data = data
        self.status_code = status_code
        self.media_type = media_type
        self.headers = headers or {}

    @property
    def body(self) -> bytes:
        return self._body

    @body.setter
    def body(self, data: Any):
        if isinstance(data, (dict, list)):
            data = json.dumps(data)
        if data is None:
            data = b""
        if isinstance(data, str):
            data = data.encode()

        if msgspec is not None:
            if isinstance(data, msgspec.Struct):
                data = msgspec.json.encode(data)

        self._body = data

    def _fix_struct_encoding(self, *, accept_header: str | None, state: State) -> None:
        if msgspec is None:
            return

        if accept_header in ("application/x-yaml", "text/yaml"):
            format_ = "yaml"
        elif accept_header == "application/toml":
            format_ = "toml"
        elif accept_header == "application/json":
            format_ = "json"
        elif accept_header in ("application/msgpack", "application/x-msgpack"):
            format_ = "msgpack"
        else:
            format_ = None

        if format_ is None:
            encoder = state.default_encoder
        else:
            encoder: Encoder = eval(f"msgspec.{format_}.encode")

        self.body = encoder(self.__data)

    def _process_headers(self) -> list[tuple[bytes, bytes]]:
        if self.headers:
            raw_headers = [
                (k.lower().encode("latin-1"), v.encode("latin-1"))
                for k, v in self.headers.items()
            ]
        else:
            raw_headers = []
        keys = [h[0] for h in raw_headers]

        if "content-length" not in keys:
            raw_headers.append(
                (b"content-length", str(len(self.body)).encode("latin-1"))
            )
        if self.media_type is not None and "content_type" not in keys:
            content_type = self.media_type

            if content_type.startswith("text/"):
                content_type += "; charset=" + self.charset
            raw_headers.append((b"content-type", content_type.encode("latin-1")))

        return raw_headers

    async def __call__(self, request: BaseRequest) -> None:
        self._fix_struct_encoding(
            accept_header=request.headers.get("accept", None), state=request.app._state
        )

        await request._send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self._process_headers(),
            }
        )
        await request._send({"type": "http.response.body", "body": self.body})

    @classmethod
    def ok(
        cls, data: DataType = None, headers: Optional[dict[str, str]] = None
    ) -> Self:
        return cls(data, 200 if data else 201, headers=headers)

    @classmethod
    def client_error(
        cls, data: DataType = None, headers: Optional[dict[str, str]] = None
    ) -> Self:
        return cls(data, 400, headers=headers)

    @classmethod
    def unauthorized(
        cls, data: DataType = None, headers: Optional[dict[str, str]] = None
    ) -> Self:
        return cls(data, 401, headers=headers)

    @classmethod
    def forbidden(
        cls, data: DataType = None, headers: Optional[dict[str, str]] = None
    ) -> Self:
        return cls(data, 403, headers=headers)

    @classmethod
    def not_found(
        cls, data: Optional[Any] = None, headers: Optional[dict[str, str]] = None
    ) -> Self:
        return cls(data, 404, headers=headers)

    @classmethod
    def internal(
        cls, data: DataType = None, headers: Optional[dict[str, str]] = None
    ) -> Self:
        return cls(data, 500, headers=headers)

    @classmethod
    def redirect(cls, url: str, headers: Optional[dict[str, str]] = None):
        headers = headers or {}
        headers["location"] = quote(url, safe=":/%#?=@[]!$&'()*+,;")
        return cls(b"", headers=headers)

    @classmethod
    def method_not_allowed(
        cls, data: DataType = None, headers: Optional[dict[str, str]] = None
    ) -> Self:
        return cls("Method Not Allowed" if data is None else data, 405, headers=headers)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} status={self.status_code!r} media_type={self.media_type!r}>"
