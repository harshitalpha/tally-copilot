"""In-memory email adapter for development — prints and stores emails in a list."""
from datetime import datetime

_email_log: list[dict] = []


class InMemoryEmailClient:
    def send(self, to: str, subject: str, html: str, text: str = "") -> None:
        entry = {
            "to": to, "subject": subject,
            "text": text or _strip_html(html),
            "sent_at": datetime.utcnow().isoformat(),
        }
        _email_log.append(entry)
        print(f"\n[EMAIL → {to}]\nSubject: {subject}\n{entry['text']}\n")

    def health_check(self) -> tuple[bool, str]:
        return True, f"in-memory log ({len(_email_log)} emails)"


def _strip_html(html: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", html).strip()


def get_email_log():
    return _email_log
