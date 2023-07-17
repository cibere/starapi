from uuid import UUID

from kick.utils import MISSING

from .base import BasePayload


class DeleteChannelTokenPayload(BasePayload):
    id: UUID


class CreateChannelTokenPayload(BasePayload):
    name: str
    expires_in: int | None  # amount of hours until expiration or no expiration


class CreateChannelPayload(BasePayload):
    chatroom_id: int


class EditChannelPayload(BasePayload):
    points_for_message: int = MISSING
    max_points_per_minute: int | None = MISSING
    message_interval: int = MISSING
    points_for_follow: int = MISSING
