"""Meta Cloud API messenger — production WhatsApp via Meta's Graph API.

Configure with a phone number id + an access token. See Meta WhatsApp Business
Cloud API docs for issuing tokens.
"""
import httpx


class MetaCloudAPIMessenger:
    def __init__(self, phone_number_id: str, access_token: str, api_version: str = "v18.0"):
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.api_version = api_version
        self._base = f"https://graph.facebook.com/{api_version}"

    def send_text(self, to: str, body: str, msg_type: str = "generic") -> None:
        url = f"{self._base}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to.lstrip("+"),
            "type": "text",
            "text": {"body": body},
        }
        with httpx.Client(timeout=10) as client:
            r = client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            r.raise_for_status()

    def health_check(self) -> tuple[bool, str]:
        url = f"{self._base}/{self.phone_number_id}"
        try:
            with httpx.Client(timeout=5) as client:
                r = client.get(url, headers={"Authorization": f"Bearer {self.access_token}"})
                if r.status_code == 200:
                    return True, "Meta phone number reachable"
                return False, f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            return False, str(e)[:200]
