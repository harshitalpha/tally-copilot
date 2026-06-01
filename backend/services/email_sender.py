"""Transactional email sender — routes through the infra router (email surface)."""
from infra import router as infra_router
from adapters.email.inmemory import get_email_log          # always available in dev


def send(to: str, subject: str, html: str, text: str = ""):
    try:
        infra_router.call(
            surface="email", task="transactional",
            fn=lambda adapter: adapter.send(to, subject, html, text),
        )
    except Exception as e:
        print(f"[email] send failed to {to}: {e}")


def send_otp(to: str, otp: str, purpose: str = "verification"):
    subject = f"Your Tally Co-pilot {'verification' if purpose == 'verification' else 'one-time'} code"
    html = f"""
<div style="font-family:sans-serif;max-width:480px;margin:40px auto">
  <h2 style="color:#0f172a">Tally Co-pilot</h2>
  <p>Your {purpose} code is:</p>
  <div style="font-size:36px;font-weight:700;letter-spacing:8px;color:#0f172a;
              background:#f1f5f9;padding:16px 24px;border-radius:8px;
              display:inline-block;margin:16px 0">{otp}</div>
  <p style="color:#64748b;font-size:14px">Valid for 10 minutes. Do not share this code.</p>
</div>"""
    send(to, subject, html, text=f"Your Tally Co-pilot {purpose} code: {otp} (valid 10 minutes)")


def send_password_reset(to: str, reset_url: str):
    html = f"""
<div style="font-family:sans-serif;max-width:480px;margin:40px auto">
  <h2 style="color:#0f172a">Reset your password</h2>
  <p>Click the button below to reset your Tally Co-pilot password.
     The link expires in 1 hour.</p>
  <a href="{reset_url}"
     style="display:inline-block;background:#0f172a;color:#fff;
            padding:12px 24px;border-radius:6px;text-decoration:none;
            font-weight:600;margin:16px 0">Reset password</a>
  <p style="color:#64748b;font-size:13px">
    If you didn't request this, ignore this email. Your password won't change.
  </p>
</div>"""
    send(to, "Reset your Tally Co-pilot password", html,
         text=f"Reset your password: {reset_url}\nLink expires in 1 hour.")
