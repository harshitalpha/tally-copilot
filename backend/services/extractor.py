import pdfplumber, anthropic, json, os, re
from dotenv import load_dotenv

load_dotenv()

PROVIDER = (os.getenv("EXTRACTION_PROVIDER") or "gemini").lower()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemma-4-31b-it")

_anthropic = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")) if os.getenv("ANTHROPIC_API_KEY") else None

_genai_client = None
if os.getenv("GEMINI_API_KEY"):
    from google import genai
    _genai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


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
  bill of supply) that has: an invoice number, an invoice date, a supplier, and
  at least one line item with a non-zero amount.
- is_valid_tax_invoice = false for: ledger statements (showing multiple
  vouchers), estimates / quotes / proforma, receipts, delivery challans,
  purchase orders, bank statements, screenshots, anything that is not itself a
  posted tax invoice. If you see multiple invoice/voucher numbers in the same
  document, it is NOT a single tax invoice — set false.
- rejection_reason: short human sentence when false. Example: "This is a
  customer ledger statement covering 8 sale vouchers, not a single tax
  invoice." Null when true.

Extraction rules (apply even when is_valid_tax_invoice is false — fill what you
can so the user sees context, but never invent missing data):
1. Amounts are plain numbers. Strip Rs and commas. "1,23,456.00" -> 123456.0
2. Dates to YYYY-MM-DD. "10/04/24" -> "2024-04-10"
3. GSTIN: exactly 15 chars. Return null if not found.
4. If IGST present, cgst_*/sgst_* fields are null (and vice versa).
5. reverse_charge true only if invoice explicitly says "Reverse Charge: Yes".
6. Missing fields return null. Never guess."""


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


def _strip_json_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        # ```json ... ``` or ``` ... ```
        m = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
        if m:
            raw = m.group(1)
    return raw.strip("` \n")


def _llm_extract_claude(text: str) -> dict:
    if not _anthropic:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    response = _anthropic.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Extract invoice data:\n\n{text}"}],
    )
    raw = response.content[0].text
    return json.loads(_strip_json_fences(raw))


def _llm_extract_gemini(text: str) -> dict:
    if not _genai_client:
        raise RuntimeError("GEMINI_API_KEY not set")
    # Gemma models don't support system_instruction; fold the system prompt into the user message.
    prompt = f"{SYSTEM_PROMPT}\n\nExtract invoice data:\n\n{text}"
    response = _genai_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={"temperature": 0, "max_output_tokens": 8192},
    )
    raw = response.text
    return json.loads(_strip_json_fences(raw))


def llm_extract(text: str) -> dict:
    # Gemma 27B/31B and Claude both handle 50k+ tokens of input easily; the old 4000-char
    # cap was dropping the totals/tax rows that sit at the end of most invoices.
    truncated = text[:50000]
    if PROVIDER == "claude":
        return _llm_extract_claude(truncated)
    if PROVIDER == "gemini":
        return _llm_extract_gemini(truncated)
    raise RuntimeError(f"Unknown EXTRACTION_PROVIDER: {PROVIDER}")
