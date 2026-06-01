import json, csv, io
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
import models
from auth import get_current_user
from services.pipeline import run_pipeline

router = APIRouter()


# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_data(action: models.UserAction) -> dict:
    try:
        return json.loads(action.data)
    except (TypeError, ValueError):
        return {}


def _serialize(action: models.UserAction) -> dict:
    data = _parse_data(action)
    return {
        "id":          action.id,
        "action_type": action.action_type,
        "status":      action.status,
        "data":        data,
        "created_at":  action.created_at.isoformat() if action.created_at else None,
        "updated_at":  action.updated_at.isoformat() if action.updated_at else None,
    }


def _supplier(action: models.UserAction) -> str:
    try:
        d = json.loads(action.data)
        inv = d.get("extracted_invoice") or {}
        return (inv.get("supplier_name") or "").lower()
    except Exception:
        return ""


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
def stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    all_actions = (
        db.query(models.UserAction)
        .filter(models.UserAction.user_id == current_user.id)
        .all()
    )
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def _amount(a: models.UserAction) -> float:
        try:
            d = json.loads(a.data)
            return float((d.get("extracted_invoice") or {}).get("total_amount") or 0)
        except Exception:
            return 0.0

    this_month = [a for a in all_actions if a.created_at and a.created_at >= month_start]

    def _summary(actions):
        total  = len(actions)
        synced = sum(1 for a in actions if a.status == "synced")
        failed = sum(1 for a in actions if a.status == "failed")
        pending = sum(1 for a in actions if a.status in ("pending", "processing", "pending_review", "pending_sync"))
        amount = sum(_amount(a) for a in actions if a.status == "synced")
        return {
            "total":          total,
            "synced":         synced,
            "failed":         failed,
            "pending":        pending,
            "success_rate":   round(synced / total * 100, 1) if total else 0,
            "total_amount_inr": round(amount, 2),
        }

    return {
        "this_month": _summary(this_month),
        "all_time":   _summary(all_actions),
    }


# ── List (search + filter + pagination) ──────────────────────────────────────

