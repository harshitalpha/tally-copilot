"""Admin API: manage providers + routing rules + view telemetry.

Single-tenant for now — these endpoints are protected by JWT (any logged-in
user). When the system goes multi-tenant, scope reads/writes by user_id.
"""
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, case
from sqlalchemy.orm import Session
from typing import Any, Optional

from database import get_db
import models
from auth import get_current_user
from infra import crypto, catalog
from infra.registry import get_registry


router = APIRouter()


# ============================================================================
# Provider catalog
# ============================================================================

@router.get("/catalog")
def get_catalog(surface: Optional[str] = None, _: models.User = Depends(get_current_user)):
    """List all adapter kinds + their config-field schemas. Surface filter optional."""
    return {"kinds": catalog.list_kinds(surface=surface)}


# ============================================================================
# Providers — CRUD
# ============================================================================

class ProviderIn(BaseModel):
    surface: str
    name: str
    adapter_kind: str
    config: dict
    enabled: bool = True


class ProviderPatch(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    enabled: Optional[bool] = None


def _mask_config(raw: dict, fields: list[dict]) -> dict:
    """Replace password-type fields with a fixed mask so we never leak them."""
    masked = {}
    pwd_fields = {f["name"] for f in fields if f.get("type") == "password"}
    for k, v in raw.items():
        if k in pwd_fields and v:
            masked[k] = "•" * 8 + (str(v)[-4:] if len(str(v)) >= 4 else "")
        else:
            masked[k] = v
    return masked


def _serialize_provider(p: models.ProviderConfig) -> dict:
    fields = catalog.CATALOG.get(p.adapter_kind, {}).get("fields", [])
    try:
        cfg = json.loads(crypto.decrypt(p.config_json))
    except Exception:
        cfg = {}
    return {
        "id": p.id,
        "surface": p.surface,
        "name": p.name,
        "adapter_kind": p.adapter_kind,
        "config": _mask_config(cfg, fields),
        "enabled": p.enabled,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("/providers")
def list_providers(
    surface: Optional[str] = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    q = db.query(models.ProviderConfig)
    if surface:
        q = q.filter(models.ProviderConfig.surface == surface)
    return {"providers": [_serialize_provider(p) for p in q.order_by(models.ProviderConfig.surface, models.ProviderConfig.name).all()]}


@router.post("/providers", status_code=201)
def create_provider(
    body: ProviderIn,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    if body.adapter_kind not in catalog.CATALOG:
        raise HTTPException(400, f"Unknown adapter_kind: {body.adapter_kind}")
    if catalog.CATALOG[body.adapter_kind]["surface"] != body.surface:
        raise HTTPException(400, "surface does not match adapter_kind's surface")
    p = models.ProviderConfig(
        surface=body.surface, name=body.name, adapter_kind=body.adapter_kind,
        config_json=crypto.encrypt(json.dumps(body.config)),
        enabled=body.enabled,
    )
    db.add(p); db.commit(); db.refresh(p)
    # Bump version on the relevant routing rules so the registry reloads
    _bump_rules_for_surface(db, body.surface)
    return _serialize_provider(p)


@router.patch("/providers/{provider_id}")
def update_provider(
    provider_id: str,
    body: ProviderPatch,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    p = db.query(models.ProviderConfig).filter(models.ProviderConfig.id == provider_id).first()
    if not p:
        raise HTTPException(404, "Provider not found")
    if body.name is not None:
        p.name = body.name
    if body.config is not None:
        # Merge — UI may send only the fields the user actually changed (and
        # masked password fields are sent back as the mask; ignore those).
        try:
            current = json.loads(crypto.decrypt(p.config_json))
        except Exception:
            current = {}
        fields = catalog.CATALOG.get(p.adapter_kind, {}).get("fields", [])
        pwd_fields = {f["name"] for f in fields if f.get("type") == "password"}
        for k, v in body.config.items():
            if k in pwd_fields and isinstance(v, str) and v.startswith("•"):
                continue  # masked value, keep existing
            current[k] = v
        p.config_json = crypto.encrypt(json.dumps(current))
    if body.enabled is not None:
        p.enabled = body.enabled
    db.commit(); db.refresh(p)
    _bump_rules_for_surface(db, p.surface)
    return _serialize_provider(p)


@router.delete("/providers/{provider_id}")
def delete_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    p = db.query(models.ProviderConfig).filter(models.ProviderConfig.id == provider_id).first()
    if not p:
        raise HTTPException(404)
    surface = p.surface
    db.delete(p); db.commit()
    _bump_rules_for_surface(db, surface)
    return {"ok": True}


@router.post("/providers/{provider_id}/test")
def test_provider(
    provider_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    p = db.query(models.ProviderConfig).filter(models.ProviderConfig.id == provider_id).first()
    if not p:
        raise HTTPException(404)
    try:
        cfg = json.loads(crypto.decrypt(p.config_json))
        adapter = catalog.build_adapter(p.adapter_kind, cfg)
        ok, msg = adapter.health_check()
        return {"ok": ok, "message": msg}
    except Exception as e:
        return {"ok": False, "message": str(e)[:300]}


# ============================================================================
# Routing rules
# ============================================================================

class RuleIn(BaseModel):
    surface: str
    task: str = "*"
    weights: list[dict]                  # [{"provider_id": "...", "weight": 70}]
    fallback: list[str] = []             # [provider_id, ...]
    budget_cap_usd_month: Optional[float] = None
    max_rpm: Optional[int] = None


def _serialize_rule(r: models.RoutingRule) -> dict:
    try:
        rj = json.loads(r.rule_json)
    except Exception:
        rj = {}
    return {
        "id": r.id, "surface": r.surface, "task": r.task,
        "version": r.version,
        "weights":  rj.get("weights",  []),
        "fallback": rj.get("fallback", []),
        "budget_cap_usd_month": rj.get("budget_cap_usd_month"),
        "max_rpm": rj.get("max_rpm"),
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.get("/rules")
def list_rules(
    surface: Optional[str] = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    q = db.query(models.RoutingRule)
    if surface:
        q = q.filter(models.RoutingRule.surface == surface)
    return {"rules": [_serialize_rule(r) for r in q.order_by(models.RoutingRule.surface, models.RoutingRule.task).all()]}


@router.put("/rules")
def upsert_rule(
    body: RuleIn,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """Replace the rule for (surface, task). Always bumps version → triggers hot reload."""
    rule_json = json.dumps({
        "weights": body.weights,
        "fallback": body.fallback,
        "budget_cap_usd_month": body.budget_cap_usd_month,
        "max_rpm": body.max_rpm,
    })
    existing = (
        db.query(models.RoutingRule)
        .filter(models.RoutingRule.surface == body.surface, models.RoutingRule.task == body.task)
        .first()
    )
    if existing:
        existing.rule_json = rule_json
        existing.version = existing.version + 1
        r = existing
    else:
        r = models.RoutingRule(surface=body.surface, task=body.task, rule_json=rule_json, version=1)
        db.add(r)
    db.commit(); db.refresh(r)
    return _serialize_rule(r)


# ============================================================================
# Topology — convenience endpoint, what the topology UI tab shows
# ============================================================================

@router.get("/topology")
def topology(db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    providers = {p.id: _serialize_provider(p) for p in db.query(models.ProviderConfig).all()}
    rules = [_serialize_rule(r) for r in db.query(models.RoutingRule).all()]
    surfaces: dict[str, dict] = {}
    for r in rules:
        wlist = []
        for w in r["weights"]:
            pmeta = providers.get(w["provider_id"])
            if pmeta:
                wlist.append({
                    "provider_id": w["provider_id"],
                    "name": pmeta["name"],
                    "adapter_kind": pmeta["adapter_kind"],
                    "weight": w["weight"],
                })
        fb = []
        for pid in r["fallback"]:
            pmeta = providers.get(pid)
            if pmeta:
                fb.append({"provider_id": pid, "name": pmeta["name"], "adapter_kind": pmeta["adapter_kind"]})
        surfaces.setdefault(r["surface"], {"surface": r["surface"], "tasks": []})["tasks"].append({
            "task": r["task"], "weights": wlist, "fallback": fb,
        })
    return {"surfaces": list(surfaces.values()), "providers": list(providers.values())}


# ============================================================================
# Telemetry
# ============================================================================

@router.get("/telemetry")
def telemetry(
    surface: Optional[str] = None,
    hours: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    since = datetime.utcnow() - timedelta(hours=hours)
    q = db.query(models.ProviderCallLog).filter(models.ProviderCallLog.started_at >= since)
    if surface:
        q = q.filter(models.ProviderCallLog.surface == surface)

    by_provider = (
        db.query(
            models.ProviderCallLog.provider_id,
            models.ProviderCallLog.adapter_kind,
            models.ProviderCallLog.surface,
            func.count(models.ProviderCallLog.id).label("calls"),
            func.sum(case((models.ProviderCallLog.success == True, 1), else_=0)).label("successes"),
            func.avg(models.ProviderCallLog.duration_ms).label("avg_ms"),
            func.sum(models.ProviderCallLog.cost_usd).label("total_cost"),
        )
        .filter(models.ProviderCallLog.started_at >= since)
        .filter(*( [models.ProviderCallLog.surface == surface] if surface else [] ))
        .group_by(
            models.ProviderCallLog.provider_id,
            models.ProviderCallLog.adapter_kind,
            models.ProviderCallLog.surface,
        )
        .all()
    )
    return {
        "since": since.isoformat(),
        "hours": hours,
        "per_provider": [
            {
                "provider_id": row.provider_id,
                "adapter_kind": row.adapter_kind,
                "surface": row.surface,
                "calls": int(row.calls or 0),
                "successes": int(row.successes or 0),
                "errors": int((row.calls or 0) - (row.successes or 0)),
                "avg_duration_ms": float(row.avg_ms or 0),
                "total_cost_usd": float(row.total_cost or 0),
            }
            for row in by_provider
        ],
    }


@router.get("/call-log")
def call_log(
    surface: Optional[str] = None,
    success: Optional[bool] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    q = db.query(models.ProviderCallLog)
    if surface:
        q = q.filter(models.ProviderCallLog.surface == surface)
    if success is not None:
        q = q.filter(models.ProviderCallLog.success == success)
    total = q.count()
    rows = q.order_by(models.ProviderCallLog.started_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": r.id, "surface": r.surface, "task": r.task,
                "provider_id": r.provider_id, "adapter_kind": r.adapter_kind,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "duration_ms": r.duration_ms,
                "success": r.success, "error": r.error,
                "request_tokens": r.request_tokens,
                "response_tokens": r.response_tokens,
                "cost_usd": r.cost_usd,
            }
            for r in rows
        ],
    }


# ============================================================================
# Helpers
# ============================================================================

def _bump_rules_for_surface(db: Session, surface: str):
    """Force registry reload by bumping the version of every rule on this surface."""
    rules = db.query(models.RoutingRule).filter(models.RoutingRule.surface == surface).all()
    for r in rules:
        r.version = r.version + 1
    db.commit()
    get_registry().invalidate()
