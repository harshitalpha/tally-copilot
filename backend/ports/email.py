from typing import Protocol, runtime_checkable


@runtime_checkable
class EmailClient(Protocol):
    def send(self, to: str, subject: str, html: str, text: str = "") -> None: ...
    def health_check(self) -> tuple[bool, str]: ...