@router.get("")
def list_actions(
    status:     Optional[str] = Query(None),
    search:     Optional[str] = Query(None, description="Supplier name contains"),
    from_date:  Optional[date] = Query(None),
    to_date:    Optional[date] = Query(None),
    page:       int = Query(1, ge=1),
    page_size:  int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = db.query(models.UserAction).filter(models.UserAction.user_id == current_user.id)

    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            q = q.filter(models.UserAction.status.in_(statuses))
    if from_date:
        q = q.filter(models.UserAction.created_at >= datetime.combine(from_date, datetime.min.time()))
    if to_date:
        q = q.filter(models.UserAction.created_at <= datetime.combine(to_date, datetime.max.time()))

    items = q.order_by(models.UserAction.created_at.desc()).all()

    # Supplier search in Python (JSON text column, no full-text index in SQLite)
    if search:
        term = search.lower()
        items = [a for a in items if term in _supplier(a)]

    total = len(items)
    offset = (page - 1) * page_size
    page_items = items[offset: offset + page_size]

    return {
        "total":       total,
        "page":        page,
        "page_size":   page_size,
        "total_pages": max(1, -(-total // page_size)),
        "items":       [_serialize(a) for a in page_items],
    }


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{action_id}")
def get_action(
    action_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    action = (
        db.query(models.UserAction)
        .filter(models.UserAction.id == action_id, models.UserAction.user_id == current_user.id)
        .first()
    )
    if not action:
        raise HTTPException(404, "Action not found")
    return _serialize(action)


# ── Retry ─────────────────────────────────────────────────────────────────────

@router.post("/{action_id}/retry")
def retry_action(
    action_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    action = (
        db.query(models.UserAction)
        .filter(models.UserAction.id == action_id, models.UserAction.user_id == current_user.id)
        .first()
    )
    if not action:
        raise HTTPException(404, "Action not found")
    if action.status not in ("failed",):
        raise HTTPException(400, f"Can only retry failed actions (current: {action.status})")

    d = _parse_data(action)
    d["tally_error"] = None
    d["tally_voucher_id"] = None
    d["validation_errors"] = []
    d["validation_warnings"] = []
    action.data = json.dumps(d)
    action.status = "pending"
    action.updated_at = datetime.utcnow()
    db.commit()

    background_tasks.add_task(run_pipeline, action.id)
    return {"status": "pending", "message": "Retrying"}


# ── Manual review ─────────────────────────────────────────────────────────────

class UpdateExtractedRequest(BaseModel):
    extracted_invoice: dict


@router.patch("/{action_id}/extracted")
def update_extracted(
    action_id: str,
    body: UpdateExtractedRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Update extracted invoice data while in pending_review state."""
    action = (
        db.query(models.UserAction)
        .filter(models.UserAction.id == action_id, models.UserAction.user_id == current_user.id)
        .first()
    )
    if not action:
        raise HTTPException(404)
    if action.status != "pending_review":
        raise HTTPException(400, "Can only edit invoices in pending_review status")

    d = _parse_data(action)
    d["extracted_invoice"] = body.extracted_invoice
    # Re-validate
    from services.validator import validate
    v = validate(body.extracted_invoice)
    d["validation_errors"]   = v["errors"]
    d["validation_warnings"] = v["warnings"]
    action.data = json.dumps(d)
    action.updated_at = datetime.utcnow()
    db.commit()
    return _serialize(action)


@router.post("/{action_id}/approve")
def approve_action(
    action_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Move from pending_review → pending_sync (connector will pick it up)."""
    action = (
        db.query(models.UserAction)
        .filter(models.UserAction.id == action_id, models.UserAction.user_id == current_user.id)
        .first()
    )
    if not action:
        raise HTTPException(404)
    if action.status != "pending_review":
        raise HTTPException(400, f"Can only approve pending_review actions (current: {action.status})")

    d = _parse_data(action)
    if d.get("validation_errors"):
        raise HTTPException(400, "Fix validation errors before approving: " +
                            "; ".join(d["validation_errors"][:3]))

    action.status = "pending_sync"
    action.updated_at = datetime.utcnow()
    db.commit()
    return {"status": "pending_sync"}


@router.post("/{action_id}/reject")
def reject_action(
    action_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    action = (
        db.query(models.UserAction)
        .filter(models.UserAction.id == action_id, models.UserAction.user_id == current_user.id)
        .first()
    )
    if not action:
        raise HTTPException(404)
    if action.status != "pending_review":
        raise HTTPException(400, "Can only reject pending_review actions")
    d = _parse_data(action)
    d["tally_error"] = "Rejected by user"
    action.data = json.dumps(d)
    action.status = "failed"
    action.updated_at = datetime.utcnow()
    db.commit()
    return {"status": "failed"}


# ── CSV export ────────────────────────────────────────────────────────────────

@router.get("/export.csv")
def export_csv(
    status: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date:   Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = db.query(models.UserAction).filter(models.UserAction.user_id == current_user.id)
    if status:
        q = q.filter(models.UserAction.status.in_([s.strip() for s in status.split(",")]))
    if from_date:
        q = q.filter(models.UserAction.created_at >= datetime.combine(from_date, datetime.min.time()))
    if to_date:
        q = q.filter(models.UserAction.created_at <= datetime.combine(to_date, datetime.max.time()))
    actions = q.order_by(models.UserAction.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Date", "Status", "Source", "Invoice #", "Supplier", "Supplier GSTIN",
        "Invoice Date", "Place of Supply",
        "Taxable Amount", "CGST", "SGST", "IGST", "Total Amount",
        "Tally Voucher #", "Error",
    ])
    for a in actions:
        d   = _parse_data(a)
        inv = d.get("extracted_invoice") or {}
        writer.writerow([
            a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "",
            a.status,
            d.get("source", ""),
            inv.get("invoice_number", ""),
            inv.get("supplier_name", ""),
            inv.get("supplier_gstin", ""),
            inv.get("invoice_date", ""),
            inv.get("place_of_supply", ""),
            inv.get("total_taxable_amount", ""),
            inv.get("total_cgst", ""),
            inv.get("total_sgst", ""),
            inv.get("total_igst", ""),
            inv.get("total_amount", ""),
            d.get("tally_voucher_id", ""),
            d.get("tally_error", ""),
        ])

    output.seek(0)
    filename = f"invoices_{date.today()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
