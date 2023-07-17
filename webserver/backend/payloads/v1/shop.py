from typing import Any
from uuid import UUID

from .actions import ActionPayload
from .base import BasePayload


class ShopItemPayload(BasePayload):
    name: str
    icon_url: str
    description: str
    price: int
    actions: list[ActionPayload]


class DeleteShopItemPayload(BasePayload):
    item_id: UUID


class BuyShopItemPayload(BasePayload):
    item_id: UUID
    args: dict[UUID, Any]
