"""Resend email adapter — https://resend.com.

Free tier: 3,000 emails/month. API is a single POST.
Set RESEND_API_KEY in .env and configure via /settings/infra.
"""
import httpx


class ResendEmailClient:
    def __init__(self, api_key: str, from_email: str = "noreply@resend.dev"):
        self.api_key = api_key
        self.from_email = from_email
        self._base = "https://api.resend.com"

    def send(self, to: str, subject: str, html: str, text: str = "") -> None:
        payload: dict = {
            "from": self.from_email,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        if text:
            payload["text"] = text
        with httpx.Client(timeout=10) as client:
            r = client.post(
                f"{self._base}/emails",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            r.raise_for_status()

    def health_check(self) -> tuple[bool, str]:
        try:
            with httpx.Client(timeout=5) as client:
                r = client.get(
                    f"{self._base}/domains",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                if r.status_code == 200:
                    return True, "Resend API reachable"
                return False, f"HTTP {r.status_code}"
        except Exception as e:
            return False, str(e)[:200]
