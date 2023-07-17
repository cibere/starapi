from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

import msgspec
from starlette.responses import Response

from .base import BasePayload


class CommandOptionType(Enum):
    command = 1
    group = 2
    string = 3
    integer = 4
    booleon = 5
    user = 6
    channel = 7
    role = 8
    mentionable = 9
    number = 10
    attachment = 11


class OptionChoice(BasePayload):
    name: str
    value: Any


class CommandOption(BasePayload):
    type: CommandOptionType
    name: str
    description: str
    required: bool = True
    choices: list[OptionChoice] = []


class SlashCommand(BasePayload):
    type: CommandOptionType
    name: str
    description: str
    options: list["CommandOption | SlashCommand"] = []


class RootCommand(BasePayload):
    name: str
    description: str
    options: list["CommandOption | SlashCommand"] = []


class InteractionCallbackType(Enum):
    pong = 1
    send_message = 4
    deferred_channel_message_with_source = 5
    deferred_update_message = 6
    update_message = 7
    command_autocomplete = 8
    modal = 9


class EmbedAuthorField(BasePayload):
    name: str
    url: Optional[str] = None
    icon_url: Optional[str] = None


class EmbedFooterField(BasePayload):
    text: str
    icon_url: Optional[str] = None


class EmbedField(BasePayload):
    name: str
    value: str
    inline: bool = False


class Embed(BasePayload):
    title: Optional[str] = None
    type: str = "rich"
    description: Optional[str] = None
    url: Optional[str] = None
    color: Optional[int] = None
    footer: Optional[EmbedFooterField] = None
    author: Optional[EmbedAuthorField] = None
    fields: list[EmbedField] = []


class InteractionCallbackData(BasePayload):
    content: Optional[str] = None
    embeds: list[Embed] = []
    tts: bool = False


class ResponsePayload(BasePayload):
    type: InteractionCallbackType
    data: Optional[InteractionCallbackData] = None

    def to_resp(self) -> Response:
        return Response(
            msgspec.json.encode(self), headers={"Content-Type": "application/json"}
        )


class InteractionType(Enum):
    ping = 1
    app_command = 2
    component = 3
    autocomplete = 4
    modal = 5


class ChannelType(Enum):
    text = 0
    dm = 1
    voice = 2
    group_dm = 3
    category = 4
    announcement = 5
    announcement_thread = 10
    public_thread = 11
    privet_thread = 12
    stage_channe = 13
    guild_directory = 14
    forum = 15


if TYPE_CHECKING:
    from typing_extensions import TypedDict

    class InteractionChannelPayload(TypedDict):
        flags: int
        guild_id: str
        id: str
        last_message_id: str
        last_pin_timestamp: str
        name: str
        nsfw: bool
        parent_id: str
        permissions: str
        position: int
        rate_limit_per_user: int
        topic: Optional[str]
        type: ChannelType

    class InteractionGuildPayload(TypedDict):
        features: list[str]
        id: int
        locale: str

    class InteractionOptionPayload(TypedDict):
        name: str
        type: CommandOptionType
        value: Any

    class InteractionDataPayload(TypedDict):
        id: str
        name: str
        type: CommandOptionType
        options: list["InteractionOptionPayload | InteractionDataPayload"]

    class InteractionUserPayload(TypedDict):
        avatar: str | None
        avatar_decoration: None | str
        disciminator: str
        global_name: str
        id: str
        public_flags: int
        username: str

    class InteractionMemberPayload(TypedDict):
        avatar: str | None
        communication_disabled_until: str | None  # iso format for when member will be untimed out
        deaf: bool
        flags: int
        joined_at: str  # iso format
        mute: bool
        nick: str | None
        pending: Optional[bool]
        permissions: Optional[str]
        premium_since: str | None  # ISO format
        roles: list[str]
        user: Optional[InteractionUserPayload]

    class InteractionPayload(TypedDict):
        app_permissions: str
        application_id: str
        channel: Optional[InteractionChannelPayload]
        channel_id: Optional[str]
        data: InteractionDataPayload
        entitlement_sku_ids: list[Any]  # Unknown
        entitlements: list[Any]  # Unknown
        guild: Optional[InteractionGuildPayload]
        guild_id: Optional[str]
        guild_locale: Optional[str]
        id: str
        locale: str
        member: Optional[InteractionMemberPayload]
        token: str
        type: InteractionType
        version: int
