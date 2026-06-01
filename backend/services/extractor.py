"""Invoice extraction — text (pdfplumber) and image (Gemini Vision).

Branches on file_type:
  PDF  → pdfplumber text extraction → text LLM
  image → bytes sent directly to vision LLM

The LLM provider is resolved through the infra router (registry + routing rules).
"""
import pdfplumber
from infra import router as infra_router
from infra.telemetry import estimate_tokens


SYSTEM_PROMPT = """You are an Indian GST invoice data extraction and classification system.
Extract data and return ONLY valid JSON. No markdown, no explanation, no code blocks. Raw JSON only.

First, classify the document. Then extract its data.

Return exactly this structure:
{
  "document_type": "tax_invoice | proforma_invoice | estimate | quote | ledger_statement | receipt | delivery_challan | purchase_order | bank_statement | other",
  "is_valid_tax_invoice": true,
  "rejection_reason": null,

  "supplier_name": "string",
  "supplier_gstin": "15-char GSTIN or null",
  "invoice_number": "string",
  "invoice_date": "YYYY-MM-DD",
  "place_of_supply": "string or null",
  "reverse_charge": false,
  "line_items": [
    {
      "description": "string",
      "hsn_sac": "string or null",
      "quantity": 1.0,
      "unit": "string or null",
      "rate": 0.0,
      "taxable_amount": 0.0,
      "cgst_rate": 9.0,
      "cgst_amount": 0.0,
      "sgst_rate": 9.0,
      "sgst_amount": 0.0,
      "igst_rate": null,
      "igst_amount": null
    }
  ],
  "total_taxable_amount": 0.0,
  "total_cgst": 0.0,
  "total_sgst": 0.0,
  "total_igst": null,
  "total_amount": 0.0
}

Classification rules:
- is_valid_tax_invoice = true ONLY if the document is a single tax invoice (or
  bill of supply) with: an invoice number, a date, a supplier, and at least one
  line item with a non-zero amount.
- is_valid_tax_invoice = false for: ledger statements (multiple vouchers),
  estimates/quotes/proforma, receipts, delivery challans, purchase orders,
  bank statements, screenshots of anything other than a posted tax invoice.
  If you see multiple invoice/voucher numbers, set false.
- rejection_reason: short sentence when false, null when true.

Extraction rules:
1. Amounts are plain numbers. Strip Rs and commas. "1,23,456.00" -> 123456.0
2. Dates to YYYY-MM-DD. "10/04/24" -> "2024-04-10"
3. GSTIN: exactly 15 chars. Return null if not found.
4. If IGST present, cgst_*/sgst_* fields are null (and vice versa).
5. reverse_charge true only if invoice explicitly says "Reverse Charge: Yes".
6. Missing fields return null. Never guess."""

_MIME_MAP = {
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "png":  "image/png",
    "heic": "image/heic",
    "webp": "image/webp",
}

IMAGE_TYPES = set(_MIME_MAP.keys())


def extract_and_classify(file_path: str, file_type: str,
                         user_id: str | None = None) -> tuple[dict, str]:
    """Main entry point. Returns (extracted_dict, extraction_method)."""
    ft = (file_type or "").lower().lstrip(".")
    if ft in IMAGE_TYPES:
        return _from_image(file_path, ft, user_id)
    return _from_pdf(file_path, user_id)


# ── PDF path ─────────────────────────────────────────────────────────────────

def extract_text(pdf_path: str) -> tuple[str, str]:
    text = _extract_with_pdfplumber(pdf_path)
    if len(text.strip()) > 50 and any(c.isdigit() for c in text):
        return text, "pdfplumber"
    return text, "pdfplumber_low_confidence"


def _extract_with_pdfplumber(path: str) -> str:
    full = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            full += (page.extract_text() or "") + "\n"
            for table in page.extract_tables():
                for row in table:
                    if row:
                        full += " | ".join(str(c or "").strip() for c in row) + "\n"
    return full.strip()


def _from_pdf(file_path: str, user_id: str | None) -> tuple[dict, str]:
    text, method = extract_text(file_path)
    prompt = f"{SYSTEM_PROMPT}\n\nExtract invoice data:\n\n{text[:50000]}"
    req_tokens = estimate_tokens(prompt)

    result = infra_router.call(
        surface="llm", task="extract_invoice",
        fn=lambda adapter: adapter.extract_json(prompt, max_tokens=8192),
        setup_ctx=lambda ctx: setattr(ctx, "request_tokens", req_tokens),
        user_id=user_id,
    )
    return result, method


# ── Image path ────────────────────────────────────────────────────────────────

def _from_image(file_path: str, file_type: str, user_id: str | None) -> tuple[dict, str]:
    mime = _MIME_MAP[file_type]
    with open(file_path, "rb") as f:
        image_bytes = f.read()

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        "Extract invoice data from this image. "
        "If the image is not a single tax invoice, set is_valid_tax_invoice to false."
    )

    def _do(adapter):
        if hasattr(adapter, "extract_json_from_image"):
            return adapter.extract_json_from_image(image_bytes, mime, prompt, max_tokens=8192)
        # Fallback: encode as base64 text description — should not happen if Gemini is configured
        raise RuntimeError(
            f"Adapter {type(adapter).__name__} does not support image extraction. "
            "Configure a Gemini provider in /settings/infra."
        )

    result = infra_router.call(
        surface="llm", task="extract_invoice_image",
        fn=_do,
        user_id=user_id,
    )
    return result, "gemini_vision"


# ── Legacy compat (pipeline still calls llm_extract directly for text) ────────

def llm_extract(text: str, user_id: str | None = None) -> dict:
    prompt = f"{SYSTEM_PROMPT}\n\nExtract invoice data:\n\n{text[:50000]}"
    req_tokens = estimate_tokens(prompt)
    return infra_router.call(
        surface="llm", task="extract_invoice",
        fn=lambda adapter: adapter.extract_json(prompt, max_tokens=8192),
        setup_ctx=lambda ctx: setattr(ctx, "request_tokens", req_tokens),
        user_id=user_id,
    )
