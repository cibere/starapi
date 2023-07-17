from .base import BasePayload


class CreateAccountPayload(BasePayload):
    password: str
