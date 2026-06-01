import os, json
from sqlalchemy.orm import Session
import models
from infra import crypto


def seed_if_empty(db: Session):
    existing = db.query(models.ProviderConfig).count()
    if existing > 0:
        _backfill_existing_users(db)
        return

    seeded_llm = []

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and gemini_key != "your_gemini_key_here":
        cfg = {
            "api_key": gemini_key,
            "model": os.getenv("GEMINI_MODEL", "models/gemma-4-31b-it"),
            "vision_model": "gemini-2.0-flash",
        }
        p = models.ProviderConfig(
            surface="llm", name="gemini-default", adapter_kind="gemini",
            config_json=crypto.encrypt(json.dumps(cfg)), enabled=True,
        )
        db.add(p); db.flush()
        seeded_llm.append((p.id, 100))

    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key and anthropic_key not in ("your_claude_key_here", "your_key_here"):
        cfg = {
            "api_key": anthropic_key,
            "model": os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
        }
        p = models.ProviderConfig(
            surface="llm", name="claude-default", adapter_kind="anthropic",
            config_json=crypto.encrypt(json.dumps(cfg)), enabled=True,
        )
        db.add(p); db.flush()
        if not seeded_llm:
            seeded_llm.append((p.id, 100))

    # Messenger (WhatsApp / in-memory)
    mem = models.ProviderConfig(
        surface="messenger", name="inmemory-default", adapter_kind="inmemory_messenger",
        config_json=crypto.encrypt(json.dumps({})), enabled=True,
    )
    db.add(mem); db.flush()

    # Object store (local FS)
    fs = models.ProviderConfig(
        surface="object_store", name="local-fs-default", adapter_kind="local_fs",
        config_json=crypto.encrypt(json.dumps({"base_path": "uploads/"})), enabled=True,
    )
    db.add(fs); db.flush()

    # Email — use Resend if key present, else in-memory
    resend_key = os.getenv("RESEND_API_KEY")
    if resend_key and resend_key != "your_resend_key_here":
        email_cfg = {
            "api_key": resend_key,
            "from_email": os.getenv("RESEND_FROM_EMAIL", "noreply@resend.dev"),
        }
        email_p = models.ProviderConfig(
            surface="email", name="resend-default", adapter_kind="resend",
            config_json=crypto.encrypt(json.dumps(email_cfg)), enabled=True,
        )
    else:
        email_p = models.ProviderConfig(
            surface="email", name="inmemory-email", adapter_kind="inmemory_email",
            config_json=crypto.encrypt(json.dumps({})), enabled=True,
        )
    db.add(email_p); db.flush()

    # Routing rules
    if seeded_llm:
        all_llm = db.query(models.ProviderConfig).filter(
            models.ProviderConfig.surface == "llm"
        ).all()
        primary_ids = {pid for pid, _ in seeded_llm}
        fallback = [p.id for p in all_llm if p.id not in primary_ids]
        weights = [{"provider_id": pid, "weight": w} for pid, w in seeded_llm]
        for task in ("extract_invoice", "extract_invoice_image"):
            db.add(models.RoutingRule(
                surface="llm", task=task, version=1,
                rule_json=json.dumps({"weights": weights, "fallback": fallback,
                                      "budget_cap_usd_month": None, "max_rpm": None}),
            ))
    db.add(models.RoutingRule(
        surface="messenger", task="*", version=1,
        rule_json=json.dumps({"weights": [{"provider_id": mem.id, "weight": 100}], "fallback": []}),
    ))
    db.add(models.RoutingRule(
        surface="object_store", task="*", version=1,
        rule_json=json.dumps({"weights": [{"provider_id": fs.id, "weight": 100}], "fallback": []}),
    ))
    db.add(models.RoutingRule(
        surface="email", task="*", version=1,
        rule_json=json.dumps({"weights": [{"provider_id": email_p.id, "weight": 100}], "fallback": []}),
    ))
    db.commit()
    print(f"[seed] {db.query(models.ProviderConfig).count()} providers, "
          f"{db.query(models.RoutingRule).count()} rules")


def _backfill_existing_users(db: Session):
    """Mark existing (pre-email-OTP) users as verified so they aren't locked out."""
    updated = (
        db.query(models.User)
        .filter(models.User.email_verified == False, models.User.email_otp.is_(None))
        .update({"email_verified": True})
    )
    if updated:
        db.commit()
        print(f"[seed] backfilled email_verified=True for {updated} existing users")
