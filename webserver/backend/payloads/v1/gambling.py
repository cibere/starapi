from .base import BasePayload


class ToggleGamblingGamePayload(BasePayload):
    game_slug: str


class PlayGamblingGamePayload(BasePayload):
    game_slug: str
    choice: int
    bid: int
