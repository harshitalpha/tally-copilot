"""Static catalog of supported adapters.

Each entry declares:
  surface       — which port it implements
  display_name  — what the UI shows
  fields        — schema for the config form
  factory       — function (config_dict) -> adapter instance

To add a new provider:
  1. Add an adapter class in backend/adapters/<surface>/<name>.py
  2. Add an entry below
  3. The UI will pick it up automatically
"""

CATALOG: dict[str, dict] = {
    # ---------- LLM ----------
    "gemini": {
        "surface": "llm",
        "display_name": "Google Gemini / Gemma",
        "fields": [
            {"name": "api_key",   "label": "API Key",   "type": "password", "required": True},
            {"name": "model",     "label": "Text model","type": "text",     "required": True,
             "default": "models/gemma-4-31b-it"},
            {"name": "vision_model", "label": "Vision model (for images)", "type": "text", "required": False,
             "default": "gemini-2.0-flash",
             "help": "Used for JPG/PNG/HEIC invoices. gemini-2.0-flash recommended."},
        ],
    },
    "anthropic": {
        "surface": "llm",
        "display_name": "Anthropic Claude",
        "fields": [
            {"name": "api_key", "label": "API Key", "type": "password", "required": True},
            {"name": "model",   "label": "Model",   "type": "text",     "required": True,
             "default": "claude-sonnet-4-20250514"},
        ],
    },
    "openai_compatible": {
        "surface": "llm",
        "display_name": "OpenAI-compatible (vLLM, RunPod, Together, Groq…)",
        "fields": [
            {"name": "base_url", "label": "Base URL",  "type": "text",     "required": True,
             "default": "https://api.openai.com/v1"},
            {"name": "api_key",  "label": "API Key",   "type": "password", "required": True},
            {"name": "model",    "label": "Model",     "type": "text",     "required": True},
        ],
    },

    # ---------- Object store ----------
    "local_fs": {
        "surface": "object_store",
        "display_name": "Local filesystem (dev only)",
        "fields": [
            {"name": "base_path", "label": "Base path", "type": "text", "required": True,
             "default": "uploads/"},
        ],
    },
    "s3_compatible": {
        "surface": "object_store",
        "display_name": "S3-compatible (AWS S3, Supabase, Cloudflare R2, MinIO)",
        "fields": [
            {"name": "endpoint_url", "label": "Endpoint URL", "type": "text",     "required": True,
             "default": "https://s3.amazonaws.com"},
            {"name": "access_key",   "label": "Access Key",   "type": "password", "required": True},
            {"name": "secret_key",   "label": "Secret Key",   "type": "password", "required": True},
            {"name": "bucket",       "label": "Bucket",       "type": "text",     "required": True},
            {"name": "region",       "label": "Region",       "type": "text",     "required": False,
             "default": "us-east-1"},
        ],
    },

    # ---------- Messenger (WhatsApp / SMS) ----------
    "inmemory_messenger": {
        "surface": "messenger",
        "display_name": "In-memory log (dev only)",
        "fields": [],
    },
    "meta_cloud_api": {
        "surface": "messenger",
        "display_name": "WhatsApp via Meta Cloud API",
        "fields": [
            {"name": "phone_number_id", "label": "Phone Number ID", "type": "text",     "required": True},
            {"name": "access_token",    "label": "Access Token",    "type": "password", "required": True},
            {"name": "api_version",     "label": "API Version",     "type": "text",     "required": False,
             "default": "v18.0"},
        ],
    },

    # ---------- Email ----------
    "inmemory_email": {
        "surface": "email",
        "display_name": "In-memory log (dev only)",
        "fields": [],
    },
    "resend": {
        "surface": "email",
        "display_name": "Resend (resend.com)",
        "fields": [
            {"name": "api_key",    "label": "API Key",     "type": "password", "required": True,
             "help": "Get from resend.com/api-keys. Starts with re_..."},
            {"name": "from_email", "label": "From address","type": "text",     "required": True,
             "default": "noreply@resend.dev",
             "help": "Use noreply@resend.dev for testing, or your verified domain."},
        ],
    },
}


def _factory(adapter_kind: str):
    if adapter_kind == "gemini":
        from adapters.llm.gemini import GeminiAdapter
        return lambda c: GeminiAdapter(
            api_key=c["api_key"],
            model=c.get("model") or "models/gemma-4-31b-it",
            vision_model=c.get("vision_model") or "gemini-2.0-flash",
        )
    if adapter_kind == "anthropic":
        from adapters.llm.anthropic import AnthropicAdapter
        return lambda c: AnthropicAdapter(api_key=c["api_key"], model=c.get("model") or "claude-sonnet-4-20250514")
    if adapter_kind == "openai_compatible":
        from adapters.llm.openai_compatible import OpenAICompatibleAdapter
        return lambda c: OpenAICompatibleAdapter(
            api_key=c["api_key"], model=c["model"],
            base_url=c.get("base_url") or "https://api.openai.com/v1",
        )
    if adapter_kind == "local_fs":
        from adapters.object_store.local_fs import LocalFSStore
        return lambda c: LocalFSStore(base_path=c.get("base_path") or "uploads/")
    if adapter_kind == "s3_compatible":
        from adapters.object_store.s3_compatible import S3CompatibleStore
        return lambda c: S3CompatibleStore(
            endpoint_url=c["endpoint_url"], access_key=c["access_key"],
            secret_key=c["secret_key"], bucket=c["bucket"],
            region=c.get("region") or "us-east-1",
        )
    if adapter_kind == "inmemory_messenger":
        from adapters.messenger.inmemory import InMemoryMessenger
        return lambda c: InMemoryMessenger()
    if adapter_kind == "meta_cloud_api":
        from adapters.messenger.meta_cloud_api import MetaCloudAPIMessenger
        return lambda c: MetaCloudAPIMessenger(
            phone_number_id=c["phone_number_id"],
            access_token=c["access_token"],
            api_version=c.get("api_version") or "v18.0",
        )
    if adapter_kind == "inmemory_email":
        from adapters.email.inmemory import InMemoryEmailClient
        return lambda c: InMemoryEmailClient()
    if adapter_kind == "resend":
        from adapters.email.resend import ResendEmailClient
        return lambda c: ResendEmailClient(
            api_key=c["api_key"],
            from_email=c.get("from_email") or "noreply@resend.dev",
        )
    raise ValueError(f"Unknown adapter_kind: {adapter_kind}")


def build_adapter(adapter_kind: str, config: dict):
    return _factory(adapter_kind)(config)


def list_kinds(surface: str | None = None) -> list[dict]:
    out = []
    for kind, meta in CATALOG.items():
        if surface and meta["surface"] != surface:
            continue
        out.append({"kind": kind, **meta})
    return out
