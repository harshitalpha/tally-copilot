"""Weighted random routing + fallback chain, with telemetry on every call.

Public entry point: call(surface, task, fn, **ctx_kwargs)
  - surface: "llm" | "object_store" | "messenger"
  - task:    "extract_invoice" | "send_confirmation" | "upload" | ... or "*"
  - fn:      callable(adapter) -> result. We invoke this against the chosen adapter.
  - ctx_kwargs: anything to stamp on the CallContext (model, request_tokens, ...)

Picks a primary by weighted random, then walks the fallback list on exception.
Every attempt produces one ProviderCallLog row.
"""
import random
from typing import Callable, Any
from database import SessionLocal

from infra.registry import get_registry
from infra.telemetry import record_call, CallContext


def _pick_weighted(weights: list[dict]) -> str | None:
    """Returns the chosen provider_id, or None if the rule is empty."""
    if not weights:
        return None
    total = sum(max(0, int(w.get("weight", 0))) for w in weights)
    if total <= 0:
        return weights[0]["provider_id"]
    pick = random.uniform(0, total)
    cum = 0.0
    for w in weights:
        cum += max(0, int(w.get("weight", 0)))
        if pick <= cum:
            return w["provider_id"]
    return weights[-1]["provider_id"]


def _build_chain(rule: dict) -> list[str]:
    """Returns [primary_provider_id, ...fallback ids without duplicates]."""
    primary = _pick_weighted(rule.get("weights", []))
    chain: list[str] = []
    if primary:
        chain.append(primary)
    for pid in rule.get("fallback", []):
        if pid not in chain:
            chain.append(pid)
    return chain


def call(
    surface: str,
    task: str,
    fn: Callable[[Any], Any],
    setup_ctx: Callable[[CallContext], None] | None = None,
    user_id: str | None = None,
):
    """Route a call to the right provider with fallback.

    fn(adapter) -> result. Raises if every provider in the chain fails.

    setup_ctx(ctx) — optional hook to stamp model/token info onto the call
    context before fn runs (so even if fn raises, telemetry has the model).
    """
    db = SessionLocal()
    try:
        reg = get_registry()
        reg.refresh_if_stale(db)
        rule = reg.get_rule(surface, task)
        if not rule:
            raise RuntimeError(
                f"No routing rule configured for surface={surface!r} task={task!r}. "
                f"Set one at /settings/infra."
            )
        chain = _build_chain(rule)
        if not chain:
            raise RuntimeError(f"Routing rule for {surface}/{task} has no providers.")

        last_error: Exception | None = None
        for provider_id in chain:
            adapter = reg.get_provider(provider_id)
            if adapter is None:
                continue
            meta = reg.get_provider_meta(provider_id) or {}
            try:
                with record_call(
                    surface=surface, task=task,
                    provider_id=provider_id,
                    adapter_kind=meta.get("adapter_kind"),
                    user_id=user_id,
                ) as ctx:
                    if setup_ctx:
                        setup_ctx(ctx)
                    # Adapters that know their model can also set ctx.model themselves
                    # via the convention of having a `.model` attribute.
                    if getattr(adapter, "model", None) and not ctx.model:
                        ctx.model = adapter.model
                    return fn(adapter)
            except Exception as e:
                last_error = e
                continue  # try next in chain

        raise last_error or RuntimeError(f"All providers in chain failed for {surface}/{task}")
    finally:
        db.close()
