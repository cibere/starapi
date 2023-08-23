from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Coroutine

if TYPE_CHECKING:
    from .requests import Request
    from .responses import Response

__all__ = ("ResponseFormatter",)


class ResponseFormatter:
    def __init__(self) -> None:
        ...

    async def __call__(self, request: Request, response: Response) -> Response:
        formatter: Callable[[Request, Response], Coroutine[Any, Any, Response] | Response] | None = getattr(
            self, f"format_{response.status_code}", None
        )
        if formatter is None:
            return response

        resp = formatter(request, response)
        if isinstance(resp, Coroutine):
            return await resp
        return resp
