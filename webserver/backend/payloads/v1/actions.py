from typing import Literal

from enums import ActionType

from .base import BasePayload


class _BaseActionPayload(BasePayload):
    @property
    def type(self) -> ActionType:
        return ActionType(self.__struct_config__.tag)


class _AssetActionPayload(_BaseActionPayload):
    url: str


class TTSActionPayload(_BaseActionPayload, tag=ActionType.play_tts.value):
    ...


class PlayVideoActionPayload(_AssetActionPayload, tag=ActionType.play_video.value):
    ...


class PlayAudioActionPayload(_AssetActionPayload, tag=ActionType.play_sound.value):
    ...


class HTTPActionPayload(_AssetActionPayload, tag=ActionType.http.value):
    method: Literal["GET", "POST", "PATCH", "HEAD", "DELETE"]
    data: dict
    headers: dict


class DiscordWebhookActionPayload(
    _AssetActionPayload, tag=ActionType.discord_webhook.value
):
    data: dict


ActionPayload = (
    TTSActionPayload
    | PlayVideoActionPayload
    | PlayAudioActionPayload
    | HTTPActionPayload
    | DiscordWebhookActionPayload
)
