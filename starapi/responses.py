from __future__ import annotations

import json
from typing import Any, Optional

from starlette.responses import Response as BaseResponse

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
        cls,
        content: dict | list | str,
        headers: Optional[dict[str, str]] = None,
        data: dict | str | None = None,
    ) -> BaseResponse:
        payload: dict[str, Any] = {"message": "Success"}

        if isinstance(content, (dict, list)):
            payload["data"] = content
        else:
            payload["message"] = content

        if data is not None:
            payload["data"] = data

        return cls(payload, headers=headers)

    @classmethod
    def client_error(
        cls, message: str, headers: Optional[dict[str, str]] = None
    ) -> BaseResponse:
        return cls({"message": message}, 400, headers=headers)

    @classmethod
    def unauthorized(
        cls, message: str, headers: Optional[dict[str, str]] = None
    ) -> BaseResponse:
        return cls({"message": message}, 401, headers=headers)

    @classmethod
    def not_found(
        cls, data: Optional[Any] = None, headers: Optional[dict[str, str]] = None
    ) -> BaseResponse:
        return cls(data or "", 404, headers=headers)

    @classmethod
    def forbidden(
        cls, message: str, headers: Optional[dict[str, str]] = None
    ) -> BaseResponse:
        return cls({"message": message}, 403, headers=headers)

    @classmethod
    def internal(
        cls, message: str, headers: Optional[dict[str, str]] = None
    ) -> BaseResponse:
        return cls({"message": message}, 500, headers=headers)
