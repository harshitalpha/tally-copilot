"""WhatsApp message sender — now goes through the infra router so the actual
backend (in-memory log, Meta Cloud API, Twilio, Gupshup) is swap-able from the
dashboard. The public API (`send_text`, `send_confirmation`, `send_failure`,
`get_send_log`) is unchanged so callers don't need to know.
"""
from infra import router as infra_router
# Always keep the in-memory log around — it's a useful audit trail in dev even
# when a real provider is also wired up.
from adapters.messenger.inmemory import get_send_log, _send_log


def send_text(phone: str, text: str, msg_type: str = "generic"):
    """Send a plain text message via the configured messenger.

    We also log it in-memory so dev mode and the WA Send Log panel always work
    even when a real provider is configured.
    """
    from datetime import datetime
    _send_log.append({
        "to": phone, "type": msg_type, "message_text": text,
        "sent_at": datetime.utcnow().isoformat(),
    })
    print(f"\n[WA → {phone}]\n{text}\n")
    try:
        infra_router.call(
            surface="messenger", task=msg_type,
            fn=lambda adapter: adapter.send_text(phone, text, msg_type),
        )
    except Exception as e:
        # Don't let a messenger failure break the calling flow. The in-memory
        # log captured it; failure is visible in /api/infra/call-log.
        print(f"[messenger] send failed: {e}")


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
