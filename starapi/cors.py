from __future__ import annotations

from typing import TYPE_CHECKING, Any, Coroutine, Sequence

from starlette.middleware.cors import CORSMiddleware

from .middleware import BaseMiddleware
from .utils import MISSING

if TYPE_CHECKING:
    from .requests import Request

__all__ = ("CORSSettings",)


class CORSSettings(BaseMiddleware):
    def __init__(
        self,
        allow_origins: Sequence[str] = MISSING,
        allow_methods: Sequence[str] = MISSING,
        allow_headers: Sequence[str] = MISSING,
        allow_credentials: bool = MISSING,
        allow_origin_regex: str | None = None,
        expose_headers: Sequence[str] = MISSING,
        max_age: int = MISSING,
    ):
        self.allow_origins = allow_origins or ()
        self.allow_methods = allow_methods or ("GET",)
        self.allow_headers = allow_headers or ()
        self.allow_credentials = allow_credentials or False
        self.allow_origin_regex = allow_origin_regex
        self.expose_headers = expose_headers or ()
        self.max_age = max_age or 600

    def __call__(self, request: Request) -> Coroutine[Any, Any, Any]:
        return CORSMiddleware(
            app=request.app,
            allow_origins=self.allow_origins,
            allow_methods=self.allow_methods,
            allow_headers=self.allow_headers,
            allow_credentials=self.allow_credentials,
            allow_origin_regex=self.allow_origin_regex,
            expose_headers=self.expose_headers,
            max_age=self.max_age,
        )(request._scope, request._receive, request._send)
