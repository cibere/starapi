from __future__ import annotations

from typing import TYPE_CHECKING

from jwt import ExpiredSignatureError
from starlette.authentication import AuthCredentials, AuthenticationBackend
from starlette.requests import HTTPConnection

if TYPE_CHECKING:
    from starapi import Application, User

__all__ = ("AuthBackend",)


class AuthBackend(AuthenticationBackend):
    def __init__(self, app: Application) -> None:
        self.app = app

    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, User] | None:
        auth: str | None = conn.headers.get("Authorization")
        if not auth:
            return

        try:
            type_, token = auth.split(" ")
        except IndexError:
            return

        scopes: list[str] = ["authed"]

        match type_:
            case "Bearer":
                try:
                    uid, username = self.app.decode_auth_token(token)
                except ExpiredSignatureError:
                    return

                user = await self.app.db.fetch_user(uid=uid)
                if user is None or user.username != username:
                    return

                scopes.append("bearer")

                if user.flags.staff:
                    scopes.append("staff")

                return AuthCredentials(scopes), user
            case "Bot":
                channel_id, _ = self.app.decode_api_key(token)

                user = await self.app.db.fetch_user(uid=channel_id)

                if user is None:
                    return

                scopes.append("bot")

                return AuthCredentials(scopes), user
