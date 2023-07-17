from __future__ import annotations

from typing import TYPE_CHECKING, Self

import msgspec
from starlette.responses import Response

if TYPE_CHECKING:
    from starapi import Request


class BasePayload(msgspec.Struct):
    def encode(self) -> bytes:
        return msgspec.json.encode(self)

    def to_dict(self) -> dict:
        return {e: getattr(self, e) for e in self.__struct_fields__}

    @classmethod
    async def from_request(cls, request: Request) -> tuple[Self | Response, bool]:
        from utils import get_payload

        data = await get_payload(request, payload_type=cls)
        return data, not isinstance(data, Response)  # type: ignore
