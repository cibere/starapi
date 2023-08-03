from __future__ import annotations

import json
from asyncio.staggered import staggered_race
from typing import TYPE_CHECKING, Any, Optional, Self
from urllib.parse import quote

DataType = list | str | dict | None

if TYPE_CHECKING:
    from .requests import BaseRequest

__all__ = ("Response",)


class Response:
    charset = "utf-8"
    raw_headers: list[tuple[bytes, bytes]]
    body: bytes

    def __init__(
        self,
        data: Any = None,
        status_code: int = 200,
        headers: Optional[dict[str, str]] = None,
        media_type: Optional[str] = None,
    ) -> None:
        if isinstance(data, (dict, list)):
            data = json.dumps(data)
        if data is None:
            data = b""
        if isinstance(data, str):
            data = data.encode()

        self.body = data
        self.status_code = status_code
        self.media_type = media_type
        self.headers = headers or {}

        self.raw_headers = self._process_headers()

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
        await request._send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": self.raw_headers,
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
