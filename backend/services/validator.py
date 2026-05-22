import re
from datetime import date as date_type


def validate(data: dict) -> dict:
    """
    Returns {"errors": [...], "warnings": [...]}.

    Errors are HARD: the pipeline will mark the action `failed` and NOT push to Tally.
    Warnings are SOFT: allowed to post; surfaced in the UI for the user to notice.
    """
    errors, warnings = [], []

    # ----- Document classification gate -----
    if data.get("is_valid_tax_invoice") is False:
        reason = data.get("rejection_reason") or "Document is not a tax invoice"
        doc_type = data.get("document_type") or "unknown"
        errors.append(f"Not a tax invoice (detected: {doc_type}). {reason}")
        # Short-circuit — there's no point checking other fields when the doc
        # isn't an invoice at all. Anything else we report would be noise.
        return {"errors": errors, "warnings": warnings}

    # ----- Structural required fields (a Tally voucher cannot be posted without these) -----
    if not (data.get("supplier_name") or "").strip():
        errors.append("Missing supplier name")
    if not (data.get("invoice_number") or "").strip():
        errors.append("Missing invoice number")
    if not (data.get("invoice_date") or "").strip():
        errors.append("Missing invoice date")
    try:
        total = float(data.get("total_amount") or 0)
    except (TypeError, ValueError):
        total = 0.0
    if total <= 0:
        errors.append("Missing or zero total amount")

    line_items = data.get("line_items") or []
    if not line_items:
        errors.append("No line items found")
    else:
        any_amount = False
        for li in line_items:
            try:
                if float(li.get("taxable_amount") or 0) > 0:
                    any_amount = True
                    break
            except (TypeError, ValueError):
                continue
        if not any_amount:
            errors.append("All line items have zero amount")

    # ----- GSTIN format check (hard error if present but malformed) -----
    if data.get("supplier_gstin"):
        if not re.match(
            r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$",
            str(data["supplier_gstin"]).upper(),
        ):
            errors.append(f"Invalid GSTIN: {data['supplier_gstin']}")

    # ----- Date sanity (hard error if in future or malformed) -----
    if data.get("invoice_date"):
        try:
            if date_type.fromisoformat(data["invoice_date"]) > date_type.today():
                errors.append("Invoice date is in the future")
        except ValueError:
            errors.append(f"Invalid date: {data['invoice_date']}")

    # ----- Tax math (warnings only — allow posting, just flag for review) -----
    for item in line_items:
        for tax in ["cgst", "sgst", "igst"]:
            r = item.get(f"{tax}_rate")
            a = item.get(f"{tax}_amount")
            t = item.get("taxable_amount")
            if r and a and t:
                try:
                    exp = round(float(t) * float(r) / 100, 2)
                    if abs(exp - float(a)) > 2:
                        warnings.append(
                            f"{tax.upper()} mismatch on '{item.get('description')}': expected {exp}, got {a}"
                        )
                except (TypeError, ValueError):
                    pass

    try:
        calc = sum(
            float(data.get(k) or 0)
            for k in ["total_taxable_amount", "total_cgst", "total_sgst", "total_igst"]
        )
        stated = float(data.get("total_amount") or 0)
        if stated > 0 and abs(calc - stated) > 5:
            warnings.append(f"Total mismatch: calculated {calc:.2f}, stated {stated:.2f}")
    except (TypeError, ValueError):
        pass

    return {"errors": errors, "warnings": warnings}
