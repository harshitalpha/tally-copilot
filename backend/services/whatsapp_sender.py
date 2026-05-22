import os
from datetime import datetime

_send_log = []


def send_text(phone: str, text: str, msg_type: str = "generic"):
    """Send any plain text message to a phone number."""
    _log(phone, text, msg_type)
    if os.getenv("APP_ENV") != "development":
        # TODO: POST to Meta Graph API
        pass


def send_confirmation(phone: str, supplier: str, amount: float, voucher_id: str):
    msg = (
        f"✅ Posted to Tally\n"
        f"{supplier} · ₹{amount:,.2f}\n"
        f"Tally Voucher #{voucher_id}"
    )
    send_text(phone, msg, "confirmation")


def send_failure(phone: str, error: str):
    msg = (
        f"❌ Could not process invoice\n"
        f"Reason: {error}\n"
        f"Please try again with a clearer photo, or upload via dashboard."
    )
    send_text(phone, msg, "failure")


def _log(phone: str, text: str, msg_type: str):
    entry = {
        "to": phone,
        "type": msg_type,
        "message_text": text,
        "sent_at": datetime.utcnow().isoformat(),
    }
    _send_log.append(entry)
    print(f"\n[WA → {phone}]\n{text}\n")


def get_send_log():
    return _send_log
