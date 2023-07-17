from .base import BasePayload


class WSBotAuth(BasePayload):
    password: str


class ContactFormPayload(BasePayload):
    token: str
    email: str
    subject: str
    content: str
