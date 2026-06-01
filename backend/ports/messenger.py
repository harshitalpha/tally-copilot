"""Messenger port — abstracts WhatsApp (Meta / Twilio / Gupshup), SMS, in-app push, etc."""
from typing import Protocol, runtime_checkable


@runtime_checkable
class Messenger(Protocol):
    def send_text(self, to: str, body: str, msg_type: str = "generic") -> None: ...
    def health_check(self) -> tuple[bool, str]: ...
