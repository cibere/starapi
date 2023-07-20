from __future__ import annotations

import json
from typing import Any, Optional

from starlette.responses import Response as BaseResponse

DataType = list | str | dict | None

__all__ = ("Response",)


class Response(BaseResponse):
    def __init__(
        self,
        data: Any,
        status_code: int = 200,
        headers: Optional[dict[str, str]] = None,
        media_type: Optional[str] = None,
    ) -> None:
        if isinstance(data, (dict, list)):
            data = json.dumps(data)

        return super().__init__(data, status_code, headers, media_type)

    @classmethod
    def ok(
        cls, data: DataType = None, headers: Optional[dict[str, str]] = None
    ) -> BaseResponse:
        return cls(data, 200 if data else 201, headers=headers)

    @classmethod
    def client_error(
        cls, data: DataType = None, headers: Optional[dict[str, str]] = None
    ) -> BaseResponse:
        return cls(data, 400, headers=headers)

    @classmethod
    def unauthorized(
        cls, data: DataType = None, headers: Optional[dict[str, str]] = None
    ) -> BaseResponse:
        return cls(data, 401, headers=headers)

    @classmethod
    def forbidden(
        cls, data: DataType = None, headers: Optional[dict[str, str]] = None
    ) -> BaseResponse:
        return cls(data, 403, headers=headers)

    @classmethod
    def not_found(
        cls, data: Optional[Any] = None, headers: Optional[dict[str, str]] = None
    ) -> BaseResponse:
        return cls(data, 404, headers=headers)

    @classmethod
    def internal(
        cls, data: DataType = None, headers: Optional[dict[str, str]] = None
    ) -> BaseResponse:
        return cls(data, 500, headers=headers)
