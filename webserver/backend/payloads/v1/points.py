from .base import BasePayload


class UpdateChatterPointsPayload(BasePayload):
    points: int


class GiftPointsPayload(BasePayload):
    points: int
