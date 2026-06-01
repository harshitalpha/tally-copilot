"""Telemetry — wraps every adapter call. Times it, captures errors, computes
cost from a static pricing table, persists to ProviderCallLog.
"""
import time
from contextlib import contextmanager
from datetime import datetime
from database import SessionLocal
import models


# Per-1M-token pricing in USD. Add new models here as they're enabled.
# Sources:
#   Gemma via Google AI Studio: free (rate-limited)
#   Anthropic Claude:  https://www.anthropic.com/pricing
#   OpenAI:            https://openai.com/api/pricing/
PRICING_PER_MTOK: dict[str, dict[str, float]] = {
    "models/gemma-4-31b-it":           {"input": 0.0,  "output": 0.0},
    "gemini-2.0-flash":                {"input": 0.10, "output": 0.40},
    "gemini-1.5-pro":                  {"input": 1.25, "output": 5.00},
    "claude-sonnet-4-20250514":        {"input": 3.0,  "output": 15.0},
    "claude-haiku-4-5-20251001":       {"input": 1.0,  "output": 5.0},
    "gpt-4o":                          {"input": 2.50, "output": 10.0},
    "gpt-4o-mini":                     {"input": 0.15, "output": 0.60},
}


class CallContext:
    """Mutated by the caller inside the `with` block to record token counts etc."""
    def __init__(self):
        self.model: str | None = None
        self.request_tokens: int | None = None
        self.response_tokens: int | None = None
        # If the adapter doesn't report tokens, we estimate later from char counts.
        self.estimated: bool = False


def _estimate_cost(ctx: CallContext) -> float | None:
    if not ctx.model or ctx.model not in PRICING_PER_MTOK:
        return None
    if ctx.request_tokens is None and ctx.response_tokens is None:
        return None
    p = PRICING_PER_MTOK[ctx.model]
    inp = (ctx.request_tokens or 0) * p["input"]
    out = (ctx.response_tokens or 0) * p["output"]
    return round((inp + out) / 1_000_000, 6)


@contextmanager
def record_call(surface: str, task: str, provider_id: str | None, adapter_kind: str | None,
                user_id: str | None = None):
    started_at = datetime.utcnow()
    t0 = time.time()
    success = False
    error_msg: str | None = None
    ctx = CallContext()
    try:
        yield ctx
        success = True
    except Exception as e:
        error_msg = (str(e) or e.__class__.__name__)[:1000]
        raise
    finally:
        duration_ms = int((time.time() - t0) * 1000)
        cost = _estimate_cost(ctx)
        db = SessionLocal()
        try:
            db.add(models.ProviderCallLog(
                user_id=user_id, surface=surface, task=task,
                provider_id=provider_id, adapter_kind=adapter_kind,
                started_at=started_at, duration_ms=duration_ms,
                success=success, error=error_msg,
                request_tokens=ctx.request_tokens,
                response_tokens=ctx.response_tokens,
                cost_usd=cost,
            ))
            db.commit()
        except Exception as e:
            print(f"[telemetry] failed to persist call log: {e}")
            db.rollback()
        finally:
            db.close()


def estimate_tokens(text: str) -> int:
    """Rough heuristic: 1 token ≈ 4 chars. Good enough for cost dashboards."""
    return max(1, len(text) // 4)
