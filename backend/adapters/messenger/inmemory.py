"""In-memory messenger — dev mode, prints + stores in a list."""
from datetime import datetime


_send_log: list[dict] = []


class InMemoryMessenger:
    def __init__(self):
        pass

    def send_text(self, to: str, body: str, msg_type: str = "generic") -> None:
        entry = {
            "to": to,
            "type": msg_type,
            "message_text": body,
            "sent_at": datetime.utcnow().isoformat(),
        }
        _send_log.append(entry)
        print(f"\n[WA → {to}]\n{body}\n")

    def health_check(self) -> tuple[bool, str]:
        return True, f"in-memory log ({len(_send_log)} messages)"


def get_send_log():
    return _send_log
